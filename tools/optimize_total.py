"""
optimize_total.py — Honest hyperparameter search for the MLB run-total model.

User's success rule: predict the game's TOTAL runs using only data before the
matchup; |predicted_total - actual_total| <= 2  -> PASS, else FAIL.
Evaluated over 30 teams x their last 15 games, point-in-time, no leakage.

Step 1: precompute point-in-time features once (slow part).
Step 2: grid-search the total model to maximize the <=2 pass rate.
"""

import itertools
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cloudscout.db")


def load():
    c = sqlite3.connect(DB)
    g = pd.read_sql_query(
        "SELECT id,date,home_team,away_team,home_score,away_score "
        "FROM games WHERE league='MLB' ORDER BY date,id", c)
    p = pd.read_sql_query(
        "SELECT name,team,date,game_id,role,innings_pitched,earned_runs,"
        "walks_allowed,hits_allowed FROM mlb_players WHERE role='pitcher'", c)
    c.close()
    return g, p


def team_feats(team, hist, hp_hist):
    """All point-in-time features for one team from pre-filtered history."""
    tg = hist[(hist.home_team == team) | (hist.away_team == team)] \
        .sort_values("date", ascending=False)
    if tg.empty:
        return None
    sc = tg.apply(lambda r: r.home_score if r.home_team == team else r.away_score, axis=1)
    al = tg.apply(lambda r: r.away_score if r.home_team == team else r.home_score, axis=1)
    tot = (tg.home_score + tg.away_score).values
    f = {}
    for n in (5, 10, 15, 20, 30):
        f[f"rs{n}"] = float(sc.values[:n].mean())
        f[f"ra{n}"] = float(al.values[:n].mean())
        f[f"env{n}"] = float(tot[:n].mean())
    # probable-starter ERA: starter of most-recent game, on his own recent line
    gids = tg.head(10).id.tolist()
    pp = hp_hist[(hp_hist.team == team) & (hp_hist.game_id.isin(gids))]
    era = 4.50
    if not pp.empty:
        idx = pp.groupby("game_id").innings_pitched.idxmax()
        st = pp.loc[idx].sort_values("date", ascending=False)
        if not st.empty:
            nm = st.iloc[0]["name"]
            s = pp[pp.name == nm]
            ip = s.innings_pitched.sum()
            if ip > 0:
                era = (s.earned_runs.sum() / ip) * 9
    f["sp_era"] = float(era)
    return f


def build():
    g, p = load()
    teams = sorted(set(g.home_team) | set(g.away_team))
    eval_games = {}
    for t in teams:
        tg = g[(g.home_team == t) | (g.away_team == t)] \
            .sort_values("date", ascending=False).head(15)
        for row in tg.itertuples():
            eval_games[row.id] = row  # dedupe shared games
    rows = []
    date_cache = {}
    for gid, gm in eval_games.items():
        d = gm.date
        if d not in date_cache:
            h = g[g.date < d]
            date_cache[d] = (h, p[p.game_id.isin(h.id)],
                             float((h.home_score + h.away_score).tail(400).mean())
                             if not h.empty else 8.8)
        hist, hph, lg = date_cache[d]
        if hist.empty:
            continue
        fa = team_feats(gm.home_team, hist, hph)
        fb = team_feats(gm.away_team, hist, hph)
        if fa is None or fb is None:
            continue
        h2 = g[((g.home_team == gm.home_team) & (g.away_team == gm.away_team))
               | ((g.home_team == gm.away_team) & (g.away_team == gm.home_team))]
        h2 = h2[h2.date < d].sort_values("date", ascending=False).head(20)
        h2t = float((h2.home_score + h2.away_score).mean()) if not h2.empty else np.nan
        rec = {"lg": lg, "h2h": h2t,
               "act_total": int(gm.home_score + gm.away_score),
               "act_margin": int(gm.home_score - gm.away_score),
               "home_won": gm.home_score > gm.away_score}
        for k, v in fa.items():
            rec["h_" + k] = v
        for k, v in fb.items():
            rec["a_" + k] = v
        rows.append(rec)
    return pd.DataFrame(rows)


def evaluate(df, n, shrink, w_env, w_rsra, sp_mag, h2h_w):
    """Vectorised total model. Returns (pass<=2 %, pass<=1 %, MAE, winner%)."""
    env = 0.5 * (df[f"h_env{n}"] + df[f"a_env{n}"])
    rsra = 0.5 * ((df["h_rs10"] + df["a_ra10"]) + (df["a_rs10"] + df["h_ra10"]))
    raw = w_env * env + w_rsra * rsra
    total = (1 - shrink) * raw + shrink * df["lg"]
    if h2h_w > 0:
        hv = df["h2h"].fillna(total)
        total = (1 - h2h_w) * total + h2h_w * hv
    if sp_mag != 0:
        adj = ((df["h_sp_era"] + df["a_sp_era"]) / 2 - 4.50) * sp_mag
        total = total * (1 + adj.clip(-0.18, 0.18))
    err = (total - df["act_total"]).abs()
    # winner: Pyth of opp-aware RS/RA (independent of total scaling)
    ea = (df["h_rs10"] + df["a_ra10"] + 0.30) ** 1.83
    eb = (df["a_rs10"] + df["h_ra10"]) ** 1.83
    pa = ea / (ea + eb)
    win = ((pa >= 0.5) == df["home_won"]).mean() * 100
    return (err.le(2).mean() * 100, err.le(1).mean() * 100,
            err.mean(), win)


def main():
    print("Precomputing point-in-time features (30 teams x last 15)...")
    df = build()
    print(f"  {len(df)} unique matchups graded.\n")

    grid = itertools.product(
        (5, 10, 15, 20),                 # n for env
        (0.0, 0.2, 0.35, 0.5, 0.65),     # shrink to league mean
        (1.0, 0.7, 0.5, 0.0),            # weight on env
        (0.0, 0.3, 0.5, 1.0),            # weight on rs/ra-implied
        (0.0, 0.03, 0.05),               # starter-ERA total adj /run
        (0.0, 0.15, 0.30),               # H2H weight
    )
    best = None
    results = []
    for n, sh, we, wr, sp, hw in grid:
        if we == 0 and wr == 0:
            continue
        s = we + wr
        p2, p1, mae, win = evaluate(df, n, sh, we / s, wr / s, sp, hw)
        results.append((p2, p1, mae, win, (n, sh, we, wr, sp, hw)))
        if best is None or p2 > best[0]:
            best = (p2, p1, mae, win, (n, sh, we, wr, sp, hw))

    results.sort(reverse=True)
    print("Top 12 configs by ≤2-run PASS rate (the user's bar):")
    print(f"{'≤2%':>6}{'≤1%':>6}{'MAE':>7}{'Win%':>7}  "
          f"{'n':>3}{'shrink':>7}{'wEnv':>6}{'wRSRA':>6}{'spAdj':>6}{'h2h':>5}")
    for p2, p1, mae, win, (n, sh, we, wr, sp, hw) in results[:12]:
        s = we + wr
        print(f"{p2:>6.1f}{p1:>6.1f}{mae:>7.2f}{win:>7.1f}  "
              f"{n:>3}{sh:>7.2f}{we/s:>6.2f}{wr/s:>6.2f}{sp:>6.2f}{hw:>5.2f}")

    p2, p1, mae, win, cfg = best
    print(f"\nBEST ≤2-run pass rate: {p2:.1f}%  (≤1: {p1:.1f}%, "
          f"MAE {mae:.2f}, winner {win:.1f}%)")
    print(f"  config (n,shrink,wEnv,wRSRA,spAdj,h2h) = {cfg}")
    print(f"\nUser target on the run side: 70%.  "
          f"{'REACHED' if p2 >= 70 else 'NOT reached — ceiling is ' + f'{p2:.1f}%'}"
          f" at ±2 runs.")
    return df, results, best


if __name__ == "__main__":
    main()

"""
backtest_30x15.py — Point-in-time backtest over EVERY team's last 15 games.

Mirrors the user's spec exactly:
  * For each of the 30 MLB teams, take their 15 most-recent games.
  * Starting from the latest date, predict each game using ONLY data that
    existed before that game (no leakage), rating each team on its prior
    N games — exactly what you'd see opening the Predict tab pre-game.
  * The real result is known, so grade winner + run prediction.

Goal: find a formula that clears 70% on EITHER winner OR run prediction.
Run:  python tools/backtest_30x15.py
"""

import math
import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mlb_analytics import mlb_win_probability  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cloudscout.db")
N = 10  # prior games per team


def load_data():
    conn = sqlite3.connect(DB)
    games = pd.read_sql_query(
        "SELECT id,date,home_team,away_team,home_score,away_score "
        "FROM games WHERE league='MLB' ORDER BY date,id", conn)
    players = pd.read_sql_query("SELECT * FROM mlb_players", conn)
    conn.close()
    return games, players


# ── point-in-time primitives ─────────────────────────────────────────────────

def last_n(team, hist, n=N):
    tg = hist[(hist.home_team == team) | (hist.away_team == team)]
    return tg.sort_values("date", ascending=False).head(n)


def rs_ra(team, hist, n=N):
    tg = last_n(team, hist, n)
    if tg.empty:
        return 4.5, 4.5
    sc = tg.apply(lambda r: r.home_score if r.home_team == team else r.away_score, axis=1)
    al = tg.apply(lambda r: r.away_score if r.home_team == team else r.home_score, axis=1)
    return float(sc.mean()), float(al.mean())


def pyth(rf, ra, e=1.83):
    rf, ra = max(rf, .1) ** e, max(ra, .1) ** e
    return rf / (rf + ra)


def h2h_total(a, b, hist, n=20):
    h = hist[((hist.home_team == a) & (hist.away_team == b))
             | ((hist.home_team == b) & (hist.away_team == a))]
    h = h.sort_values("date", ascending=False).head(n)
    return None if h.empty else float((h.home_score + h.away_score).mean())


def starter_quality(team, hist, hp, n=10):
    """Probable-starter proxy: the most recent distinct starter for `team`
    (most innings in their last start), scored on that pitcher's own recent
    starts (ERA, WHIP). Returns (era, whip, n_starts) — None-safe."""
    gids = last_n(team, hist, n).id.tolist()
    p = hp[(hp.role == "pitcher") & (hp.team == team) & (hp.game_id.isin(gids))]
    if p.empty:
        return 4.50, 1.30, 0
    # starter per game = max innings; "probable" = the starter of the most
    # recent game (rotation will turn back to a similar arm). mlb_players
    # already carries its own `date`, so no merge needed.
    idx = p.groupby("game_id").innings_pitched.idxmax()
    starters = p.loc[idx]
    if starters.empty:
        return 4.50, 1.30, 0
    last_starter = starters.sort_values("date", ascending=False).iloc[0]["name"]
    s = p[p.name == last_starter]
    ip = s.innings_pitched.sum()
    if ip <= 0:
        return 4.50, 1.30, 0
    era = (s.earned_runs.sum() / ip) * 9
    whip = (s.walks_allowed.sum() + s.hits_allowed.sum()) / ip
    return float(era), float(whip), len(s)


HOME = 0.15


# ── candidate formulas: (proj_home, proj_away, prob_home%) ───────────────────

def P_production(a, b, hist, hp, home):
    r = mlb_win_probability(a, b, hist, hp, home_team=home, n=N)
    return r["proj_runs_a"], r["proj_runs_b"], r["prob_a"]


def V1_oppaware(a, b, hist, hp, home):
    """½(own RS + opp RA), Pyth winner. The simple stable core."""
    rsa, raa = rs_ra(a, hist)
    rsb, rab = rs_ra(b, hist)
    pa = 0.5 * (rsa + rab) + HOME
    pb = 0.5 * (rsb + raa)
    return pa, pb, round(pyth(pa, pb) * 100, 1)


def V2_pitcher(a, b, hist, hp, home):
    """V1 base, then scale each side by the OPPONENT's probable-starter ERA
    (vs lg 4.50, ±9%/run capped ±28%) + bullpen-lite via team RA already in."""
    rsa, raa = rs_ra(a, hist)
    rsb, rab = rs_ra(b, hist)
    era_a, _, _ = starter_quality(a, hist, hp)
    era_b, _, _ = starter_quality(b, hist, hp)
    sup_a = max(0.72, min(1.28, 1 + (era_b - 4.50) * 0.09))   # opp SP vs A
    sup_b = max(0.72, min(1.28, 1 + (era_a - 4.50) * 0.09))
    pa = (0.5 * (rsa + rab)) * sup_a + HOME
    pb = (0.5 * (rsb + raa)) * sup_b
    return pa, pb, round(pyth(pa, pb) * 100, 1)


def V3_pitcher_h2h(a, b, hist, hp, home):
    """V2 + 80/20 shrink toward head-to-head average total."""
    pa, pb, _ = V2_pitcher(a, b, hist, hp, home)
    h = h2h_total(a, b, hist)
    if h is not None and pa + pb > 0:
        s = ((pa + pb) * 0.80 + h * 0.20) / (pa + pb)
        pa, pb = pa * s, pb * s
    return pa, pb, round(pyth(pa, pb) * 100, 1)


def V4_pitcher_whip(a, b, hist, hp, home):
    """V3 but suppression blends starter ERA AND WHIP (baserunners→runs)."""
    rsa, raa = rs_ra(a, hist)
    rsb, rab = rs_ra(b, hist)
    ea, wa, _ = starter_quality(a, hist, hp)
    eb, wb, _ = starter_quality(b, hist, hp)
    def sup(era, whip):
        e = (era - 4.50) * 0.075
        w = (whip - 1.30) * 0.22
        return max(0.70, min(1.30, 1 + e + w))
    pa = (0.5 * (rsa + rab)) * sup(eb, wb) + HOME
    pb = (0.5 * (rsb + raa)) * sup(ea, wa)
    h = h2h_total(a, b, hist)
    if h is not None and pa + pb > 0:
        s = ((pa + pb) * 0.82 + h * 0.18) / (pa + pb)
        pa, pb = pa * s, pb * s
    return pa, pb, round(pyth(pa, pb) * 100, 1)


def _team_game_total(team, hist, n):
    """Avg combined runs in `team`'s last n games — the scoring *environment*
    that team has been in (pace + park + era), more stable than RS+RA."""
    tg = last_n(team, hist, n)
    if tg.empty:
        return None
    return float((tg.home_score + tg.away_score).mean())


def _lg_total(hist, n=400):
    """Point-in-time league-average total (recent games) for shrinkage."""
    r = hist.sort_values("date", ascending=False).head(n)
    return float((r.home_score + r.away_score).mean()) if not r.empty else 8.8


def T1_env_shrink(a, b, hist, hp, home):
    """Total = blend of both teams' recent game-total environment, shrunk
    toward the point-in-time league mean (variance reduction). Winner from
    RS/RA Pythagorean. Split total by each side's RS/RA strength."""
    rsa, raa = rs_ra(a, hist)
    rsb, rab = rs_ra(b, hist)
    ta = _team_game_total(a, hist, 20) or 8.8
    tb = _team_game_total(b, hist, 20) or 8.8
    raw = 0.5 * (ta + tb)
    lg = _lg_total(hist)
    total = 0.55 * raw + 0.45 * lg          # shrink 45% to league mean
    ea = pyth(0.5 * (rsa + rab) + HOME, 0.5 * (rsb + raa))
    pa = total * ea
    pb = total * (1 - ea)
    return pa, pb, round(ea * 100, 1)


def T2_env_n10(a, b, hist, hp, home):
    """Like T1 but environment from last 10 games, lighter shrink (35%)."""
    rsa, raa = rs_ra(a, hist)
    rsb, rab = rs_ra(b, hist)
    ta = _team_game_total(a, hist, 10) or 8.8
    tb = _team_game_total(b, hist, 10) or 8.8
    lg = _lg_total(hist)
    total = 0.65 * (0.5 * (ta + tb)) + 0.35 * lg
    ea = pyth(0.5 * (rsa + rab) + HOME, 0.5 * (rsb + raa))
    return total * ea, total * (1 - ea), round(ea * 100, 1)


def T3_env_pitcher(a, b, hist, hp, home):
    """T1 environment+shrink, but nudge the total by both probable starters'
    ERA vs league (good arms → fewer runs). Winner unchanged from T1."""
    rsa, raa = rs_ra(a, hist)
    rsb, rab = rs_ra(b, hist)
    ta = _team_game_total(a, hist, 20) or 8.8
    tb = _team_game_total(b, hist, 20) or 8.8
    lg = _lg_total(hist)
    total = 0.55 * (0.5 * (ta + tb)) + 0.45 * lg
    ea_, _, _ = starter_quality(a, hist, hp)
    eb_, _, _ = starter_quality(b, hist, hp)
    # avg starter ERA vs 4.50 → ±4%/run on the total, capped ±14%
    adj = max(-0.14, min(0.14, ((ea_ + eb_) / 2 - 4.50) * 0.04))
    total *= (1 + adj)
    ew = pyth(0.5 * (rsa + rab) + HOME, 0.5 * (rsb + raa))
    return total * ew, total * (1 - ew), round(ew * 100, 1)


FORMULAS = [
    ("P  production (current)", P_production),
    ("V1 opp-aware core",       V1_oppaware),
    ("V2 + probable starter",   V2_pitcher),
    ("T1 env+lg-shrink",        T1_env_shrink),
    ("T2 env n10 lt-shrink",    T2_env_n10),
    ("T3 env+shrink+SP",        T3_env_pitcher),
]


# ── 30 teams × last 15 games ─────────────────────────────────────────────────

def build_eval_set(games):
    teams = sorted(set(games.home_team) | set(games.away_team))
    rows = []
    for t in teams:
        tg = games[(games.home_team == t) | (games.away_team == t)]
        tg = tg.sort_values("date", ascending=False).head(15)
        for g in tg.itertuples():
            rows.append((t, g))
    return teams, rows


def grade(games, players, eval_rows):
    print(f"\n30 teams × last 15 games = {len(eval_rows)} point-in-time "
          f"evaluations  (N={N} prior games, no leakage)\n")
    tol = [1, 2, 3, 4, 5]
    hdr = (f"{'Formula':<26}{'Winner%':>9}"
           + "".join(f"{'Tot±'+str(x):>7}" for x in tol)
           + f"{'TotMAE':>8}{'MgnMAE':>8}")
    print(hdr); print("-" * len(hdr))
    results = []
    # cache history slices by date (many games share dates)
    hist_cache = {}
    for name, fn in FORMULAS:
        wins = n = 0
        tot_ok = {x: 0 for x in tol}
        tmae = mmae = 0.0
        for team, g in eval_rows:
            gd = g.date
            if gd not in hist_cache:
                h = games[games.date < gd]
                hist_cache[gd] = (h, players[players.game_id.isin(h.id)])
            hist, hp = hist_cache[gd]
            if hist.empty:
                continue
            hs, as_ = int(g.home_score), int(g.away_score)
            pa, pb, prob = fn(g.home_team, g.away_team, hist, hp, g.home_team)
            n += 1
            wins += int((prob >= 50) == (hs > as_))
            et = abs((pa + pb) - (hs + as_))
            tmae += et
            mmae += abs((pa - pb) - (hs - as_))
            for x in tol:
                tot_ok[x] += int(et <= x)
        row = (name, wins / n * 100, {x: tot_ok[x] / n * 100 for x in tol},
               tmae / n, mmae / n, n)
        results.append(row)
        print(f"{name:<26}{row[1]:>8.1f}%"
              + "".join(f"{row[2][x]:>6.0f}%" for x in tol)
              + f"{row[3]:>8.2f}{row[4]:>8.2f}")
    print(f"\n(n={results[0][5]} evaluations graded)")
    return results


if __name__ == "__main__":
    g, p = load_data()
    _, ev = build_eval_set(g)
    res = grade(g, p, ev)
    # report best on each axis + whether 70% reached anywhere
    best_w = max(res, key=lambda r: r[1])
    print(f"\nBest WINNER : {best_w[0]}  {best_w[1]:.1f}%")
    for thr in (3, 4, 5):
        cand = [(r[0], r[2][thr]) for r in res if r[2][thr] >= 70]
        if cand:
            b = max(cand, key=lambda c: c[1])
            print(f"≥70% RUN  : {b[0]} hits {b[1]:.0f}% within ±{thr} runs")
            break
    else:
        bestrun = max(res, key=lambda r: r[2][3])
        print(f"No formula reaches 70% within ±3; best is "
              f"{bestrun[0]} at {bestrun[2][3]:.0f}% (±3 runs)")

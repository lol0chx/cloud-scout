"""
backtest_mlb.py — Point-in-time backtest of MLB run/winner prediction formulas.

Methodology (mirrors a real "go to Predict, pick a matchup" flow):
  * Pick 15 real matchups spread across 10 distinct game days.
  * For each matchup on date D, the model may ONLY see games played on
    dates strictly before D (no leakage). Each team is scored on its
    previous N=10 games — exactly the data a user would have pre-game.
  * The actual final score is known (games already happened), so we can
    grade each formula: did it pick the winner? how close were the
    projected runs / margin / total?

Run:  python tools/backtest_mlb.py
"""

import math
import os
import sqlite3
import sys

import pandas as pd

# Allow running from tools/ — add repo root to path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mlb_analytics import mlb_win_probability  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cloudscout.db")
N = 10  # "previous 10 games" per team, as the user specified


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data():
    conn = sqlite3.connect(DB)
    games = pd.read_sql_query(
        "SELECT id, date, home_team, away_team, home_score, away_score "
        "FROM games WHERE league='MLB' ORDER BY date, id",
        conn,
    )
    players = pd.read_sql_query(
        "SELECT name, team, date, game_id, role, at_bats, hits, runs, "
        "home_runs, rbi, walks, strikeouts, innings_pitched, hits_allowed, "
        "earned_runs, walks_allowed, strikeouts_pitched, home_runs_allowed "
        "FROM mlb_players",
        conn,
    )
    conn.close()
    return games, players


# ── Point-in-time helpers ─────────────────────────────────────────────────────

def team_last_n(team, hist, n=N):
    """Most recent n games for `team` from already date-filtered history."""
    tg = hist[(hist.home_team == team) | (hist.away_team == team)]
    return tg.sort_values("date", ascending=False).head(n)


def scored_allowed(team, hist, n=N):
    """(avg runs scored, avg runs allowed) over last n games. League-avg fallback."""
    tg = team_last_n(team, hist, n)
    if tg.empty:
        return 4.5, 4.5, 0
    sc = tg.apply(lambda r: r.home_score if r.home_team == team else r.away_score, axis=1)
    al = tg.apply(lambda r: r.away_score if r.home_team == team else r.home_score, axis=1)
    return float(sc.mean()), float(al.mean()), len(tg)


def pythagorean(rf, ra, exp=1.83):
    rf, ra = max(rf, 0.1) ** exp, max(ra, 0.1) ** exp
    return rf / (rf + ra)


def h2h_total(a, b, hist, n=20):
    h = hist[((hist.home_team == a) & (hist.away_team == b))
             | ((hist.home_team == b) & (hist.away_team == a))]
    h = h.sort_values("date", ascending=False).head(n)
    if h.empty:
        return None
    return float((h.home_score + h.away_score).mean())


HOME_EDGE = 0.15  # ~0.15 run typical MLB home-field bump


# ── Candidate formulas ────────────────────────────────────────────────────────
# Each returns (proj_a, proj_b, prob_a_pct). team_a is the HOME team.

def f0_baseline(a, b, hist, hist_players, home):
    """Current production model: 8-pillar composite + Pythagorean blend."""
    r = mlb_win_probability(a, b, hist, hist_players, home_team=home, n=N)
    return r["proj_runs_a"], r["proj_runs_b"], r["prob_a"]


def f1_recent_scoring(a, b, hist, hist_players, home):
    """Team offense vs opponent run-prevention, averaged. Pyth win prob."""
    sa, aa, _ = scored_allowed(a, hist)
    sb, ab, _ = scored_allowed(b, hist)
    pa = (sa + ab) / 2 + HOME_EDGE
    pb = (sb + aa) / 2
    return pa, pb, round(pythagorean(pa, pb) * 100, 1)


def f2_pythagorean_form(a, b, hist, hist_players, home):
    """Each team's L10 Pythagorean strength, combined via Bill James' Log5."""
    sa, aa, _ = scored_allowed(a, hist)
    sb, ab, _ = scored_allowed(b, hist)
    ea, eb = pythagorean(sa, aa), pythagorean(sb, ab)
    denom = ea + eb - 2 * ea * eb
    log5_a = (ea - ea * eb) / denom if denom > 0 else 0.5
    log5_a = min(0.92, max(0.08, log5_a + 0.03))  # small home tilt
    pa = (sa + ab) / 2 + HOME_EDGE
    pb = (sb + aa) / 2
    return pa, pb, round(log5_a * 100, 1)


def f3_pitching_adjusted(a, b, hist, hist_players, home):
    """Run projection scaled by opponent starter ERA; prob = Pythagorean only.

    Isolates the run-projection core (no 8-pillar layer) to test whether the
    pillar composite helps or hurts vs. straight baseball run math.
    """
    def starter_era(team):
        gids = team_last_n(team, hist).id.tolist()
        p = hist_players[(hist_players.role == "pitcher")
                         & (hist_players.team == team)
                         & (hist_players.game_id.isin(gids))]
        if p.empty:
            return 4.50
        # starter = most innings per game
        idx = p.groupby("game_id").innings_pitched.idxmax()
        s = p.loc[idx]
        ip = s.innings_pitched.sum()
        if ip <= 0:
            return 4.50
        return (s.earned_runs.sum() / ip) * 9

    sa, aa, _ = scored_allowed(a, hist)
    sb, ab, _ = scored_allowed(b, hist)
    # opp starter ERA vs league 4.50 → ±7.5%/run, clamped ±25%
    supp_a = max(0.75, min(1.25, 1.0 + (starter_era(b) - 4.50) * 0.075))
    supp_b = max(0.75, min(1.25, 1.0 + (starter_era(a) - 4.50) * 0.075))
    pa = ((sa + ab) / 2) * supp_a + HOME_EDGE
    pb = ((sb + aa) / 2) * supp_b
    return pa, pb, round(pythagorean(pa, pb) * 100, 1)


def _decay_means(team, hist, n=12, decay=0.85):
    tg = team_last_n(team, hist, n)
    if tg.empty:
        return 4.5, 4.5
    rows = list(tg.itertuples())
    w = [decay ** i for i in range(len(rows))]  # most recent = weight 1
    sw = sum(w)
    sc = sum(wi * (r.home_score if r.home_team == team else r.away_score)
             for wi, r in zip(w, rows)) / sw
    al = sum(wi * (r.away_score if r.home_team == team else r.home_score)
             for wi, r in zip(w, rows)) / sw
    return sc, al


def f4_decay_form(a, b, hist, hist_players, home):
    """Exponentially recency-weighted run differential → logistic win prob."""
    sa, aa = _decay_means(a, hist)
    sb, ab = _decay_means(b, hist)
    pa = (sa + ab) / 2 + HOME_EDGE
    pb = (sb + aa) / 2
    diff = (sa - aa) - (sb - ab) + 0.30  # +0.30 logit home edge
    prob = 1.0 / (1.0 + math.exp(-0.42 * diff))
    return pa, pb, round(prob * 100, 1)


def f5_ensemble(a, b, hist, hist_players, home):
    """Average of F1/F3/F4 run projections; win prob = mean of F1/F2/F3/F4."""
    outs = [f(a, b, hist, hist_players, home)
            for f in (f1_recent_scoring, f3_pitching_adjusted, f4_decay_form)]
    pa = sum(o[0] for o in outs) / 3
    pb = sum(o[1] for o in outs) / 3
    probs = [f(a, b, hist, hist_players, home)[2]
             for f in (f1_recent_scoring, f2_pythagorean_form,
                       f3_pitching_adjusted, f4_decay_form)]
    return pa, pb, round(sum(probs) / len(probs), 1)


def f6_log5_winpct(a, b, hist, hist_players, home):
    """Pure win% (L20) combined via Log5 for the winner; F1 runs for totals."""
    def winpct(team):
        tg = team_last_n(team, hist, 20)
        if tg.empty:
            return 0.5
        sc = tg.apply(lambda r: r.home_score if r.home_team == team else r.away_score, axis=1)
        al = tg.apply(lambda r: r.away_score if r.home_team == team else r.home_score, axis=1)
        return float((sc.values > al.values).mean())

    wa, wb = winpct(a), winpct(b)
    denom = wa + wb - 2 * wa * wb
    p = (wa - wa * wb) / denom if denom > 0 else 0.5
    p = min(0.90, max(0.10, p + 0.03))
    pa, pb, _ = f1_recent_scoring(a, b, hist, hist_players, home)
    return pa, pb, round(p * 100, 1)


FORMULAS = [
    ("F0 Baseline (8-pillar+Pyth)", f0_baseline),
    ("F1 RecentScoringAvg",         f1_recent_scoring),
    ("F2 PythagoreanForm/Log5",     f2_pythagorean_form),
    ("F3 PitchingAdjusted",         f3_pitching_adjusted),
    ("F4 DecayWeightedForm",        f4_decay_form),
    ("F5 Ensemble",                 f5_ensemble),
    ("F6 Log5 WinPct",              f6_log5_winpct),
]


# ── Matchup selection: 15 games across 10 distinct days ───────────────────────

def pick_matchups(games, n_days=10, n_matchups=15):
    """`n_days` evenly-spread game days in the 2026 season, `n_matchups`
    games total. Round-robin one game per day per pass until full, so every
    chosen day contributes and the spread is preserved. Deterministic."""
    all_dates = sorted(games[games.date >= "2026-03-25"].date.unique())
    # Evenly-spaced distinct day indices.
    idxs, seen = [], set()
    for k in range(n_days):
        i = int(round(k * (len(all_dates) - 1) / (n_days - 1)))
        while i in seen:
            i += 1
        seen.add(i)
        idxs.append(i)
    chosen_dates = [all_dates[i] for i in idxs]

    per_day = {d: list(games[games.date == d].sort_values("id").itertuples())
               for d in chosen_dates}
    matchups, pass_i = [], 0
    while len(matchups) < n_matchups:
        progressed = False
        for d in chosen_dates:
            if pass_i < len(per_day[d]):
                matchups.append(per_day[d][pass_i])
                progressed = True
                if len(matchups) == n_matchups:
                    break
        pass_i += 1
        if not progressed:
            break
    return matchups


# ── Run backtest ──────────────────────────────────────────────────────────────

def main():
    games, players = load_data()
    matchups = pick_matchups(games)

    # Accumulators per formula
    stats = {name: dict(correct=0, n=0, tot_ae=0.0, mgn_ae=0.0,
                         brier=0.0, tot_within2=0) for name, _ in FORMULAS}
    rows = []  # per-matchup detail for the report

    for g in matchups:
        gid, gdate = int(g.id), g.date
        home, away = g.home_team, g.away_team
        hs, as_ = int(g.home_score), int(g.away_score)
        actual_total = hs + as_
        actual_margin = hs - as_           # home minus away
        home_won = hs > as_

        hist = games[games.date < gdate]   # POINT-IN-TIME: nothing from gdate on
        hist_players = players[players.game_id.isin(hist.id)]

        rec = {"matchup": f"{away} @ {home}", "date": gdate,
               "actual": f"{home} {hs}-{as_} {away}",
               "actual_total": actual_total, "actual_margin": actual_margin,
               "preds": {}}

        for name, fn in FORMULAS:
            pa, pb, prob_a = fn(home, away, hist, hist_players, home)
            pred_total = pa + pb
            pred_margin = pa - pb          # home minus away
            pred_home_win = prob_a >= 50.0
            correct = (pred_home_win == home_won)

            s = stats[name]
            s["n"] += 1
            s["correct"] += int(correct)
            s["tot_ae"] += abs(pred_total - actual_total)
            s["mgn_ae"] += abs(pred_margin - actual_margin)
            s["brier"] += ((prob_a / 100.0) - (1.0 if home_won else 0.0)) ** 2
            s["tot_within2"] += int(abs(pred_total - actual_total) <= 2.0)

            rec["preds"][name] = dict(
                pa=round(pa, 2), pb=round(pb, 2), prob_a=prob_a,
                pred_total=round(pred_total, 1), pred_margin=round(pred_margin, 1),
                pick=home if pred_home_win else away, correct=correct)
        rows.append(rec)

    # ── Print scoreboard ──────────────────────────────────────────────────
    print(f"\nPoint-in-time backtest — {len(matchups)} matchups, "
          f"N={N} prior games/team, no data leakage\n")
    hdr = (f"{'Formula':<30}{'Win%':>7}{'TotalMAE':>10}"
           f"{'MgnMAE':>9}{'Brier':>8}{'Tot±2':>7}")
    print(hdr)
    print("-" * len(hdr))
    ranking = []
    for name, _ in FORMULAS:
        s = stats[name]
        acc = s["correct"] / s["n"] * 100
        tmae = s["tot_ae"] / s["n"]
        mmae = s["mgn_ae"] / s["n"]
        brier = s["brier"] / s["n"]
        tw2 = s["tot_within2"] / s["n"] * 100
        ranking.append((name, acc, tmae, mmae, brier, tw2))
        print(f"{name:<30}{acc:>6.1f}%{tmae:>10.2f}{mmae:>9.2f}"
              f"{brier:>8.3f}{tw2:>6.0f}%")

    # Composite score: winner accuracy is king, then total & margin error.
    def composite(r):
        _, acc, tmae, mmae, brier, _ = r
        return acc - 4.0 * tmae - 2.0 * mmae - 30.0 * brier

    best = max(ranking, key=composite)
    print(f"\nBest by composite (acc − 4·TotMAE − 2·MgnMAE − 30·Brier): "
          f"{best[0]}")

    return rows, ranking, best, matchups


if __name__ == "__main__":
    main()

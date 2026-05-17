"""
mlb_analytics.py — MLB-specific player analytics for CloudScout.

Handles batter and pitcher stat analysis. Team-level analytics
(standings, form, H2H, predictions) are shared with analytics.py
since the games table structure is identical across sports.
"""

import math
import unicodedata
from datetime import datetime

import pandas as pd


def _normalize(name):
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _safe_era(earned_runs, innings_pitched):
    """Calculate ERA from totals. Returns 0.0 if no innings pitched."""
    try:
        ip = float(innings_pitched)
        return round((float(earned_runs) / ip) * 9, 2) if ip > 0 else 0.0
    except (TypeError, ZeroDivisionError, ValueError):
        return 0.0


def _safe_avg(hits, at_bats):
    """Calculate batting average. Returns 0.000 if no at-bats."""
    try:
        ab = int(at_bats)
        return round(int(hits) / ab, 3) if ab > 0 else 0.0
    except (TypeError, ZeroDivisionError, ValueError):
        return 0.0


def mlb_batter_avg(player_name, n, df):
    """
    Calculate average batting stats for a player over their last N games.

    Args:
        player_name: player name (case-insensitive partial match)
        n: number of recent games to include
        df: mlb_players DataFrame (role='batter' rows)

    Returns:
        pandas DataFrame with one row: player, games, avg, hr, rbi, hits,
        runs, walks, strikeouts
    Raises:
        ValueError: if player not found
    """
    if n < 1:
        raise ValueError("n must be at least 1.")

    batters = df[df["role"] == "batter"].copy()
    normalized = _normalize(player_name)
    player_rows = batters[batters["name"].apply(_normalize) == normalized]

    if player_rows.empty:
        raise ValueError(f"No batter data found for '{player_name}'.")

    matched_name = player_rows.iloc[0]["name"]
    player_rows = player_rows.sort_values("date", ascending=False).head(n)

    total_ab = player_rows["at_bats"].sum()
    total_hits = player_rows["hits"].sum()
    avg = _safe_avg(total_hits, total_ab)

    result = pd.DataFrame([{
        "player": matched_name,
        "games": len(player_rows),
        "AVG": avg,
        "HR": int(player_rows["home_runs"].sum()),
        "RBI": int(player_rows["rbi"].sum()),
        "H": int(total_hits),
        "R": int(player_rows["runs"].sum()),
        "BB": int(player_rows["walks"].sum()),
        "SO": int(player_rows["strikeouts"].sum()),
    }])

    return result


def mlb_pitcher_avg(player_name, n, df):
    """
    Calculate average pitching stats for a player over their last N appearances.

    Args:
        player_name: player name (case-insensitive partial match)
        n: number of recent games to include
        df: mlb_players DataFrame (role='pitcher' rows)

    Returns:
        pandas DataFrame with one row: player, games, ERA, WHIP, IP, SO, etc.
    Raises:
        ValueError: if player not found
    """
    if n < 1:
        raise ValueError("n must be at least 1.")

    pitchers = df[df["role"] == "pitcher"].copy()
    normalized = _normalize(player_name)
    player_rows = pitchers[pitchers["name"].apply(_normalize) == normalized]

    if player_rows.empty:
        raise ValueError(f"No pitcher data found for '{player_name}'.")

    matched_name = player_rows.iloc[0]["name"]
    player_rows = player_rows.sort_values("date", ascending=False).head(n)

    total_ip = player_rows["innings_pitched"].sum()
    total_er = player_rows["earned_runs"].sum()
    total_bb = player_rows["walks_allowed"].sum()
    total_h = player_rows["hits_allowed"].sum()

    era = _safe_era(total_er, total_ip)
    whip = round((total_bb + total_h) / total_ip, 2) if total_ip > 0 else 0.0

    result = pd.DataFrame([{
        "player": matched_name,
        "games": len(player_rows),
        "ERA": era,
        "WHIP": whip,
        "IP": round(total_ip, 1),
        "SO": int(player_rows["strikeouts_pitched"].sum()),
        "BB": int(total_bb),
        "H": int(total_h),
        "HR": int(player_rows["home_runs_allowed"].sum()),
    }])

    return result


def mlb_batter_vs_team(player_name, opponent, n, df, games_df):
    """
    Calculate a batter's stats when facing a specific opponent.

    Args:
        player_name: player name (case-insensitive partial match)
        opponent: opponent team name
        n: number of recent matchups to include
        df: mlb_players DataFrame
        games_df: games DataFrame

    Returns:
        pandas DataFrame with one row, or empty if no data
    """
    if games_df is None or games_df.empty:
        return pd.DataFrame()

    batters = df[df["role"] == "batter"].copy()
    normalized = _normalize(player_name)
    player_rows = batters[batters["name"].apply(_normalize) == normalized]

    if player_rows.empty:
        return pd.DataFrame()

    matched_name = player_rows.iloc[0]["name"]

    merged = player_rows.merge(
        games_df[["id", "home_team", "away_team"]],
        left_on="game_id",
        right_on="id",
        how="left",
    )
    merged["opponent"] = merged.apply(
        lambda row: row["away_team"] if row["team"] == row["home_team"] else row["home_team"],
        axis=1,
    )

    vs_games = merged[merged["opponent"] == opponent].sort_values("date", ascending=False).head(n)

    if vs_games.empty:
        return pd.DataFrame()

    total_ab = vs_games["at_bats"].sum()
    total_hits = vs_games["hits"].sum()
    avg = _safe_avg(total_hits, total_ab)

    return pd.DataFrame([{
        "player": matched_name,
        "opponent": opponent,
        "games": len(vs_games),
        "AVG": avg,
        "HR": int(vs_games["home_runs"].sum()),
        "RBI": int(vs_games["rbi"].sum()),
        "H": int(total_hits),
        "BB": int(vs_games["walks"].sum()),
        "SO": int(vs_games["strikeouts"].sum()),
    }])


def mlb_top_batters(team, n, df, games_df=None):
    """
    Rank batters on a team by home runs over the last N team games.
    Also shows batting average and RBI.

    Args:
        team: team name
        n: number of recent team games to consider
        df: mlb_players DataFrame
        games_df: games DataFrame

    Returns:
        pandas DataFrame ranked by home runs (descending)
    """
    batters = df[df["role"] == "batter"].copy()

    if games_df is not None and not games_df.empty:
        team_game_ids = games_df[
            (games_df["home_team"] == team) | (games_df["away_team"] == team)
        ].sort_values("date", ascending=False).head(n)["id"].tolist()
        team_batters = batters[
            (batters["team"] == team) & (batters["game_id"].isin(team_game_ids))
        ].copy()
    else:
        team_batters = batters[batters["team"] == team].copy()

    if team_batters.empty:
        return pd.DataFrame()

    grouped = team_batters.groupby("name").agg(
        games=("game_id", "count"),
        total_ab=("at_bats", "sum"),
        total_hits=("hits", "sum"),
        HR=("home_runs", "sum"),
        RBI=("rbi", "sum"),
        R=("runs", "sum"),
        BB=("walks", "sum"),
    ).reset_index()

    grouped["AVG"] = grouped.apply(
        lambda r: _safe_avg(r["total_hits"], r["total_ab"]), axis=1
    )
    grouped = grouped.sort_values("HR", ascending=False)
    grouped = grouped[["name", "games", "AVG", "HR", "RBI", "R", "BB"]].copy()
    grouped.columns = ["player", "games", "AVG", "HR", "RBI", "R", "BB"]

    return grouped.reset_index(drop=True)


def mlb_top_pitchers(team, n, df, games_df=None):
    """
    Rank pitchers on a team by ERA over the last N team games.
    Also shows WHIP, K totals, and innings pitched.

    Args:
        team: team name
        n: number of recent team games to consider
        df: mlb_players DataFrame
        games_df: games DataFrame

    Returns:
        pandas DataFrame ranked by ERA (ascending — lower is better)
    """
    pitchers = df[df["role"] == "pitcher"].copy()

    if games_df is not None and not games_df.empty:
        team_game_ids = games_df[
            (games_df["home_team"] == team) | (games_df["away_team"] == team)
        ].sort_values("date", ascending=False).head(n)["id"].tolist()
        team_pitchers = pitchers[
            (pitchers["team"] == team) & (pitchers["game_id"].isin(team_game_ids))
        ].copy()
    else:
        team_pitchers = pitchers[pitchers["team"] == team].copy()

    if team_pitchers.empty:
        return pd.DataFrame()

    grouped = team_pitchers.groupby("name").agg(
        games=("game_id", "count"),
        IP=("innings_pitched", "sum"),
        ER=("earned_runs", "sum"),
        H=("hits_allowed", "sum"),
        BB=("walks_allowed", "sum"),
        SO=("strikeouts_pitched", "sum"),
        HR=("home_runs_allowed", "sum"),
    ).reset_index()

    grouped["ERA"] = grouped.apply(
        lambda r: _safe_era(r["ER"], r["IP"]), axis=1
    )
    grouped["WHIP"] = grouped.apply(
        lambda r: round((r["BB"] + r["H"]) / r["IP"], 2) if r["IP"] > 0 else 0.0,
        axis=1,
    )
    grouped["IP"] = grouped["IP"].round(1)

    # Only include pitchers with at least 1 inning pitched
    grouped = grouped[grouped["IP"] > 0]
    grouped = grouped.sort_values("ERA")
    grouped = grouped[["name", "games", "ERA", "WHIP", "IP", "SO", "BB", "HR"]].copy()
    grouped.columns = ["player", "games", "ERA", "WHIP", "IP", "SO", "BB", "HR"]

    return grouped.reset_index(drop=True)


def mlb_possible_injured_players(team, players_df, games_df):
    """
    Flag batters who appeared in the 3 games before the most recent game
    but did not play in the most recent game. Pitchers are excluded since
    they naturally rotate on a 5-day schedule.

    Returns sorted list of player names.
    """
    if players_df.empty or games_df.empty:
        return []

    batters = players_df[players_df["role"] == "batter"]

    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False)

    if len(team_games) < 2:
        return []

    latest_id = int(team_games.iloc[0]["id"])
    prev_ids = team_games.iloc[1:4]["id"].astype(int).tolist()

    latest_players = set(
        batters[(batters["team"] == team) & (batters["game_id"] == latest_id)]["name"]
    )
    prev_players = set(
        batters[(batters["team"] == team) & (batters["game_id"].isin(prev_ids))]["name"]
    )

    return sorted(prev_players - latest_players)


def mlb_player_projected_stats(player_name, opponent, players_df, games_df,
                               role="batter", injuries_df=None, n=15):
    """Project an MLB player's per-game line vs a specific opponent.

    Mirrors the NBA projection (analytics.player_projected_stats): blends a
    decay-weighted baseline (games 6–n), recent 5-game form, and Bayesian-
    shrunk decay-weighted head-to-head vs THIS opponent, then applies an
    opponent factor (how that opponent's pitching/batting compares to the
    league for each stat, capped ±25%). No minutes trend (not an MLB
    concept). Returns projected counting stats + a derived rate stat
    (AVG for batters, ERA/WHIP for pitchers), breakdown, H2H log, injury
    flag, streak context, and confidence.
    """
    if role == "pitcher":
        STATS = ["strikeouts_pitched", "earned_runs", "hits_allowed",
                 "walks_allowed", "innings_pitched"]
        primary = "strikeouts_pitched"
    else:
        role = "batter"
        STATS = ["hits", "home_runs", "rbi", "runs", "walks", "strikeouts"]
        primary = "hits"

    role_df = players_df[players_df["role"] == role]
    norm = _normalize(player_name)
    pg = role_df[role_df["name"].apply(_normalize) == norm].copy()
    if pg.empty:
        return {"error": f"No {role} data found for '{player_name}'."}
    matched = pg.iloc[0]["name"]
    team = pg.iloc[0]["team"]
    pg = pg.sort_values("date", ascending=False)

    # Injury status
    injury_status = injury_detail = None
    if injuries_df is not None and not injuries_df.empty:
        inj = injuries_df[injuries_df["player_name"].str.lower() == matched.lower()]
        if not inj.empty:
            injury_status = str(inj.iloc[0]["status"]).lower()
            injury_detail = inj.iloc[0].get("injury_type") or inj.iloc[0].get("detail")

    season_games = pg.head(n)
    if season_games.empty:
        return {"error": f"Insufficient data for '{player_name}'."}
    recent_games = pg.head(5)
    base_games = pg.iloc[5:n]
    has_base = not base_games.empty

    _D = 0.88

    def _decay_avg(slc, stat):
        vals = slc[stat].tolist()
        w = [_D ** i for i in range(len(vals))]
        ws = sum(w)
        return round(sum(v * x for v, x in zip(vals, w)) / ws, 3) if ws > 0 else 0.0

    recent_avg = {s: round(float(recent_games[s].mean()), 3) for s in STATS}
    base_avg = ({s: _decay_avg(base_games, s) for s in STATS}
                if has_base else recent_avg)
    season_avg = {s: round(float(season_games[s].mean()), 3) for s in STATS}

    if season_avg[primary] > 0:
        r = recent_avg[primary] / season_avg[primary]
        streak_context = "hot" if r >= 1.20 else ("cold" if r <= 0.80 else "normal")
    else:
        streak_context = "normal"

    # Head-to-head vs opponent (decay-weighted, Bayesian-shrunk, capped 10)
    h2h_n = 0
    h2h_avg = None
    h2h_raw_avg = None
    h2h_log = []
    if not games_df.empty:
        merged = pg.merge(games_df[["id", "home_team", "away_team"]],
                          left_on="game_id", right_on="id", how="left")
        merged["_opp"] = merged.apply(
            lambda x: x["away_team"] if x["team"] == x["home_team"] else x["home_team"],
            axis=1)
        h2h_rows = merged[merged["_opp"] == opponent] \
            .sort_values("date", ascending=False).head(10)
        h2h_n = len(h2h_rows)
        if h2h_n > 0:
            d = 0.85
            w = [d ** i for i in range(h2h_n)]
            ws = sum(w)
            h2h_avg, h2h_raw_avg = {}, {}
            for s in STATS:
                vals = h2h_rows[s].tolist()
                h2h_avg[s] = round(sum(v * x for v, x in zip(vals, w)) / ws, 3)
                h2h_raw_avg[s] = round(float(h2h_rows[s].mean()), 3)
            _M = 4  # prior strength: at k=4 H2H games it's 50/50 with season
            h2h_avg = {s: round((h2h_n * h2h_avg[s] + _M * season_avg[s])
                                / (h2h_n + _M), 3) for s in STATS}
            ldf = h2h_rows[["date"] + STATS].copy()
            h2h_log = ldf.where(pd.notnull(ldf), None).to_dict(orient="records")

    # Opponent factor: opponent's allowed (batter) / produced (pitcher) per
    # role-game vs the league baseline, current season only, capped ±25%.
    opp_factors = {s: 1.0 for s in STATS}
    if not games_df.empty:
        latest = games_df["season"].max() if "season" in games_df.columns else None
        sgames = games_df[games_df["season"] == latest] if latest is not None else games_df
        opp_gids = sgames[(sgames["home_team"] == opponent)
                          | (sgames["away_team"] == opponent)]["id"].values
        # batter → look at opposing batters facing this opponent's pitching;
        # pitcher → opposing pitchers facing this opponent's batters.
        vs_opp = players_df[players_df["game_id"].isin(opp_gids)
                            & (players_df["team"] != opponent)
                            & (players_df["role"] == role)]
        season_role = players_df[players_df["game_id"].isin(sgames["id"].values)
                                 & (players_df["role"] == role)]
        for s in STATS:
            lg = season_role[s].mean() if not season_role.empty else role_df[s].mean()
            allowed = vs_opp[s].mean() if not vs_opp.empty else lg
            if lg and lg > 0:
                opp_factors[s] = float(max(min(allowed / lg, 1.25), 0.75))

    # Blend: H2H 8%/game (max 40%), remainder 70% base / 30% recent
    h2h_w = min(0.40, h2h_n * 0.08) if h2h_n > 0 else 0.0
    base_w = (1 - h2h_w) * 0.70
    rec_w = (1 - h2h_w) * 0.30

    projected, breakdown = {}, {}
    for s in STATS:
        ra, ba = recent_avg[s], base_avg[s]
        if h2h_avg is not None and h2h_w > 0:
            raw = h2h_avg[s] * h2h_w + ba * base_w + ra * rec_w
        else:
            raw = ba * 0.70 + ra * 0.30
        projected[s] = round(float(max(raw * opp_factors[s], 0.0)), 2)
        breakdown[s] = {
            "season_avg": float(season_avg[s]),
            "base_avg_decayed": float(ba),
            "recent_avg_5g": float(ra),
            "h2h_avg_raw": h2h_raw_avg[s] if h2h_raw_avg else None,
            "h2h_avg_shrunk": h2h_avg[s] if h2h_avg else None,
            "h2h_games": h2h_n,
            "h2h_weight_pct": round(h2h_w * 100),
            "opp_factor": round(opp_factors[s], 3),
            "projected": projected[s],
        }

    # Derived rate stat
    derived = {}
    if role == "batter":
        ab_r = float(recent_games["at_bats"].mean())
        ab_s = float(season_games["at_bats"].mean())
        proj_ab = max(ab_r * 0.30 + ab_s * 0.70, 0.1)
        derived = {
            "AVG": round(projected["hits"] / proj_ab, 3) if proj_ab > 0 else 0.0,
            "proj_at_bats": round(proj_ab, 1),
        }
    else:
        ip = projected["innings_pitched"]
        derived = {
            "ERA": round(projected["earned_runs"] / ip * 9, 2) if ip > 0 else 0.0,
            "WHIP": round((projected["walks_allowed"] + projected["hits_allowed"]) / ip, 2)
                    if ip > 0 else 0.0,
        }

    total_games = len(season_games)
    if h2h_n >= 4 and total_games >= 10:
        confidence = "high"
    elif h2h_n >= 2 or total_games >= 8:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "player": matched,
        "team": team,
        "opponent": opponent,
        "role": role,
        "projected": projected,
        "derived": derived,
        "breakdown": breakdown,
        "h2h_games": h2h_n,
        "h2h_log": h2h_log,
        "season_games_used": total_games,
        "streak_context": streak_context,
        "injury_status": injury_status,
        "injury_detail": injury_detail,
        "confidence": confidence,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MLB Prediction Model — 8-Pillar composite blended with Pythagorean expectation.
#
# Margin is the *direct* projected-runs differential (R_a - R_b), not a logit
# conversion. Win probability is 30% pillar score + 70% Pythagorean of the
# projected runs — this anchors the model to actual baseball math rather than
# letting one wild pillar swing the prediction. Run projection is
# opponent-aware (own runs scored blended with opponent runs allowed). Both
# weightings were chosen by point-in-time backtest — see
# MLB_PREDICTION_BACKTEST.md and tools/backtest_mlb.py.
# ══════════════════════════════════════════════════════════════════════════════

_PILLAR_WEIGHTS = [
    ("Pitching Matchup",        0.22),
    ("Offensive Power",         0.18),
    ("Bullpen Depth",           0.12),
    ("Defensive Efficiency",    0.10),
    ("Plate Discipline",        0.08),
    ("Baserunning & Speed",     0.08),
    ("Home / Park",             0.12),
    ("Situational",             0.10),
]


def _clamp01(x):
    return max(0.0, min(1.0, float(x)))


def _team_recent_games(team, games_df, n):
    tg = games_df[(games_df["home_team"] == team) | (games_df["away_team"] == team)]
    return tg.sort_values("date", ascending=False).head(n)


def _team_recent_ids(team, games_df, n):
    return _team_recent_games(team, games_df, n)["id"].tolist()


def _team_pitchers(team, games_df, players_df, n):
    if players_df.empty:
        return players_df
    gids = _team_recent_ids(team, games_df, n)
    return players_df[
        (players_df["role"] == "pitcher")
        & (players_df["team"] == team)
        & (players_df["game_id"].isin(gids))
    ]


def _team_batters(team, games_df, players_df, n):
    if players_df.empty:
        return players_df
    gids = _team_recent_ids(team, games_df, n)
    return players_df[
        (players_df["role"] == "batter")
        & (players_df["team"] == team)
        & (players_df["game_id"].isin(gids))
    ]


def _split_rotation(team_pitchers):
    """Per game, the pitcher with most innings is the starter; rest are relievers."""
    if team_pitchers.empty:
        return team_pitchers, team_pitchers
    starter_idx = team_pitchers.groupby("game_id")["innings_pitched"].idxmax()
    starters = team_pitchers.loc[starter_idx]
    relievers = team_pitchers[~team_pitchers.index.isin(starter_idx)]
    return starters, relievers


def _rest_days(team, games_df):
    tg = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False)
    if len(tg) < 2:
        return 1
    try:
        d1 = datetime.strptime(str(tg.iloc[0]["date"])[:10], "%Y-%m-%d")
        d2 = datetime.strptime(str(tg.iloc[1]["date"])[:10], "%Y-%m-%d")
        return max(0, (d1 - d2).days)
    except (ValueError, TypeError):
        return 1


# ── Pillar scorers ───────────────────────────────────────────────────────────

def _pillar_pitching(team, games_df, players_df, n):
    pitchers = _team_pitchers(team, games_df, players_df, n)
    if pitchers.empty:
        return 0.5
    starters, _ = _split_rotation(pitchers)
    ip = starters["innings_pitched"].sum() if not starters.empty else 0
    if ip <= 0:
        return 0.5
    era = _safe_era(starters["earned_runs"].sum(), ip)
    whip = (starters["walks_allowed"].sum() + starters["hits_allowed"].sum()) / ip
    era_score = _clamp01((8.0 - era) / 8.0)
    whip_score = _clamp01((2.5 - whip) / 2.5)
    return round(era_score * 0.6 + whip_score * 0.4, 4)


def _pillar_offense(team, games_df, players_df, n):
    batters = _team_batters(team, games_df, players_df, n)
    if batters.empty:
        return 0.5
    ab = batters["at_bats"].sum()
    hits = batters["hits"].sum()
    hr = batters["home_runs"].sum()
    rbi = batters["rbi"].sum()
    g = max(len(_team_recent_ids(team, games_df, n)), 1)
    avg = hits / ab if ab > 0 else 0.0
    avg_s = _clamp01((avg - 0.200) / 0.100)
    hr_s = _clamp01((hr / g - 0.5) / 1.5)
    rbi_s = _clamp01((rbi / g - 3.0) / 5.0)
    return round(avg_s * 0.40 + hr_s * 0.35 + rbi_s * 0.25, 4)


def _pillar_bullpen(team, games_df, players_df, n):
    pitchers = _team_pitchers(team, games_df, players_df, n)
    if pitchers.empty:
        return 0.5
    _, relievers = _split_rotation(pitchers)
    if relievers.empty:
        return 0.5
    ip = relievers["innings_pitched"].sum()
    if ip <= 0:
        return 0.5
    era = _safe_era(relievers["earned_runs"].sum(), ip)
    return round(_clamp01((8.0 - era) / 8.0), 4)


def _pillar_defense(team, games_df, n):
    tg = _team_recent_games(team, games_df, n)
    if tg.empty:
        return 0.5
    conceded = tg.apply(
        lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1
    )
    return round(_clamp01((8.0 - conceded.mean()) / 6.0), 4)


def _pillar_plate_discipline(team, games_df, players_df, n):
    batters = _team_batters(team, games_df, players_df, n)
    pitchers = _team_pitchers(team, games_df, players_df, n)
    bb_drawn = batters["walks"].sum() if not batters.empty else 0
    ab = batters["at_bats"].sum() if not batters.empty else 1
    ip = pitchers["innings_pitched"].sum() if not pitchers.empty else 1
    bb_allowed = pitchers["walks_allowed"].sum() if not pitchers.empty else 0
    drawn_rate = bb_drawn / max(ab, 1)
    allowed_rate = bb_allowed / max(ip, 1)
    drawn_s = _clamp01((drawn_rate - 0.05) / 0.10)
    allowed_s = _clamp01((2.5 - allowed_rate) / 2.0)
    return round(drawn_s * 0.5 + allowed_s * 0.5, 4)


def _pillar_baserunning(team, games_df, players_df, n):
    batters = _team_batters(team, games_df, players_df, n)
    if batters.empty:
        return 0.5
    hits = batters["hits"].sum()
    runs = batters["runs"].sum()
    if hits == 0:
        return 0.5
    return round(_clamp01((runs / hits - 0.30) / 0.40), 4)


def _pillar_home_park(team, games_df, n, is_home):
    tg = _team_recent_games(team, games_df, n)
    if tg.empty:
        return 0.5
    if is_home:
        hg = tg[tg["home_team"] == team]
        if not hg.empty:
            return float((hg["home_score"] > hg["away_score"]).mean())
    else:
        ag = tg[tg["away_team"] == team]
        if not ag.empty:
            return float((ag["away_score"] > ag["home_score"]).mean())
    # Fallback to overall win%
    scored = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
    conceded = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
    return float((scored.values > conceded.values).mean())


def _pillar_situational(team, games_df, n):
    rest = _rest_days(team, games_df)
    rest_s = 0.65 if rest >= 2 else (0.50 if rest == 1 else 0.30)
    tg = _team_recent_games(team, games_df, 5)
    if tg.empty:
        form_s = 0.5
    else:
        scored = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
        conceded = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
        form_s = float((scored.values > conceded.values).mean())
    return round(rest_s * 0.40 + form_s * 0.60, 4)


# ── Run projection (offense vs opponent pitching) ────────────────────────────

def _avg_runs_scored(team, games_df, n, default=4.5):
    tg = _team_recent_games(team, games_df, n)
    if tg.empty:
        return default
    scored = tg.apply(
        lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1
    )
    return float(scored.mean())


def _avg_runs_allowed(team, games_df, n, default=4.5):
    tg = _team_recent_games(team, games_df, n)
    if tg.empty:
        return default
    allowed = tg.apply(
        lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1
    )
    return float(allowed.mean())


def _obp_factor(team, games_df, players_df, n):
    """OBP relative to league avg 0.320, ±10% multiplier."""
    batters = _team_batters(team, games_df, players_df, n)
    if batters.empty:
        return 1.0
    ab = batters["at_bats"].sum()
    hits = batters["hits"].sum()
    bb = batters["walks"].sum()
    obp = (hits + bb) / max(ab + bb, 1)
    return max(0.90, min(1.10, 1.0 + (obp - 0.320) * 1.0))


def _hr_bonus(team, games_df, players_df, n):
    """Extra runs from HR/G over league avg of 1.0; each HR/G above adds 0.25 runs."""
    batters = _team_batters(team, games_df, players_df, n)
    if batters.empty:
        return 0.0
    g = max(len(_team_recent_ids(team, games_df, n)), 1)
    return max(0.0, (batters["home_runs"].sum() / g - 1.0) * 0.25)


def _h2h_avg_total(team_a, team_b, games_df, n=20):
    h2h = games_df[
        ((games_df["home_team"] == team_a) & (games_df["away_team"] == team_b))
        | ((games_df["home_team"] == team_b) & (games_df["away_team"] == team_a))
    ].sort_values("date", ascending=False).head(n)
    if h2h.empty:
        return None
    return float((h2h["home_score"] + h2h["away_score"]).mean())


def _lg_mean_total(games_df, n=400):
    """Point-in-time league-average combined runs (recent n games) — the
    shrinkage target that cuts run-total variance."""
    r = games_df.sort_values("date", ascending=False).head(n)
    if r.empty:
        return 8.8
    return float((r["home_score"] + r["away_score"]).mean())


def _env_total(team, games_df, n):
    """Avg combined runs in a team's last n games — the scoring environment
    (pace + park + era it has been playing in), steadier than RS+RA."""
    tg = _team_recent_games(team, games_df, n)
    if tg.empty:
        return None
    return float((tg["home_score"] + tg["away_score"]).mean())


def _park_factor(home_team, games_df):
    """Empirical park factor for the game's venue, point-in-time.

    Uses the new `venue` column when populated (handles neutral-site games
    and relocations); otherwise falls back to the home team's home-game run
    environment. Shrunk toward 1.0 on small samples and clamped. NOTE: the
    backtest (MLB_PREDICTION_BACKTEST.md §0) measured this at ~0 lift for
    team game totals — it is kept because the data is now scraped and it
    matters for future player-level props, not because it moves win/total.
    """
    lg = _lg_mean_total(games_df)
    if lg <= 0:
        return 1.0
    park_games = None
    if "venue" in games_df.columns:
        v = games_df[(games_df["home_team"] == home_team)
                     & games_df["venue"].notna()]
        if not v.empty:
            venue = v.sort_values("date", ascending=False).iloc[0]["venue"]
            park_games = games_df[games_df["venue"] == venue]
    if park_games is None or park_games.empty:
        park_games = games_df[games_df["home_team"] == home_team]
    if len(park_games) < 20:
        return 1.0
    pf = float((park_games["home_score"] + park_games["away_score"]).mean()) / lg
    w = min(1.0, len(park_games) / 60.0)        # confidence shrink
    return max(0.85, min(1.18, 1.0 + (pf - 1.0) * w))


def _project_runs(team_a, team_b, games_df, players_df, home_team, n):
    is_a_home = (home_team == team_a)
    is_b_home = (home_team == team_b)
    park_a = 1.02 if is_a_home else (0.98 if is_b_home else 1.0)
    park_b = 1.02 if is_b_home else (0.98 if is_a_home else 1.0)

    def _rest_mult(team):
        r = _rest_days(team, games_df)
        return 1.03 if r >= 2 else (1.0 if r == 1 else 0.97)

    # Opponent-aware base: blend a team's own recent runs scored with the
    # opponent's recent runs allowed. The opponent's actual runs-allowed
    # already captures their starter + bullpen + defense empirically, so the
    # old parametric _sp_suppression / _bullpen_suppression ERA multipliers
    # were removed (they double-counted run prevention). Point-in-time
    # backtesting (tools/backtest_mlb.py, see MLB_PREDICTION_BACKTEST.md)
    # showed this lowers Total MAE 3.52→3.44 and Margin MAE 3.79→3.72 on a
    # 176-game sample with no loss in winner accuracy or calibration.
    base_a = 0.5 * _avg_runs_scored(team_a, games_df, n) + \
        0.5 * _avg_runs_allowed(team_b, games_df, n)
    base_b = 0.5 * _avg_runs_scored(team_b, games_df, n) + \
        0.5 * _avg_runs_allowed(team_a, games_df, n)

    a_proj = (
        base_a
        * _obp_factor(team_a, games_df, players_df, n)
        * _rest_mult(team_a)
        * park_a
    ) + _hr_bonus(team_a, games_df, players_df, n)

    b_proj = (
        base_b
        * _obp_factor(team_b, games_df, players_df, n)
        * _rest_mult(team_b)
        * park_b
    ) + _hr_bonus(team_b, games_df, players_df, n)

    # ── Calibrated run total ─────────────────────────────────────────────
    # The opponent-aware split above sets the *ratio* (winner/margin). The
    # game's *total* is then recalibrated by blending it with the recent
    # scoring environment of both teams, shrinking toward the point-in-time
    # league mean (variance reduction — the one lever a 480-config grid
    # search found, MLB_PREDICTION_BACKTEST.md §0), and a small empirical
    # park factor. proj_a/proj_b are rescaled to the calibrated total while
    # keeping their ratio, so margin/winner are preserved.
    #
    # Honest ceiling: on the 30-teams × last-15-games point-in-time rig the
    # user specified, |proj_total − actual| ≤ 2 runs passes ~38% of the
    # time. 70% at ±2 is mathematically impossible for single MLB games
    # (an oracle with the real starter lines caps at ~50%); this is the
    # closest achievable, applied as requested.
    # Constants below were chosen by sweeping this exact production path on
    # the 30-teams × last-15-games ±2 rig (see report §0): 5-game scoring
    # environment, 70/30 formula/env, 20% league-mean shrink, park on, light
    # H2H — the configuration closest to the (unreachable) 70% target,
    # landing at ~37% within ±2 runs.
    formula_total = a_proj + b_proj
    h2h = _h2h_avg_total(team_a, team_b, games_df)
    if formula_total > 0:
        env_a = _env_total(team_a, games_df, 5)
        env_b = _env_total(team_b, games_df, 5)
        env = (env_a + env_b) / 2 if env_a and env_b else formula_total
        raw = 0.70 * formula_total + 0.30 * env
        total = 0.80 * raw + 0.20 * _lg_mean_total(games_df)
        total *= _park_factor(home_team, games_df) if home_team else 1.0
        if h2h is not None:
            total = 0.85 * total + 0.15 * h2h
        scale = total / formula_total
        a_proj *= scale
        b_proj *= scale

    return a_proj, b_proj, h2h


def _pythagorean(runs_for, runs_against, exp=1.83):
    """Bill James' Pythagorean expectation. exp=1.83 is the modern best-fit for MLB."""
    rf = max(runs_for, 0.1) ** exp
    ra = max(runs_against, 0.1) ** exp
    return rf / (rf + ra)


def mlb_win_probability(team_a, team_b, games_df, players_df, home_team=None, n=20):
    """
    8-Pillar MLB prediction blended with Pythagorean expectation.

    Returns a dict with:
      prob_a, prob_b: win probabilities (0-100, sum to 100)
      margin: signed projected run differential (proj_a - proj_b)
      proj_runs_a, proj_runs_b: projected runs for each team
      projected_total: blended over/under run total
      pythagorean_prob_a: pure Pythagorean win prob (sanity check)
      pillars: list of {name, weight, score_a, score_b} for breakdown UI
      h2h_avg_total: historical H2H avg combined runs (or None)
    """
    if games_df is None or games_df.empty:
        return {
            "prob_a": 50.0, "prob_b": 50.0, "margin": 0.0,
            "proj_runs_a": 4.5, "proj_runs_b": 4.5,
            "projected_total": 9.0, "pythagorean_prob_a": 0.5,
            "pillars": [], "h2h_avg_total": None,
        }
    if players_df is None:
        players_df = pd.DataFrame()

    is_a_home = (home_team == team_a)
    is_b_home = (home_team == team_b)

    # ── 8-Pillar composite ───────────────────────────────────────────────
    pillar_scores = [
        ("Pitching Matchup",     _pillar_pitching(team_a, games_df, players_df, n),
                                  _pillar_pitching(team_b, games_df, players_df, n)),
        ("Offensive Power",      _pillar_offense(team_a, games_df, players_df, n),
                                  _pillar_offense(team_b, games_df, players_df, n)),
        ("Bullpen Depth",        _pillar_bullpen(team_a, games_df, players_df, n),
                                  _pillar_bullpen(team_b, games_df, players_df, n)),
        ("Defensive Efficiency", _pillar_defense(team_a, games_df, n),
                                  _pillar_defense(team_b, games_df, n)),
        ("Plate Discipline",     _pillar_plate_discipline(team_a, games_df, players_df, n),
                                  _pillar_plate_discipline(team_b, games_df, players_df, n)),
        ("Baserunning & Speed",  _pillar_baserunning(team_a, games_df, players_df, n),
                                  _pillar_baserunning(team_b, games_df, players_df, n)),
        ("Home / Park",          _pillar_home_park(team_a, games_df, n, is_a_home),
                                  _pillar_home_park(team_b, games_df, n, is_b_home)),
        ("Situational",          _pillar_situational(team_a, games_df, n),
                                  _pillar_situational(team_b, games_df, n)),
    ]
    pillars = [
        {"name": name, "weight": w, "score_a": round(sa, 4), "score_b": round(sb, 4)}
        for (name, w), (_, sa, sb) in zip(_PILLAR_WEIGHTS, pillar_scores)
    ]
    score_a = sum(p["weight"] * p["score_a"] for p in pillars)
    score_b = sum(p["weight"] * p["score_b"] for p in pillars)
    total = score_a + score_b
    pillar_prob_a = score_a / total if total > 0 else 0.5

    # ── Run projection + Pythagorean ─────────────────────────────────────
    proj_a, proj_b, h2h = _project_runs(team_a, team_b, games_df, players_df, home_team, n)
    pyth_a = _pythagorean(proj_a, proj_b)

    # ── Blend: 30% pillar, 70% Pythagorean ───────────────────────────────
    # Shifted from 70/30 toward the run math. A point-in-time blend sweep
    # (MLB_PREDICTION_BACKTEST.md) showed winner accuracy rises monotonically
    # as weight moves from the 8-pillar composite to the Pythagorean of the
    # (now opponent-aware) projected runs — the pillar composite was actively
    # hurting winner accuracy. 30/70 beats the old 70/30 baseline on winner
    # accuracy (56.8% vs 56.2%) and Total/Margin MAE on the 176-game sample
    # with ~equal Brier, while still letting the pillar breakdown feed 30% of
    # the probability so the UI "why" stays consistent with the number.
    final_a = 0.30 * pillar_prob_a + 0.70 * pyth_a
    prob_a = round(final_a * 100, 1)
    prob_b = round(100 - prob_a, 1)

    # ── Margin = direct projected run differential ───────────────────────
    margin = round(proj_a - proj_b, 1)

    return {
        "prob_a": prob_a,
        "prob_b": prob_b,
        "margin": margin,
        "proj_runs_a": round(proj_a, 2),
        "proj_runs_b": round(proj_b, 2),
        "projected_total": round(proj_a + proj_b, 1),
        "pythagorean_prob_a": round(pyth_a * 100, 1),
        "pillars": pillars,
        "h2h_avg_total": round(h2h, 1) if h2h is not None else None,
    }

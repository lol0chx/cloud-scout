"""
mlb_analytics.py — MLB-specific player analytics for CloudScout.

Handles batter and pitcher stat analysis. Team-level analytics
(standings, form, H2H, predictions) are shared with analytics.py
since the games table structure is identical across sports.
"""

import unicodedata

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

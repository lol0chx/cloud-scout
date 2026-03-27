"""
analytics.py — Statistical analysis functions for CloudScout.

Pure DataFrame operations — no API calls. Each function takes a pandas
DataFrame (loaded from the database) and computes stats like averages,
head-to-head records, rolling form, and player performance rankings.

All functions accept a league parameter (default "NBA") to support
future multi-sport expansion.
"""

import unicodedata

import pandas as pd


def _normalize(name):
    """
    Strip accents and diacritics from a string so that e.g.
    "Dončić" matches "Doncic". Converts to lowercase for comparison.
    """
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def last_n_avg(team, n, df):
    """
    Calculate the average points scored and conceded over the last N games
    for a given team. Useful for gauging recent offensive and defensive form.

    Args:
        team: team name to analyze
        n: number of recent games to include
        df: games DataFrame with columns: date, home_team, away_team,
            home_score, away_score

    Returns:
        pandas DataFrame with one row: team, games, avg_scored, avg_conceded

    Raises:
        ValueError: if the team is not found in the data or n < 1
    """
    if n < 1:
        raise ValueError("n must be at least 1.")

    # Filter for games involving this team on either side
    team_games = df[(df["home_team"] == team) | (df["away_team"] == team)].copy()

    if team_games.empty:
        raise ValueError(f"No data found for team '{team}'.")

    # Sort by date descending and take the most recent N games
    team_games = team_games.sort_values("date", ascending=False).head(n)

    # Calculate points scored and conceded depending on home/away status
    team_games["scored"] = team_games.apply(
        lambda row: row["home_score"] if row["home_team"] == team else row["away_score"],
        axis=1,
    )
    team_games["conceded"] = team_games.apply(
        lambda row: row["away_score"] if row["home_team"] == team else row["home_score"],
        axis=1,
    )

    result = pd.DataFrame([{
        "team": team,
        "games": len(team_games),
        "avg_scored": round(team_games["scored"].mean(), 1),
        "avg_conceded": round(team_games["conceded"].mean(), 1),
    }])

    return result


def head_to_head(team_a, team_b, n, df):
    """
    Analyze the last N head-to-head meetings between two teams.
    Returns a game-by-game breakdown with scores and the winner of each game.

    Args:
        team_a: first team name
        team_b: second team name
        n: number of recent meetings to include
        df: games DataFrame

    Returns:
        pandas DataFrame with per-game results (date, team_a_score,
        team_b_score, winner) or empty DataFrame if no meetings found
    """
    if n < 1:
        raise ValueError("n must be at least 1.")

    # Find games where these two teams played each other
    h2h_games = df[
        ((df["home_team"] == team_a) & (df["away_team"] == team_b))
        | ((df["home_team"] == team_b) & (df["away_team"] == team_a))
    ].copy()

    if h2h_games.empty:
        print(f"No head-to-head data found between {team_a} and {team_b}.")
        return pd.DataFrame()

    # Sort by date descending and take the last N meetings
    h2h_games = h2h_games.sort_values("date", ascending=False).head(n)

    # Map scores to the correct team regardless of home/away
    h2h_games["team_a_score"] = h2h_games.apply(
        lambda row: row["home_score"] if row["home_team"] == team_a else row["away_score"],
        axis=1,
    )
    h2h_games["team_b_score"] = h2h_games.apply(
        lambda row: row["home_score"] if row["home_team"] == team_b else row["away_score"],
        axis=1,
    )

    # Determine the winner of each game
    h2h_games["winner"] = h2h_games.apply(
        lambda row: team_a if row["team_a_score"] > row["team_b_score"] else team_b,
        axis=1,
    )

    # Build a clean result table
    result = h2h_games[["date", "team_a_score", "team_b_score", "winner"]].copy()
    result.columns = ["date", f"{team_a}_score", f"{team_b}_score", "winner"]

    # Print a quick summary of wins
    a_wins = (result["winner"] == team_a).sum()
    b_wins = (result["winner"] == team_b).sum()
    print(f"\nHead-to-Head Summary (last {len(result)} games):")
    print(f"  {team_a}: {a_wins} wins | {team_b}: {b_wins} wins")

    return result


def rolling_form(team, window, df):
    """
    Calculate a rolling average of points scored over a sliding window
    for a team. Helps visualize offensive streaks and slumps.

    Args:
        team: team name to analyze
        window: size of the rolling window (number of games)
        df: games DataFrame

    Returns:
        pandas DataFrame with columns: date, opponent, scored, rolling_avg
    """
    if window < 1:
        raise ValueError("Window size must be at least 1.")

    # Filter and sort games chronologically for rolling calculation
    team_games = df[(df["home_team"] == team) | (df["away_team"] == team)].copy()

    if team_games.empty:
        raise ValueError(f"No data found for team '{team}'.")

    team_games = team_games.sort_values("date", ascending=True)

    # Determine opponent and points scored for each game
    team_games["location"] = team_games.apply(
        lambda row: "Home" if row["home_team"] == team else "Away", axis=1
    )
    team_games["opponent"] = team_games.apply(
        lambda row: row["away_team"] if row["home_team"] == team else row["home_team"],
        axis=1,
    )
    team_games["scored"] = team_games.apply(
        lambda row: row["home_score"] if row["home_team"] == team else row["away_score"],
        axis=1,
    )
    team_games["conceded"] = team_games.apply(
        lambda row: row["away_score"] if row["home_team"] == team else row["home_score"],
        axis=1,
    )
    team_games["result"] = team_games.apply(
        lambda row: "W" if row["scored"] > row["conceded"] else "L", axis=1
    )
    team_games["margin"] = team_games["scored"] - team_games["conceded"]

    # Apply the rolling average — min_periods=1 so early games still show a value
    team_games["rolling_avg"] = (
        team_games["scored"].rolling(window=window, min_periods=1).mean().round(1)
    )

    return team_games[["date", "location", "opponent", "result", "scored", "conceded", "margin", "rolling_avg"]]


def player_avg(player_name, n, df):
    """
    Calculate average stats (points, assists, rebounds, steals, blocks)
    for a player over their last N games.

    Args:
        player_name: player name to search for (case-insensitive partial match)
        n: number of recent games to include
        df: players DataFrame

    Returns:
        pandas DataFrame with one row of averaged stats

    Raises:
        ValueError: if the player is not found in the data
    """
    if n < 1:
        raise ValueError("n must be at least 1.")

    # Match player name, ignoring accents and case
    # (e.g., "Luka Doncic" matches "Luka Dončić")
    normalized_input = _normalize(player_name)
    player_games = df[df["name"].apply(_normalize) == normalized_input].copy()

    if player_games.empty:
        raise ValueError(f"No data found for player '{player_name}'.")

    matched_name = player_games.iloc[0]["name"]

    # Sort by date descending and take the last N games
    player_games = player_games.sort_values("date", ascending=False).head(n)

    stat_cols = ["points", "assists", "rebounds", "steals", "blocks"]
    averages = player_games[stat_cols].mean().round(1)

    result = pd.DataFrame([{
        "player": matched_name,
        "games": len(player_games),
        **averages.to_dict(),
    }])

    return result


def player_vs_team(player_name, opponent, n, df, games_df=None):
    """
    Calculate a player's average stats when playing against a specific
    opponent over the last N matchups. Requires joining player stats
    with game data to determine the opponent.

    Args:
        player_name: player name (case-insensitive partial match)
        opponent: opponent team name
        n: number of recent matchups to include
        df: players DataFrame
        games_df: games DataFrame (needed to determine opponents).
                  If None, returns empty DataFrame with a message.

    Returns:
        pandas DataFrame with one row of averaged stats
    """
    if games_df is None or games_df.empty:
        print("Games data required for player-vs-team analysis.")
        return pd.DataFrame()

    # Match player name, ignoring accents and case
    normalized_input = _normalize(player_name)
    player_games = df[df["name"].apply(_normalize) == normalized_input].copy()

    if player_games.empty:
        print(f"No data found for player '{player_name}'.")
        return pd.DataFrame()

    matched_name = player_games.iloc[0]["name"]

    # Join with games data to get opponent info for each game
    merged = player_games.merge(
        games_df[["id", "home_team", "away_team"]],
        left_on="game_id",
        right_on="id",
        how="left",
    )

    # Determine the opponent for each game based on the player's team
    merged["opponent"] = merged.apply(
        lambda row: row["away_team"] if row["team"] == row["home_team"] else row["home_team"],
        axis=1,
    )

    # Filter for games against the specified opponent
    vs_games = merged[merged["opponent"] == opponent].copy()

    if vs_games.empty:
        print(f"No data found for {matched_name} vs {opponent}.")
        return pd.DataFrame()

    # Sort by date and take the last N games
    vs_games = vs_games.sort_values("date", ascending=False).head(n)

    stat_cols = ["points", "assists", "rebounds", "steals", "blocks"]
    averages = vs_games[stat_cols].mean().round(1)

    result = pd.DataFrame([{
        "player": matched_name,
        "opponent": opponent,
        "games": len(vs_games),
        **averages.to_dict(),
    }])

    return result


def home_away_stats(team, df):
    """
    Calculate home and away performance stats for a team across all games.

    Returns a dict with avg points scored/conceded and win % at home and away.
    """
    team_games = df[(df["home_team"] == team) | (df["away_team"] == team)].copy()

    if team_games.empty:
        return None

    home_games = team_games[team_games["home_team"] == team].copy()
    away_games = team_games[team_games["away_team"] == team].copy()

    def stats(g, is_home):
        if g.empty:
            return {"games": 0, "avg_scored": 0, "avg_conceded": 0, "win_pct": 0}
        scored = g["home_score"] if is_home else g["away_score"]
        conceded = g["away_score"] if is_home else g["home_score"]
        wins = (scored.values > conceded.values).sum()
        return {
            "games": len(g),
            "avg_scored": round(scored.mean(), 1),
            "avg_conceded": round(conceded.mean(), 1),
            "win_pct": round(wins / len(g) * 100, 1),
        }

    return {
        "home": stats(home_games, True),
        "away": stats(away_games, False),
    }


def win_streak(team, df):
    """Return the current win or loss streak for a team as (count, 'W' or 'L')."""
    team_games = df[(df["home_team"] == team) | (df["away_team"] == team)]
    if team_games.empty:
        return 0, "W"
    team_games = team_games.sort_values("date", ascending=False)
    streak_type = None
    streak_count = 0
    for _, row in team_games.iterrows():
        is_home = row["home_team"] == team
        scored = row["home_score"] if is_home else row["away_score"]
        conceded = row["away_score"] if is_home else row["home_score"]
        result = "W" if scored > conceded else "L"
        if streak_type is None:
            streak_type = result
            streak_count = 1
        elif result == streak_type:
            streak_count += 1
        else:
            break
    return streak_count, streak_type


def season_standings(df):
    """Compute W/L record and key stats for all teams currently in the database."""
    teams = sorted(set(df["home_team"].tolist() + df["away_team"].tolist()))
    rows = []
    for team in teams:
        team_games = df[(df["home_team"] == team) | (df["away_team"] == team)]
        if team_games.empty:
            continue
        scored = team_games.apply(
            lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1
        )
        conceded = team_games.apply(
            lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1
        )
        wins = int((scored.values > conceded.values).sum())
        losses = len(team_games) - wins
        streak_count, streak_type = win_streak(team, df)
        rows.append({
            "Team": team,
            "W": wins,
            "L": losses,
            "GP": len(team_games),
            "Win%": round(wins / len(team_games) * 100, 1),
            "Avg Pts": round(scored.mean(), 1),
            "Avg Allowed": round(conceded.mean(), 1),
            "Net Rtg": round(scored.mean() - conceded.mean(), 1),
            "Streak": f"{streak_type}{streak_count}",
        })
    return pd.DataFrame(rows).sort_values("Win%", ascending=False).reset_index(drop=True)


def win_probability(team_a, team_b, df, home_team=None):
    """
    Estimate win probability using overall win%, H2H record, and home/away splits.
    Weights: overall 35%, H2H 30%, home/away 35%.
    Returns (prob_a, prob_b, predicted_margin) where margin is from team_a's perspective.
    """
    def _win_pct(team):
        tg = df[(df["home_team"] == team) | (df["away_team"] == team)]
        if tg.empty:
            return 0.5
        s = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
        c = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
        return (s.values > c.values).mean()

    def _home_win_pct(team):
        hg = df[df["home_team"] == team]
        if hg.empty:
            return _win_pct(team)
        return (hg["home_score"] > hg["away_score"]).mean()

    def _away_win_pct(team):
        ag = df[df["away_team"] == team]
        if ag.empty:
            return _win_pct(team)
        return (ag["away_score"] > ag["home_score"]).mean()

    def _avg_margin(team):
        tg = df[(df["home_team"] == team) | (df["away_team"] == team)]
        if tg.empty:
            return 0
        s = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
        c = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
        return (s - c).mean()

    h2h = df[
        ((df["home_team"] == team_a) & (df["away_team"] == team_b)) |
        ((df["home_team"] == team_b) & (df["away_team"] == team_a))
    ]
    if not h2h.empty:
        a_s = h2h.apply(lambda r: r["home_score"] if r["home_team"] == team_a else r["away_score"], axis=1)
        b_s = h2h.apply(lambda r: r["home_score"] if r["home_team"] == team_b else r["away_score"], axis=1)
        h2h_pct_a = (a_s.values > b_s.values).mean()
    else:
        h2h_pct_a = 0.5

    wp_a = _win_pct(team_a)
    wp_b = _win_pct(team_b)

    if home_team == team_a:
        ha_a = _home_win_pct(team_a)
        ha_b = _away_win_pct(team_b)
    elif home_team == team_b:
        ha_a = _away_win_pct(team_a)
        ha_b = _home_win_pct(team_b)
    else:
        ha_a, ha_b = wp_a, wp_b

    score_a = wp_a * 0.35 + h2h_pct_a * 0.30 + ha_a * 0.35
    score_b = wp_b * 0.35 + (1 - h2h_pct_a) * 0.30 + ha_b * 0.35
    total = score_a + score_b
    prob_a = round(score_a / total * 100, 1) if total > 0 else 50.0
    prob_b = round(100 - prob_a, 1)
    margin = round(_avg_margin(team_a) - _avg_margin(team_b), 1)
    return prob_a, prob_b, margin


def possible_injured_players(team, players_df, games_df):
    """
    Flag players who appeared in the 3 games before the most recent game
    but did not play in the most recent game. Returns sorted list of names.
    """
    if players_df.empty or games_df.empty:
        return []
    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False)
    if len(team_games) < 2:
        return []
    latest_id = int(team_games.iloc[0]["id"])
    prev_ids = team_games.iloc[1:4]["id"].astype(int).tolist()
    latest_players = set(
        players_df[(players_df["team"] == team) & (players_df["game_id"] == latest_id)]["name"]
    )
    prev_players = set(
        players_df[(players_df["team"] == team) & (players_df["game_id"].isin(prev_ids))]["name"]
    )
    return sorted(prev_players - latest_players)


def top_performers(team, n, df, games_df=None):
    """
    Rank players on a team by their average points over the last N team games.
    Shows points, assists, and rebounds averages for each player.

    Args:
        team: team name to analyze
        n: number of recent team games to consider
        df: players DataFrame
        games_df: games DataFrame (needed to find the team's recent game IDs).
                  If None, uses all available player data for the team.

    Returns:
        pandas DataFrame ranked by average points (descending)
    """
    if games_df is not None and not games_df.empty:
        # Get the last N game IDs for this team
        team_game_ids = games_df[
            (games_df["home_team"] == team) | (games_df["away_team"] == team)
        ].sort_values("date", ascending=False).head(n)["id"].tolist()

        # Filter player stats to only those games
        team_players = df[
            (df["team"] == team) & (df["game_id"].isin(team_game_ids))
        ].copy()
    else:
        # Fallback: use all available data for the team
        team_players = df[df["team"] == team].copy()

    if team_players.empty:
        print(f"No player data found for {team}.")
        return pd.DataFrame()

    # Group by player and calculate averages
    stat_cols = ["points", "assists", "rebounds", "steals"]
    grouped = team_players.groupby("name")[stat_cols].mean().round(1)

    # Add the number of games each player appeared in
    grouped["games"] = team_players.groupby("name").size()

    # Sort by average points (highest first) and reset index for clean output
    grouped = grouped.sort_values("points", ascending=False).reset_index()
    grouped.columns = ["player", "avg_points", "avg_assists", "avg_rebounds", "avg_steals", "games"]

    return grouped

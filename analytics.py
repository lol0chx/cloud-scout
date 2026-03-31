"""
analytics.py — Statistical analysis functions for CloudScout.

Pure DataFrame operations — no API calls. Each function takes a pandas
DataFrame (loaded from the database) and computes stats like averages,
head-to-head records, rolling form, and player performance rankings.

All functions accept a league parameter (default "NBA") to support
future multi-sport expansion.
"""

import math
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


def win_probability(team_a, team_b, df, home_team=None, pts_per_logit=6.0):
    """
    Estimate win probability using overall win%, H2H record, and home/away splits.
    Weights: overall 35%, H2H 30%, home/away 35%.
    Returns (prob_a, prob_b, predicted_margin) where margin is from team_a's perspective.

    pts_per_logit scales the log-odds to a point spread.
    NBA ≈ 6.0 (13 pts ≈ 90% win), MLB ≈ 3.5 (3 runs ≈ 70% win).
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
    # Logit conversion: clamp probabilities to avoid log(0), then scale
    p = max(min(prob_a / 100, 0.99), 0.01)
    margin = round(math.log(p / (1 - p)) * pts_per_logit, 1)
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


# ══════════════════════════════════════════════════════════════════════════════
# Advanced Analytics — Pace, Ratings, Shooting, Rest, Situational
# ══════════════════════════════════════════════════════════════════════════════

def estimate_possessions(team_score, opp_score, team_players_df=None):
    """
    Estimate possessions using the simplified Dean Oliver formula:
        Poss ≈ FGA - OREB + TOV + (0.44 * FTA)
    Falls back to score-based estimation when player data is unavailable.

    Args:
        team_score: int, team's total points scored
        opp_score: int, opponent's total points scored (used for fallback)
        team_players_df: optional DataFrame of player rows for this team/game

    Returns:
        float: estimated possessions
    """
    if team_players_df is not None and not team_players_df.empty:
        fga  = team_players_df["field_goals_attempted"].sum()
        oreb = team_players_df["off_rebounds"].sum()
        tov  = team_players_df["turnovers"].sum()
        fta  = team_players_df["free_throws_attempted"].sum()
        if fga > 0:
            return fga - oreb + tov + 0.44 * fta
    # Fallback: rough estimate based on average NBA scoring efficiency (~1.1 pts/poss)
    return (team_score + opp_score) / 2.2


def team_pace(team, games_df, players_df, n=10):
    """
    Calculate a team's pace (estimated possessions per 48 minutes) over
    the last N games. Uses player-level shot/turnover data when available.

    Args:
        team: team name string
        games_df: DataFrame of games
        players_df: DataFrame of player stats
        n: number of recent games to use (default 10)

    Returns:
        dict with keys: pace, possessions_per_game, games_used
        or None if insufficient data
    """
    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False).head(n)

    if team_games.empty:
        return None

    poss_list = []
    for _, g in team_games.iterrows():
        is_home = g["home_team"] == team
        team_score = g["home_score"] if is_home else g["away_score"]
        opp_score  = g["away_score"] if is_home else g["home_score"]

        # Use player-level data from this game if available
        game_players = players_df[
            (players_df["game_id"] == g["id"]) & (players_df["team"] == team)
        ] if players_df is not None and not players_df.empty else pd.DataFrame()

        poss = estimate_possessions(team_score, opp_score, game_players if not game_players.empty else None)
        poss_list.append(poss)

    avg_poss = round(sum(poss_list) / len(poss_list), 1)
    # Pace = possessions per 48 min. NBA games are 48 min.
    # Possessions here are already per-game so pace ≈ possessions_per_game
    return {
        "possessions_per_game": avg_poss,
        "pace": avg_poss,  # for a full 48-min game, poss = pace
        "games_used": len(poss_list),
    }


def h2h_pace(team_a, team_b, games_df, players_df, n=10):
    """
    Calculate average game pace specifically when team_a and team_b
    have played each other.

    Returns:
        dict with avg_possessions and games_used, or None
    """
    h2h = games_df[
        ((games_df["home_team"] == team_a) & (games_df["away_team"] == team_b)) |
        ((games_df["home_team"] == team_b) & (games_df["away_team"] == team_a))
    ].sort_values("date", ascending=False).head(n)

    if h2h.empty:
        return None

    poss_list = []
    for _, g in h2h.iterrows():
        gp_a = players_df[(players_df["game_id"] == g["id"]) & (players_df["team"] == team_a)] \
               if players_df is not None and not players_df.empty else pd.DataFrame()
        poss = estimate_possessions(g["home_score"], g["away_score"], gp_a if not gp_a.empty else None)
        poss_list.append(poss)

    return {
        "avg_possessions": round(sum(poss_list) / len(poss_list), 1),
        "games_used": len(poss_list),
    }


def offensive_rating(team, games_df, players_df, n=10):
    """
    Offensive rating = (points scored / estimated possessions) * 100.
    A higher number means the team scores more per 100 possessions.

    Args:
        team: team name string
        games_df: games DataFrame
        players_df: players DataFrame
        n: last N games to use

    Returns:
        float: offensive rating, or None if no data
    """
    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False).head(n)

    if team_games.empty:
        return None

    total_pts, total_poss = 0, 0
    for _, g in team_games.iterrows():
        is_home = g["home_team"] == team
        pts = g["home_score"] if is_home else g["away_score"]
        opp = g["away_score"] if is_home else g["home_score"]
        gp = players_df[
            (players_df["game_id"] == g["id"]) & (players_df["team"] == team)
        ] if players_df is not None and not players_df.empty else pd.DataFrame()
        poss = estimate_possessions(pts, opp, gp if not gp.empty else None)
        total_pts  += pts
        total_poss += poss

    if total_poss == 0:
        return None
    return round((total_pts / total_poss) * 100, 1)


def defensive_rating(team, games_df, players_df, n=10):
    """
    Defensive rating = (opponent points / estimated opponent possessions) * 100.
    Lower is better — fewer points allowed per 100 possessions.

    Returns:
        float: defensive rating, or None if no data
    """
    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False).head(n)

    if team_games.empty:
        return None

    total_opp_pts, total_poss = 0, 0
    for _, g in team_games.iterrows():
        is_home = g["home_team"] == team
        pts     = g["home_score"] if is_home else g["away_score"]
        opp_pts = g["away_score"] if is_home else g["home_score"]
        poss = estimate_possessions(pts, opp_pts)
        total_opp_pts += opp_pts
        total_poss    += poss

    if total_poss == 0:
        return None
    return round((total_opp_pts / total_poss) * 100, 1)


def team_shooting_stats(team, players_df, games_df, n=10):
    """
    Aggregate shooting stats for a team over the last N games:
    - eFG% = (FGM + 0.5 * 3PM) / FGA  — weights 3s appropriately
    - TS%  = PTS / (2 * (FGA + 0.44 * FTA))  — true shooting efficiency
    - 3PAr = 3PA / FGA  — share of shots that are 3-pointers
    - FTr  = FTA / FGA  — free throw attempt rate
    - TOV% = TOV / (FGA + 0.44 * FTA + TOV)

    Args:
        team: team name string
        players_df: player stats DataFrame
        games_df: games DataFrame (used to find game IDs)
        n: last N games

    Returns:
        dict of shooting metrics, or None if no data
    """
    # Get game IDs from the last N team games
    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False).head(n)

    if team_games.empty or players_df is None or players_df.empty:
        return None

    tp = players_df[
        (players_df["game_id"].isin(team_games["id"])) & (players_df["team"] == team)
    ]

    if tp.empty:
        return None

    fgm  = tp["field_goals_made"].sum()
    fga  = tp["field_goals_attempted"].sum()
    tpm  = tp["three_pointers_made"].sum()
    tpa  = tp["three_pointers_attempted"].sum()
    ftm  = tp["free_throws_made"].sum()
    fta  = tp["free_throws_attempted"].sum()
    pts  = tp["points"].sum()
    tov  = tp["turnovers"].sum()
    oreb = tp["off_rebounds"].sum()
    dreb = tp["def_rebounds"].sum()
    tot_reb = oreb + dreb

    efg  = round((fgm + 0.5 * tpm) / fga * 100, 1)       if fga  > 0 else None
    ts   = round(pts / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + fta) > 0 else None
    tpar = round(tpa / fga * 100, 1)                       if fga  > 0 else None
    ftr  = round(fta / fga * 100, 1)                       if fga  > 0 else None
    tovr = round(tov / (fga + 0.44 * fta + tov) * 100, 1) if (fga + fta + tov) > 0 else None
    oreb_pct = round(oreb / (oreb + dreb) * 100, 1)        if (oreb + dreb) > 0 else None

    return {
        "efg_pct":      efg,
        "ts_pct":       ts,
        "three_par":    tpar,
        "ft_rate":      ftr,
        "tov_rate":     tovr,
        "oreb_pct":     oreb_pct,
        "dreb_pct":     round(dreb / (oreb + dreb) * 100, 1) if (oreb + dreb) > 0 else None,
        "fg_pct":       round(fgm / fga * 100, 1) if fga > 0 else None,
        "three_pct":    round(tpm / tpa * 100, 1) if tpa > 0 else None,
        "ft_pct":       round(ftm / fta * 100, 1) if fta > 0 else None,
        "games":        len(team_games),
    }


def rest_days(team, games_df):
    """
    Calculate the number of rest days a team has had since their last game,
    and whether they are on a back-to-back (0 rest days).

    Args:
        team: team name string
        games_df: games DataFrame sorted by date

    Returns:
        dict with:
            - rest_days: int (days since last game, 0 = back-to-back)
            - back_to_back: bool
            - last_game_date: str (YYYY-MM-DD)
        or None if no previous game found
    """
    import datetime

    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False)

    if len(team_games) < 2:
        return None

    # Most recent game
    last_date_str = team_games.iloc[0]["date"]
    prev_date_str = team_games.iloc[1]["date"]

    try:
        last_date = datetime.date.fromisoformat(last_date_str)
        prev_date = datetime.date.fromisoformat(prev_date_str)
        days = (last_date - prev_date).days - 1  # days between games (0 = b2b)
    except Exception:
        return None

    return {
        "rest_days":      max(days, 0),
        "back_to_back":   days <= 0,
        "last_game_date": last_date_str,
    }


def advanced_team_stats(team, games_df, players_df, n=10):
    """
    Convenience function that bundles all advanced metrics for a team
    into a single dict: pace, offensive/defensive rating, shooting stats,
    and rest info.

    Args:
        team: team name string
        games_df: games DataFrame
        players_df: players DataFrame (must have extended schema columns)
        n: number of recent games for rolling stats

    Returns:
        dict combining pace, ratings, shooting, and rest data
    """
    result = {"team": team, "games": n}

    pace_data   = team_pace(team, games_df, players_df, n)
    off_rtg     = offensive_rating(team, games_df, players_df, n)
    def_rtg     = defensive_rating(team, games_df, players_df, n)
    shooting    = team_shooting_stats(team, players_df, games_df, n)
    rest        = rest_days(team, games_df)

    if pace_data:
        result.update(pace_data)
    if off_rtg is not None:
        result["off_rating"] = off_rtg
    if def_rtg is not None:
        result["def_rating"] = def_rtg
        result["net_rating_advanced"] = round(off_rtg - def_rtg, 1) if off_rtg else None
    if shooting:
        result.update(shooting)
    if rest:
        result.update(rest)

    return result


def opponent_efg(team, players_df, games_df, n=10):
    """
    Compute the effective field goal percentage that opponents shoot
    against this team over the last N games (defensive eFG% allowed).
    """
    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False).head(n)

    if team_games.empty:
        return None

    opp_players = players_df[
        (players_df["game_id"].isin(team_games["id"])) & (players_df["team"] != team)
    ]

    fgm = opp_players["field_goals_made"].dropna().sum()
    fga = opp_players["field_goals_attempted"].dropna().sum()
    tpm = opp_players["three_pointers_made"].dropna().sum()

    if fga > 0:
        return round((fgm + 0.5 * tpm) / fga * 100, 1)
    return None


def league_averages(players_df):
    """
    Compute league-wide averages for eFG%, TOV rate, and FT rate
    from all player data in the database.
    """
    fgm = players_df["field_goals_made"].dropna().sum()
    fga = players_df["field_goals_attempted"].dropna().sum()
    tpm = players_df["three_pointers_made"].dropna().sum()
    fta = players_df["free_throws_attempted"].dropna().sum()
    tov = players_df["turnovers"].dropna().sum()

    efg = round((fgm + 0.5 * tpm) / fga * 100, 1) if fga > 0 else 52.0
    tov_rate = round(tov / (fga + 0.44 * fta + tov) * 100, 1) if (fga + fta + tov) > 0 else 13.0
    ft_rate = round(fta / fga * 100, 1) if fga > 0 else 25.0

    return {"efg_pct": efg, "tov_rate": tov_rate, "ft_rate": ft_rate}


def projected_total(team_a, team_b, games_df, players_df, home_team=None, n=10,
                     injuries_df=None):
    """
    Project the over/under game total using an 8-step model:
    1. Pace-based base total (possessions x combined offensive ratings)
    2. Shooting adjustment (matchup eFG% vs league average)
    3. Turnover adjustment (combined TOV% deviation)
    4. Free throw adjustment (combined FT rate deviation)
    5. Rest adjustment (back-to-back penalties, extra rest bonuses)
    6. Home court adjustment (+1.5 if not neutral)
    7. Recent form adjustment (last N ORtg vs season ORtg)
    8. Injury adjustment (missing key players reduce projected total)

    Returns a detailed dict with every intermediate value for each step.
    """
    steps = {}

    # Gather core metrics
    pace_a_data = team_pace(team_a, games_df, players_df, n)
    pace_b_data = team_pace(team_b, games_df, players_df, n)
    ortg_a = offensive_rating(team_a, games_df, players_df, n)
    ortg_b = offensive_rating(team_b, games_df, players_df, n)
    drtg_a = defensive_rating(team_a, games_df, players_df, n)
    drtg_b = defensive_rating(team_b, games_df, players_df, n)

    pace_a_val = pace_a_data.get("pace") or pace_a_data.get("pace_per_48") if pace_a_data else None
    pace_b_val = pace_b_data.get("pace") or pace_b_data.get("pace_per_48") if pace_b_data else None

    if not all([pace_a_val, pace_b_val, ortg_a, ortg_b, drtg_a, drtg_b]):
        return {"error": "Not enough game data — scrape more games first."}

    # ── Step 1: Base Total ──
    expected_poss = (pace_a_val + pace_b_val) / 2
    exp_ortg_a = (ortg_a + drtg_b) / 2
    exp_ortg_b = (ortg_b + drtg_a) / 2
    base_total = expected_poss * (exp_ortg_a + exp_ortg_b) / 100

    steps["step_1_base"] = {
        "label": "Base Total",
        "pace_a": pace_a_val, "pace_b": pace_b_val,
        "expected_possessions": round(expected_poss, 1),
        "ortg_a": ortg_a, "drtg_a": drtg_a,
        "ortg_b": ortg_b, "drtg_b": drtg_b,
        "exp_ortg_a": round(exp_ortg_a, 1),
        "exp_ortg_b": round(exp_ortg_b, 1),
        "base_total": round(base_total, 1),
    }

    # ── Step 2: Shooting Adjustment ──
    shooting_a = team_shooting_stats(team_a, players_df, games_df, n)
    shooting_b = team_shooting_stats(team_b, players_df, games_df, n)
    opp_efg_a_val = opponent_efg(team_a, players_df, games_df, n)
    opp_efg_b_val = opponent_efg(team_b, players_df, games_df, n)
    lg = league_averages(players_df)

    efg_a = shooting_a.get("efg_pct") if shooting_a else None
    efg_b = shooting_b.get("efg_pct") if shooting_b else None

    shooting_adj = 0.0
    if all(v is not None for v in [efg_a, efg_b, opp_efg_a_val, opp_efg_b_val]):
        matchup_efg_a = (efg_a + opp_efg_b_val) / 2
        matchup_efg_b = (efg_b + opp_efg_a_val) / 2
        efg_dev = ((matchup_efg_a - lg["efg_pct"]) + (matchup_efg_b - lg["efg_pct"])) / 2
        shooting_adj = round(efg_dev * 2.0, 1)
        steps["step_2_shooting"] = {
            "label": "Shooting Adjustment",
            "efg_a": efg_a, "efg_b": efg_b,
            "opp_efg_a": opp_efg_a_val, "opp_efg_b": opp_efg_b_val,
            "league_avg_efg": lg["efg_pct"],
            "matchup_efg_a": round(matchup_efg_a, 1),
            "matchup_efg_b": round(matchup_efg_b, 1),
            "efg_deviation": round(efg_dev, 2),
            "adjustment": shooting_adj,
        }
    else:
        steps["step_2_shooting"] = {"label": "Shooting Adjustment", "skipped": True,
                                     "reason": "Missing eFG% data — re-scrape teams", "adjustment": 0.0}

    # ── Step 3: Turnover Adjustment ──
    tov_a = shooting_a.get("tov_rate") if shooting_a else None
    tov_b = shooting_b.get("tov_rate") if shooting_b else None

    tov_adj = 0.0
    if tov_a is not None and tov_b is not None:
        tov_adj = round(((tov_a - lg["tov_rate"]) + (tov_b - lg["tov_rate"])) * -0.4, 1)
        steps["step_3_turnovers"] = {
            "label": "Turnover Adjustment",
            "tov_rate_a": tov_a, "tov_rate_b": tov_b,
            "league_avg_tov": lg["tov_rate"],
            "adjustment": tov_adj,
        }
    else:
        steps["step_3_turnovers"] = {"label": "Turnover Adjustment", "skipped": True, "adjustment": 0.0}

    # ── Step 4: Free Throw Adjustment ──
    # FT rate stored as percentage (e.g. 25.0), so scale the 8.0 multiplier
    # to 0.08 to keep the adjustment in points
    ftr_a = shooting_a.get("ft_rate") if shooting_a else None
    ftr_b = shooting_b.get("ft_rate") if shooting_b else None

    ft_adj = 0.0
    if ftr_a is not None and ftr_b is not None:
        ft_adj = round(((ftr_a - lg["ft_rate"]) + (ftr_b - lg["ft_rate"])) * 0.08, 1)
        steps["step_4_free_throws"] = {
            "label": "Free Throw Adjustment",
            "ft_rate_a": ftr_a, "ft_rate_b": ftr_b,
            "league_avg_ft_rate": lg["ft_rate"],
            "adjustment": ft_adj,
        }
    else:
        steps["step_4_free_throws"] = {"label": "Free Throw Adjustment", "skipped": True, "adjustment": 0.0}

    # ── Step 5: Rest Adjustment ──
    rest_a_info = rest_days(team_a, games_df)
    rest_b_info = rest_days(team_b, games_df)

    def _rest_value(info):
        if not info:
            return 0.0
        d = info["rest_days"]
        if d <= 0:
            return -2.0   # back-to-back
        if d == 1:
            return 0.0    # normal rest
        if d == 2:
            return 0.5
        return 1.0        # 3+ days rest

    rv_a = _rest_value(rest_a_info)
    rv_b = _rest_value(rest_b_info)
    rest_adj = rv_a + rv_b

    steps["step_5_rest"] = {
        "label": "Rest Adjustment",
        "rest_days_a": rest_a_info["rest_days"] if rest_a_info else None,
        "rest_days_b": rest_b_info["rest_days"] if rest_b_info else None,
        "b2b_a": rest_a_info.get("back_to_back") if rest_a_info else None,
        "b2b_b": rest_b_info.get("back_to_back") if rest_b_info else None,
        "rest_value_a": rv_a,
        "rest_value_b": rv_b,
        "adjustment": rest_adj,
    }

    # ── Step 6: Home Court ──
    home_adj = 1.5 if home_team else 0.0
    steps["step_6_home_court"] = {
        "label": "Home Court",
        "home_team": home_team or "Neutral",
        "adjustment": home_adj,
    }

    # ── Step 7: Recent Form ──
    season_ortg_a = offensive_rating(team_a, games_df, players_df, n=82)
    season_ortg_b = offensive_rating(team_b, games_df, players_df, n=82)

    form_adj = 0.0
    if season_ortg_a and season_ortg_b:
        form_delta_a = ortg_a - season_ortg_a
        form_delta_b = ortg_b - season_ortg_b
        form_adj = round((form_delta_a + form_delta_b) * 0.25, 1)
        steps["step_7_form"] = {
            "label": "Recent Form",
            "recent_ortg_a": ortg_a, "season_ortg_a": season_ortg_a,
            "form_delta_a": round(form_delta_a, 1),
            "recent_ortg_b": ortg_b, "season_ortg_b": season_ortg_b,
            "form_delta_b": round(form_delta_b, 1),
            "adjustment": form_adj,
        }
    else:
        steps["step_7_form"] = {"label": "Recent Form", "skipped": True, "adjustment": 0.0}

    # ��─ Step 8: Injury Adjustment ──
    #
    # Empirically-calibrated model matching real-world O/U line movements:
    #   Star out   → line moves ~4-6 pts   (25+ PPG, top-2 on team)
    #   Starter out → line moves ~2-3 pts   (12+ PPG, top-5 / 28+ min)
    #   Bench out  → line moves ~0.5-1 pt   (everyone else)
    #
    # Key insight: when a star is out, the team scores less BUT also defends
    # worse (shorter rotations, less cohesion). These partially cancel in the
    # game total, so the net O/U effect is much smaller than the raw PPG lost.
    #
    # Factors:
    #   - Player tier determines a PPG-to-O/U conversion factor
    #   - Playmaking bonus: high-assist players create non-replaceable offense
    #   - Minutes weighting: 35-min players harder to replace than 15-min
    #   - Status probability: Out=100%, Doubtful=75%, Day-to-Day/GTD=50%
    #   - Per-team cap at 10 pts, total cap at 15 pts

    _MISS_PROB = {
        "out": 1.0,
        "suspension": 1.0,
        "doubtful": 0.75,
        "day-to-day": 0.50,
        "questionable": 0.50,
        "probable": 0.10,
    }

    # PPG-to-O/U conversion factors calibrated to real Vegas line moves:
    #   Star:    25 PPG * 0.18 = 4.5 pts  (realistic for a max player out)
    #   Starter: 15 PPG * 0.15 = 2.25 pts (solid starter missing)
    #   Bench:    7 PPG * 0.10 = 0.7 pts  (depth loss, barely moves line)
    _TIER_FACTOR = {"Star": 0.18, "Starter": 0.15, "Bench": 0.10}

    injury_adj = 0.0
    step_8 = {"label": "Injury Adjustment"}
    team_injury_details = {}

    if injuries_df is not None and not injuries_df.empty:
        for team_label, team_name in [("a", team_a), ("b", team_b)]:
            team_inj = injuries_df[
                (injuries_df["team"] == team_name)
                & (injuries_df["status"].str.lower().isin(_MISS_PROB.keys()))
            ]
            if team_inj.empty:
                team_injury_details[team_label] = []
                continue

            # Build the full team roster averages to rank players
            team_roster = players_df[players_df["team"] == team_name]
            if team_roster.empty:
                team_injury_details[team_label] = []
                continue

            roster_avg = (
                team_roster.groupby("name")
                .agg(
                    ppg=("points", "mean"),
                    apg=("assists", "mean"),
                    mpg=("minutes", "first"),
                    games=("game_id", "nunique"),
                )
                .sort_values("ppg", ascending=False)
                .reset_index()
            )
            roster_avg["rank"] = range(1, len(roster_avg) + 1)

            def _parse_minutes(m):
                if not m or m == "0":
                    return 0.0
                try:
                    if ":" in str(m):
                        parts = str(m).split(":")
                        return float(parts[0]) + float(parts[1]) / 60.0
                    return float(m)
                except (ValueError, TypeError):
                    return 0.0

            roster_avg["min_float"] = roster_avg["mpg"].apply(_parse_minutes)

            missing_players = []
            team_total_adj = 0.0

            for _, row in team_inj.iterrows():
                pname = row["player_name"]
                status = row["status"]
                miss_prob = _MISS_PROB.get(status.lower(), 0.0)

                # Match player to roster — exact, then accent-normalized,
                # then partial last-name match (handles "Doncic" ↔ "Dončić")
                match = roster_avg[roster_avg["name"] == pname]
                if match.empty:
                    norm_name = _normalize(pname)
                    match = roster_avg[
                        roster_avg["name"].apply(_normalize) == norm_name
                    ]
                if match.empty:
                    last_name = _normalize(pname.split()[-1])
                    match = roster_avg[
                        roster_avg["name"].apply(
                            lambda n: _normalize(n.split()[-1])
                        ) == last_name
                    ]

                if match.empty:
                    missing_players.append({
                        "name": pname, "status": status,
                        "injury": row.get("detail") or row.get("injury_type") or "—",
                        "body_part": row.get("body_part") or "��",
                        "return_date": row.get("return_date") or "Unknown",
                        "avg_ppg": 0.0, "avg_apg": 0.0, "minutes": 0.0,
                        "tier": "Unknown", "miss_prob": miss_prob,
                        "impact_pts": 0.0,
                    })
                    continue

                p = match.iloc[0]
                ppg = round(float(p["ppg"]), 1)
                apg = round(float(p["apg"]), 1)
                mins = round(float(p["min_float"]), 1)
                rank = int(p["rank"])

                # ── Tier classification ──
                # Use both scoring rank AND minutes to avoid mis-classifying
                # a starter who defers scoring (e.g. a point guard at 10 PPG
                # but 32 min is still a starter, not bench).
                if rank <= 2 and ppg >= 20:
                    tier = "Star"
                elif (rank <= 5 and ppg >= 10) or (mins >= 28 and ppg >= 8):
                    tier = "Starter"
                else:
                    tier = "Bench"

                factor = _TIER_FACTOR[tier]

                # ── Base scoring impact ──
                # PPG * tier factor gives the calibrated O/U effect
                base_impact = ppg * factor

                # ── Playmaking bonus ──
                # High-assist players create ~2 pts per assist for teammates.
                # ~20% of that creation is non-replaceable when they sit.
                playmaking_bonus = apg * 0.20

                # ── Minutes weighting ──
                # A 35-min player missing is a bigger hole to fill than a
                # 15-min player. Normalized to 1.0 at 32 min (typical starter).
                min_weight = min(max(mins / 32.0, 0.5), 1.2)

                # ── Total impact for this player ──
                raw_impact = (base_impact + playmaking_bonus) * min_weight
                impact = round(raw_impact * miss_prob, 1)

                team_total_adj += impact

                missing_players.append({
                    "name": pname, "status": status,
                    "injury": row.get("detail") or row.get("injury_type") or "—",
                    "body_part": row.get("body_part") or "—",
                    "return_date": row.get("return_date") or "Unknown",
                    "avg_ppg": ppg, "avg_apg": apg, "minutes": mins,
                    "tier": tier, "miss_prob": miss_prob,
                    "impact_pts": impact,
                })

            team_injury_details[team_label] = missing_players

            # Cap per-team at 10 pts (even 3 starters out won't move
            # the total more than 10 — the team adjusts its pace/style)
            team_total_adj = min(team_total_adj, 10.0)
            injury_adj -= team_total_adj

        # Cap combined adjustment at -15 (both teams decimated)
        injury_adj = max(injury_adj, -15.0)
        injury_adj = round(injury_adj, 1)
        step_8.update({
            "injured_out_a": team_injury_details.get("a", []),
            "injured_out_b": team_injury_details.get("b", []),
            "adjustment": injury_adj,
        })
    else:
        step_8.update({"skipped": True, "reason": "No injury data available", "adjustment": 0.0})

    steps["step_8_injuries"] = step_8

    # ── Final Projected Total ──
    projected = round(base_total + shooting_adj + tov_adj + ft_adj + rest_adj + home_adj + form_adj + injury_adj, 1)

    steps["final"] = {
        "base_total": round(base_total, 1),
        "shooting_adj": shooting_adj,
        "tov_adj": tov_adj,
        "ft_adj": ft_adj,
        "rest_adj": rest_adj,
        "home_adj": home_adj,
        "form_adj": form_adj,
        "injury_adj": injury_adj,
        "projected_total": projected,
    }

    return {
        "team_a": team_a,
        "team_b": team_b,
        "home_team": home_team,
        "n_games": n,
        "steps": steps,
        "projected_total": projected,
    }

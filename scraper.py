"""
scraper.py — NBA stats fetcher for CloudScout using nba_api.

Fetches NBA game results and player box score statistics from
stats.nba.com via the nba_api library. No API key required.
Includes rate limiting, duplicate detection, and returns results
as pandas DataFrames.
"""

import time
from datetime import datetime

import pandas as pd
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import TeamGameLog, BoxScoreTraditionalV3

from database import init_db, game_exists, insert_game, insert_players

# Configuration constants
LEAGUE = "NBA"
REQUEST_DELAY = 1.0  # seconds between API calls to respect stats.nba.com rate limits
DEFAULT_SEASON = "2025-26"  # NBA.com uses "YYYY-YY" format

# Aliases for common shorthand team names that differ from NBA.com canonical names
TEAM_ALIASES = {
    "LA Lakers": "Los Angeles Lakers",
    "LA Clippers": "LA Clippers",  # NBA.com actually uses "LA Clippers"
}


def _resolve_team(team):
    """
    Look up an NBA team by name, abbreviation, or nickname using
    nba_api's static team data. Supports common aliases like "LA Lakers".

    Args:
        team: team name string (e.g., "Los Angeles Lakers", "LAL", "Lakers", "LA Lakers")

    Returns:
        dict: team info with keys 'id', 'full_name', 'abbreviation', 'nickname', etc.

    Raises:
        ValueError: if the team name isn't recognized, with a list of valid names
    """
    # Check aliases first (e.g., "LA Lakers" -> "Los Angeles Lakers")
    lookup_name = TEAM_ALIASES.get(team, team)

    all_teams = nba_teams.get_teams()

    # Try matching by full name, abbreviation, or nickname (case-insensitive)
    for t in all_teams:
        if (lookup_name.lower() == t["full_name"].lower()
                or lookup_name.lower() == t["abbreviation"].lower()
                or lookup_name.lower() == t["nickname"].lower()):
            return t

    # No match found — show valid team names
    valid_names = "\n  ".join(sorted(t["full_name"] for t in all_teams))
    raise ValueError(
        f"Team '{team}' not found. Valid team names:\n  {valid_names}"
    )


def _tricode_to_full_name(tricode):
    """
    Convert a team tricode (e.g., "LAL") to the full team name
    (e.g., "Los Angeles Lakers") using nba_api's static data.
    Falls back to the tricode itself if no match is found.

    Args:
        tricode: 3-letter team code string

    Returns:
        str: full team name or the tricode if not found
    """
    for t in nba_teams.get_teams():
        if t["abbreviation"] == tricode:
            return t["full_name"]
    return tricode


def fetch_games(team, season=DEFAULT_SEASON, last=15):
    """
    Fetch the last N completed NBA games for a given team from stats.nba.com.
    Uses TeamGameLog to get the list of recent games, then checks the database
    to skip games we've already stored.

    Args:
        team: team display name (e.g., "Los Angeles Lakers", "LA Lakers", "LAL")
        season: season string in NBA.com format (e.g., "2025-26")
        last: number of recent games to fetch (default: 15)

    Returns:
        list of dicts with game info for games not yet in the DB,
        or empty list if no new games found
    """
    team_info = _resolve_team(team)
    conn = init_db()

    # Fetch the team's game log for the season
    time.sleep(REQUEST_DELAY)
    try:
        gamelog = TeamGameLog(
            team_id=team_info["id"],
            season=season,
            season_type_all_star="Regular Season",
        )
        df = gamelog.get_data_frames()[0]
    except Exception as e:
        print(f"Failed to fetch game log for {team}: {e}")
        conn.close()
        return []

    if df.empty:
        print(f"No games found for {team_info['full_name']} in {season}.")
        conn.close()
        return []

    # TeamGameLog returns most recent games first — take the last N
    df = df.head(last)

    pending_games = []
    for _, row in df.iterrows():
        game_id = row["Game_ID"]  # string like "0022500123"
        game_id_int = int(game_id)  # store as int in the database

        # Skip games we already have in the database
        if game_exists(conn, game_id_int):
            print(f"  Game {game_id} already in DB, skipping.")
            continue

        # Parse MATCHUP to determine home/away
        # Format: "LAL vs. BOS" (home) or "LAL @ BOS" (away)
        matchup = row["MATCHUP"]
        is_home = "vs." in matchup

        # Convert "MAR 14, 2026" to "2026-03-14" for consistent storage
        raw_date = str(row["GAME_DATE"]).strip()
        try:
            parsed_date = datetime.strptime(raw_date, "%b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            parsed_date = raw_date[:10]

        pending_games.append({
            "game_id": game_id,
            "game_id_int": game_id_int,
            "date": parsed_date,
            "is_home": is_home,
            "team_name": team_info["full_name"],
            "season": season,
        })

    conn.close()

    if not pending_games:
        print(f"No new games to save for {team_info['full_name']}.")

    return pending_games


def fetch_player_stats(game_id, game_date):
    """
    Fetch player box score stats and team scores for a single game
    using BoxScoreTraditionalV2. Returns both the player stats and
    the team-level stats (used to determine final scores).

    Args:
        game_id: NBA.com game ID string (e.g., "0022500123")
        game_date: date string (YYYY-MM-DD) for this game

    Returns:
        tuple of (players_list, team_stats_df):
            - players_list: list of dicts with player stats
            - team_stats_df: DataFrame with team-level scores
        Returns ([], empty DataFrame) on failure.
    """
    time.sleep(REQUEST_DELAY)
    try:
        box = BoxScoreTraditionalV3(game_id=game_id)
        frames = box.get_data_frames()
        player_df = frames[0]  # PlayerStats
        team_df = frames[2]    # TeamStats totals (2 rows, one per team)
    except Exception as e:
        print(f"  Failed to fetch box score for game {game_id}: {e}")
        return [], pd.DataFrame()

    if player_df.empty:
        print(f"  No player stats returned for game {game_id}.")
        return [], pd.DataFrame()

    # Map each player's V3 stats to our database schema
    # V3 uses camelCase column names: firstName, familyName, teamTricode,
    # points, assists, reboundsTotal, steals, blocks, turnovers, minutes,
    # fieldGoalsPercentage, threePointersPercentage
    players_list = []
    for _, row in player_df.iterrows():
        full_name = f"{row.get('firstName', '')} {row.get('familyName', '')}".strip()
        players_list.append({
            "name": full_name or "Unknown",
            "team": _tricode_to_full_name(row.get("teamTricode", "")),
            "date": game_date,
            "game_id": int(game_id),
            "points": _safe_int(row.get("points")),
            "assists": _safe_int(row.get("assists")),
            "rebounds": _safe_int(row.get("reboundsTotal")),
            "steals": _safe_int(row.get("steals")),
            "blocks": _safe_int(row.get("blocks")),
            "turnovers": _safe_int(row.get("turnovers")),
            "minutes": str(row.get("minutes", "0")),
            "field_goal_pct": _safe_float(row.get("fieldGoalsPercentage")),
            "three_point_pct": _safe_float(row.get("threePointersPercentage")),
        })

    return players_list, team_df


def _parse_team_scores(team_stats_df, game_info):
    """
    Extract home/away team names and scores from the BoxScoreTraditionalV2
    team stats DataFrame. Uses the game_info to determine which team
    was home and which was away.

    Args:
        team_stats_df: DataFrame with 2 rows (one per team), has
                       TEAM_ABBREVIATION and PTS columns
        game_info: dict with 'is_home' and 'team_name' keys

    Returns:
        tuple of (home_team, away_team, home_score, away_score)
    """
    # Build a list of the two teams in the game
    # V3 uses camelCase: teamTricode, points
    teams_in_game = []
    for _, row in team_stats_df.iterrows():
        teams_in_game.append({
            "full_name": _tricode_to_full_name(row["teamTricode"]),
            "pts": int(row["points"]),
        })

    # Determine which team is home and which is away
    if game_info["is_home"]:
        home = next(t for t in teams_in_game if t["full_name"] == game_info["team_name"])
        away = next(t for t in teams_in_game if t["full_name"] != game_info["team_name"])
    else:
        away = next(t for t in teams_in_game if t["full_name"] == game_info["team_name"])
        home = next(t for t in teams_in_game if t["full_name"] != game_info["team_name"])

    return home["full_name"], away["full_name"], home["pts"], away["pts"]


def _safe_int(value):
    """
    Safely convert a value to int, returning 0 if conversion fails.
    Handles None, empty strings, and non-numeric values from the API.
    """
    try:
        return int(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0


def _safe_float(value):
    """
    Safely convert a value to float, returning 0.0 if conversion fails.
    Handles None, empty strings, and non-numeric values from the API.
    """
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def scrape_team(team, last=15):
    """
    High-level scraping function: fetches the game log for a team,
    then fetches player box scores and team scores for each new game.
    Inserts everything into the database and prints progress.

    Args:
        team: team display name (e.g., "Los Angeles Lakers", "LA Lakers")
        last: number of recent games to fetch (default: 15)

    Returns:
        tuple of (games_df, players_df) — both pandas DataFrames
    """
    print(f"\nScraping games for {team}...")
    pending_games = fetch_games(team, last=last)

    if not pending_games:
        print(f"No new games found for {team}.")
        return pd.DataFrame(), pd.DataFrame()

    conn = init_db()
    all_games = []
    all_players = []

    for i, game_info in enumerate(pending_games, 1):
        print(f"  Fetching box score {i}/{len(pending_games)} (ID: {game_info['game_id']})...")

        players, team_stats_df = fetch_player_stats(game_info["game_id"], game_info["date"])

        if team_stats_df.empty:
            print(f"  Skipping game {game_info['game_id']} — no team stats available.")
            continue

        # Extract home/away teams and scores from the box score
        home_team, away_team, home_score, away_score = _parse_team_scores(
            team_stats_df, game_info
        )

        # Build and insert the game record
        game_record = {
            "id": game_info["game_id_int"],
            "date": game_info["date"],
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "league": LEAGUE,
            "season": game_info["season"],
        }

        insert_game(conn, game_record)
        all_games.append(game_record)

        # Insert player stats for this game
        if players:
            insert_players(conn, players)
            all_players.extend(players)

        print(f"  Saved: {home_team} {home_score} - {away_score} {away_team}")

    conn.close()

    games_df = pd.DataFrame(all_games) if all_games else pd.DataFrame()
    players_df = pd.DataFrame(all_players) if all_players else pd.DataFrame()

    print(f"Done! Saved {len(all_games)} games and {len(all_players)} player stat lines for {team}.")
    return games_df, players_df

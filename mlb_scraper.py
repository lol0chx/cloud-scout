"""
mlb_scraper.py — MLB stats fetcher for CloudScout using MLB-StatsAPI.

Fetches MLB game results and player box score statistics from the
MLB Stats API via the statsapi library. No API key required.
Includes rate limiting, duplicate detection, and returns results
as pandas DataFrames.
"""

import time
from datetime import datetime, timedelta

import pandas as pd
import statsapi

from database import init_db, game_exists, insert_game, insert_mlb_players

LEAGUE = "MLB"
REQUEST_DELAY = 0.5  # seconds between API calls
DEFAULT_SEASON = 2025  # last completed full MLB season


def get_all_mlb_teams():
    """
    Fetch all active MLB teams from the Stats API and return a sorted
    list of full team names.
    """
    data = statsapi.get("teams", {"sportId": 1, "activeStatus": "Y"})
    teams = data.get("teams", [])
    names = sorted(
        t["name"] for t in teams
        if t.get("sport", {}).get("id") == 1
    )
    return names


def _resolve_mlb_team(team_name):
    """
    Look up an MLB team by name using the Stats API. Returns a dict
    with at least 'id' and 'name'. Raises ValueError if not found.

    Args:
        team_name: full or partial team name (e.g. "Yankees", "New York Yankees")

    Returns:
        dict with 'id' and 'name'
    """
    results = statsapi.lookup_team(team_name)
    if not results:
        raise ValueError(
            f"Team '{team_name}' not found. "
            "Try the full name, e.g. 'New York Yankees'."
        )
    # Prefer an exact full-name match; fall back to first result
    for r in results:
        if r["name"].lower() == team_name.lower():
            return r
    return results[0]


def fetch_mlb_games(team, season=DEFAULT_SEASON, last=15):
    """
    Fetch the last N completed regular-season MLB games for a team.
    Uses the MLB Stats API schedule endpoint filtered to the season.

    Args:
        team: team name (full or partial)
        season: integer year (e.g. 2025)
        last: number of recent games to fetch

    Returns:
        list of game info dicts for games not yet in the DB,
        or empty list if no new games found
    """
    team_info = _resolve_mlb_team(team)
    conn = init_db()

    start_date = f"{season}-03-01"
    end_date = f"{season}-11-30"

    time.sleep(REQUEST_DELAY)
    try:
        schedule = statsapi.schedule(
            team=team_info["id"],
            start_date=start_date,
            end_date=end_date,
            sportId=1,
        )
    except Exception as e:
        print(f"Failed to fetch schedule for {team}: {e}")
        conn.close()
        return []

    # Filter to completed regular season games only
    completed = [
        g for g in schedule
        if g.get("status") == "Final" and g.get("game_type") == "R"
    ]
    # Sort most recent first, take last N
    completed.sort(key=lambda g: g["game_date"], reverse=True)
    completed = completed[:last]

    pending = []
    for game in completed:
        game_id = game["game_id"]

        if game_exists(conn, game_id):
            cursor = conn.cursor()
            cursor.execute(
                "SELECT home_score, away_score FROM games WHERE id = ?", (game_id,)
            )
            row = cursor.fetchone()
            if row and not (row[0] == 0 and row[1] == 0):
                print(f"  Game {game_id} already in DB, skipping.")
                continue
            # Corrupt 0-0 record — delete and re-fetch
            print(f"  Game {game_id} has 0-0 score, re-fetching...")
            cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
            cursor.execute("DELETE FROM mlb_players WHERE game_id = ?", (game_id,))
            conn.commit()

        pending.append({
            "game_id": game_id,
            "date": game["game_date"],          # YYYY-MM-DD
            "home_team": game["home_name"],
            "away_team": game["away_name"],
            "home_score": int(game.get("home_score", 0)),
            "away_score": int(game.get("away_score", 0)),
            "season": str(season),
        })

    conn.close()

    if not pending:
        print(f"No new games found for {team_info['name']}.")

    return pending


def fetch_mlb_box_score(game_id, game_date, home_team, away_team):
    """
    Fetch player batting and pitching stats for a single MLB game.
    Uses the MLB Stats API boxscore endpoint.

    Args:
        game_id: MLB Stats API game primary key (gamePk)
        game_date: date string (YYYY-MM-DD) for this game
        home_team: full home team name (for player team assignment)
        away_team: full away team name

    Returns:
        list of player stat dicts (batters and pitchers combined)
        Returns empty list on failure.
    """
    time.sleep(REQUEST_DELAY)
    try:
        box = statsapi.boxscore_data(game_id)
    except Exception as e:
        print(f"  Failed to fetch box score for game {game_id}: {e}")
        return []

    players = []
    side_team_map = {
        "home": home_team,
        "away": away_team,
    }

    for side, team_name in side_team_map.items():
        side_data = box.get(side, {})
        all_players = side_data.get("players", {})

        # Extract batters
        for pid in side_data.get("batters", []):
            pid_key = f"ID{pid}"
            if pid_key not in all_players:
                continue
            pdata = all_players[pid_key]
            name = pdata.get("person", {}).get("fullName", "Unknown")
            batting = pdata.get("stats", {}).get("batting", {})
            # Skip players with no at-bats (e.g., pinch runners only)
            if not batting or batting.get("atBats") is None:
                continue
            players.append({
                "name": name,
                "team": team_name,
                "date": game_date,
                "game_id": game_id,
                "role": "batter",
                "at_bats": _safe_int(batting.get("atBats")),
                "hits": _safe_int(batting.get("hits")),
                "runs": _safe_int(batting.get("runs")),
                "home_runs": _safe_int(batting.get("homeRuns")),
                "rbi": _safe_int(batting.get("rbi")),
                "walks": _safe_int(batting.get("baseOnBalls")),
                "strikeouts": _safe_int(batting.get("strikeOuts")),
                # pitching fields null for batters
                "innings_pitched": None,
                "hits_allowed": None,
                "earned_runs": None,
                "walks_allowed": None,
                "strikeouts_pitched": None,
                "home_runs_allowed": None,
            })

        # Extract pitchers
        for pid in side_data.get("pitchers", []):
            pid_key = f"ID{pid}"
            if pid_key not in all_players:
                continue
            pdata = all_players[pid_key]
            name = pdata.get("person", {}).get("fullName", "Unknown")
            pitching = pdata.get("stats", {}).get("pitching", {})
            if not pitching or pitching.get("inningsPitched") is None:
                continue
            players.append({
                "name": name,
                "team": team_name,
                "date": game_date,
                "game_id": game_id,
                "role": "pitcher",
                # batting fields null for pitchers
                "at_bats": None,
                "hits": None,
                "runs": None,
                "home_runs": None,
                "rbi": None,
                "walks": None,
                "strikeouts": None,
                "innings_pitched": _safe_float(pitching.get("inningsPitched")),
                "hits_allowed": _safe_int(pitching.get("hits")),
                "earned_runs": _safe_int(pitching.get("earnedRuns")),
                "walks_allowed": _safe_int(pitching.get("baseOnBalls")),
                "strikeouts_pitched": _safe_int(pitching.get("strikeOuts")),
                "home_runs_allowed": _safe_int(pitching.get("homeRuns")),
            })

    return players


def scrape_mlb_team(team, season=DEFAULT_SEASON, last=15):
    """
    High-level scraping function: fetches the game schedule for a team,
    then fetches player box scores for each new game.
    Inserts everything into the database and prints progress.

    Args:
        team: team name (full or partial)
        season: integer year (e.g. 2025)
        last: number of recent games to fetch

    Returns:
        tuple of (games_df, players_df) — both pandas DataFrames
    """
    print(f"\nScraping MLB games for {team} ({season})...")
    pending_games = fetch_mlb_games(team, season=season, last=last)

    if not pending_games:
        print(f"No new games found for {team}.")
        return pd.DataFrame(), pd.DataFrame()

    conn = init_db()
    all_games = []
    all_players = []

    for i, game_info in enumerate(pending_games, 1):
        game_id = game_info["game_id"]
        print(f"  Fetching box score {i}/{len(pending_games)} (ID: {game_id})...")

        game_record = {
            "id": game_id,
            "date": game_info["date"],
            "home_team": game_info["home_team"],
            "away_team": game_info["away_team"],
            "home_score": game_info["home_score"],
            "away_score": game_info["away_score"],
            "league": LEAGUE,
            "season": game_info["season"],
        }
        insert_game(conn, game_record)
        all_games.append(game_record)

        players = fetch_mlb_box_score(
            game_id, game_info["date"],
            game_info["home_team"], game_info["away_team"],
        )
        if players:
            insert_mlb_players(conn, players)
            all_players.extend(players)

        print(
            f"  Saved: {game_info['home_team']} {game_info['home_score']} - "
            f"{game_info['away_score']} {game_info['away_team']}"
        )

    conn.close()

    games_df = pd.DataFrame(all_games) if all_games else pd.DataFrame()
    players_df = pd.DataFrame(all_players) if all_players else pd.DataFrame()

    print(
        f"Done! Saved {len(all_games)} games and {len(all_players)} "
        f"player stat lines for {team}."
    )
    return games_df, players_df


def _safe_int(value):
    try:
        return int(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0


def _safe_float(value):
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

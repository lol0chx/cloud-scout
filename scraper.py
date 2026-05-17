"""
scraper.py — NBA stats fetcher for CloudScout using nba_api.

Fetches NBA game results and player box score statistics from
stats.nba.com via the nba_api library. No API key required.
Includes rate limiting, duplicate detection, and returns results
as pandas DataFrames.

Also fetches official injury reports from ESPN and today's
projected starters from the NBA CDN.
"""

import time
import json
from datetime import datetime

import requests
import pandas as pd
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import TeamGameLog, BoxScoreTraditionalV3

from database import (
    init_db, game_exists, insert_game, insert_players,
    game_scores, game_has_shooting, delete_game,
    clear_injuries, upsert_injuries, load_injuries,
    clear_referee_stats, upsert_referee_stats,
    clear_referee_assignments, upsert_referee_assignments,
)

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

    # Fetch the team's game log across Regular Season, Play-In, and Playoffs
    # so updates keep working through the postseason — TeamGameLog returns
    # nothing for a season_type the team isn't currently playing in.
    season_dfs = []
    for season_type in ("Regular Season", "PlayIn", "Playoffs"):
        time.sleep(REQUEST_DELAY)
        try:
            gamelog = TeamGameLog(
                team_id=team_info["id"],
                season=season,
                season_type_all_star=season_type,
            )
            part = gamelog.get_data_frames()[0]
        except Exception as e:
            print(f"Failed to fetch {season_type} game log for {team}: {e}")
            continue
        if not part.empty:
            season_dfs.append(part)

    if not season_dfs:
        print(f"No games found for {team_info['full_name']} in {season}.")
        conn.close()
        return []

    df = pd.concat(season_dfs, ignore_index=True)
    # Sort newest-first across both season types, then take the last N
    df["_parsed_date"] = pd.to_datetime(df["GAME_DATE"], format="%b %d, %Y", errors="coerce")
    df = df.sort_values("_parsed_date", ascending=False).head(last)
    df = df.drop(columns=["_parsed_date"])

    pending_games = []
    for _, row in df.iterrows():
        game_id = row["Game_ID"]  # string like "0022500123"
        game_id_int = int(game_id)  # store as int in the database

        # Skip games we already have, unless scores are 0-0 or player stats are missing
        if game_exists(conn, game_id_int):
            score_row = game_scores(conn, game_id_int)
            is_corrupt = bool(score_row and score_row[0] == 0 and score_row[1] == 0)
            has_shooting = game_has_shooting(conn, game_id_int)

            if not is_corrupt and has_shooting:
                print(f"  Game {game_id} already in DB, skipping.")
                continue

            # Stale record — delete and re-fetch
            reason = "0-0 score" if is_corrupt else "missing shooting data"
            print(f"  Game {game_id} has {reason}, re-fetching...")
            delete_game(conn, game_id_int, "players")

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

    # Map each player's V3 stats to our database schema.
    # BoxScoreTraditionalV3 camelCase fields used here:
    #   fieldGoalsMade, fieldGoalsAttempted, fieldGoalsPercentage
    #   threePointersMade, threePointersAttempted, threePointersPercentage
    #   freeThrowsMade, freeThrowsAttempted, freeThrowsPercentage
    #   reboundsOffensive, reboundsDefensive, reboundsTotal
    #   plusMinusPoints
    players_list = []
    for _, row in player_df.iterrows():
        full_name = f"{row.get('firstName', '')} {row.get('familyName', '')}".strip()
        fgm = _safe_int(row.get("fieldGoalsMade"))
        fga = _safe_int(row.get("fieldGoalsAttempted"))
        tpm = _safe_int(row.get("threePointersMade"))
        tpa = _safe_int(row.get("threePointersAttempted"))
        ftm = _safe_int(row.get("freeThrowsMade"))
        fta = _safe_int(row.get("freeThrowsAttempted"))
        players_list.append({
            "name": full_name or "Unknown",
            "team": _tricode_to_full_name(row.get("teamTricode", "")),
            "date": game_date,
            "game_id": int(game_id),
            "points":               _safe_int(row.get("points")),
            "assists":              _safe_int(row.get("assists")),
            "rebounds":             _safe_int(row.get("reboundsTotal")),
            "off_rebounds":         _safe_int(row.get("reboundsOffensive")),
            "def_rebounds":         _safe_int(row.get("reboundsDefensive")),
            "steals":               _safe_int(row.get("steals")),
            "blocks":               _safe_int(row.get("blocks")),
            "turnovers":            _safe_int(row.get("turnovers")),
            "minutes":              str(row.get("minutes", "0")),
            "field_goals_made":         fgm,
            "field_goals_attempted":    fga,
            "field_goal_pct":           _safe_float(row.get("fieldGoalsPercentage")),
            "three_pointers_made":      tpm,
            "three_pointers_attempted": tpa,
            "three_point_pct":          _safe_float(row.get("threePointersPercentage")),
            "free_throws_made":         ftm,
            "free_throws_attempted":    fta,
            "free_throw_pct":           _safe_float(row.get("freeThrowsPercentage")),
            "plus_minus":               _safe_int(row.get("plusMinusPoints")),
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


# ── ESPN Injury Report ──────────────────────────────────────────────────────

# Map ESPN team displayName → nba_api full_name for teams that differ
_ESPN_TEAM_MAP = {
    "LA Clippers": "LA Clippers",
    "Los Angeles Clippers": "LA Clippers",
}


def _espn_team_to_nba(espn_name):
    """Convert an ESPN team display name to the nba_api canonical name."""
    if espn_name in _ESPN_TEAM_MAP:
        return _ESPN_TEAM_MAP[espn_name]
    # Most ESPN names match nba_api exactly
    return espn_name


def fetch_injuries(league="NBA"):
    """
    Fetch the current official injury report from ESPN's public API.
    Returns a list of injury dicts ready for database insertion.

    Each dict contains:
        player_name, team, status, injury_type, body_part, detail,
        side, return_date, short_comment, long_comment, last_updated, league
    """
    if league == "MLB":
        url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries"
    else:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Failed to fetch {league} injury report from ESPN: {e}")
        return []

    injuries = []
    for team_block in data.get("injuries", data.get("items", [])):
        espn_team = team_block.get("displayName", "")
        team_name = _espn_team_to_nba(espn_team) if league == "NBA" else espn_team

        for entry in team_block.get("injuries", []):
            athlete = entry.get("athlete", {})
            details = entry.get("details", {})

            injuries.append({
                "player_name": athlete.get("displayName", "Unknown"),
                "team": team_name,
                "status": entry.get("status", entry.get("type", {}).get("description", "Unknown")),
                "injury_type": details.get("type"),
                "body_part": details.get("location"),
                "detail": details.get("detail"),
                "side": details.get("side"),
                "return_date": details.get("returnDate"),
                "short_comment": entry.get("shortComment"),
                "long_comment": entry.get("longComment"),
                "last_updated": entry.get("date", datetime.now().isoformat()),
                "league": league,
            })

    print(f"Fetched {len(injuries)} {league} injury entries from ESPN.")
    return injuries


def scrape_injuries(league="NBA"):
    """
    Fetch injuries from ESPN and save them to the database.
    Clears old records first so the table always reflects the current report.
    """
    injuries = fetch_injuries(league)
    if not injuries:
        return []

    conn = init_db()
    clear_injuries(conn, league)
    upsert_injuries(conn, injuries)
    conn.close()
    print(f"Saved {len(injuries)} {league} injuries to database.")
    return injuries


def live_injuries(league="NBA"):
    """
    Fetch the current ESPN injury report, persist it to the local DB,
    and return the records as a DataFrame.

    Mirrors the always-fresh behavior of `fetch_todays_games()` while
    still keeping a local copy on disk so a network blip never empties
    the feed. If the ESPN call fails or returns nothing, falls back to
    whatever is already in the DB.
    """
    fresh = fetch_injuries(league)
    conn = init_db()
    try:
        if fresh:
            clear_injuries(conn, league)
            upsert_injuries(conn, fresh)
        return load_injuries(conn, league=league)
    finally:
        conn.close()


# ── Today's Scoreboard & Projected Starters ─────────────────────────────────

NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
NBA_BOXSCORE_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"

_NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/",
    "Accept": "application/json",
}


def fetch_todays_games():
    """
    Fetch today's NBA scoreboard (scheduled, live, and completed games).
    Returns a list of dicts with game_id, home_team, away_team, status, start_time.
    """
    try:
        resp = requests.get(NBA_SCOREBOARD_URL, headers=_NBA_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Failed to fetch NBA scoreboard: {e}")
        return []

    games = []
    for g in data.get("scoreboard", {}).get("games", []):
        games.append({
            "game_id": g.get("gameId", ""),
            "home_team": g.get("homeTeam", {}).get("teamName", ""),
            "home_team_full": g.get("homeTeam", {}).get("teamCity", "") + " " + g.get("homeTeam", {}).get("teamName", ""),
            "away_team": g.get("awayTeam", {}).get("teamName", ""),
            "away_team_full": g.get("awayTeam", {}).get("teamCity", "") + " " + g.get("awayTeam", {}).get("teamName", ""),
            "status": g.get("gameStatusText", ""),
            "game_status": g.get("gameStatus", 0),  # 1=scheduled, 2=live, 3=final
        })
    return games


def fetch_starters(game_id):
    """
    Fetch confirmed starters for a specific NBA game from the NBA CDN boxscore.
    Only works for live or completed games (gameStatus >= 2).

    Returns dict with 'home' and 'away' keys, each a list of starter dicts:
        {name, position, jersey_number}
    """
    url = NBA_BOXSCORE_URL.format(game_id=game_id)
    try:
        resp = requests.get(url, headers=_NBA_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Failed to fetch boxscore for game {game_id}: {e}")
        return {"home": [], "away": []}

    game = data.get("game", {})
    result = {}
    for side in ("home", "away"):
        team_data = game.get(f"{side}Team", {})
        starters = []
        for p in team_data.get("players", []):
            if p.get("starter") == "1":
                starters.append({
                    "name": p.get("name", ""),
                    "position": p.get("position", ""),
                    "jersey_number": p.get("jerseyNum", ""),
                })
        result[side] = starters
        team_name = f"{team_data.get('teamCity', '')} {team_data.get('teamName', '')}".strip()
        result[f"{side}_team"] = team_name

    return result


# ── Referee Data ──────────────────────────────────────────────────────────────

def fetch_referee_stats():
    """
    Scrape referee season stats from NBAStuffer.
    Returns list of dicts with name, games_officiated, total_ppg, fouls_per_game, home_win_pct.
    """
    from bs4 import BeautifulSoup
    url = "https://www.nbastuffer.com/2025-2026-nba-referee-stats/"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch referee stats: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", id="tablepress-149")
    if not table:
        # fallback: try any table with enough columns
        table = soup.find("table")
    if not table:
        print("No referee stats table found")
        return []

    rows = table.find("tbody").find_all("tr") if table.find("tbody") else []
    now = datetime.now().isoformat()
    refs = []
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 10:
            continue
        try:
            refs.append({
                "name": cells[1],
                "games_officiated": int(cells[5]) if cells[5] else None,
                "home_win_pct": _safe_float(cells[6]),
                "total_ppg": _safe_float(cells[8]),
                "fouls_per_game": _safe_float(cells[9]),
                "last_updated": now,
            })
        except (ValueError, IndexError):
            continue
    return refs


def _safe_float(val):
    """Parse a float from a string, stripping % signs and commas."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return None
    try:
        return float(str(val).replace("%", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def fetch_referee_assignments():
    """
    Scrape today's referee assignments from official.nba.com.
    Returns list of dicts with game_matchup, referee_name, role, assignment_date.
    """
    from bs4 import BeautifulSoup
    url = "https://official.nba.com/referee-assignments/"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch referee assignments: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find assignment date from the page
    date_el = soup.find("div", class_="entry-meta") or soup.find("time")
    if date_el:
        date_text = date_el.get_text(strip=True)
        try:
            assignment_date = datetime.strptime(date_text, "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            assignment_date = datetime.now().strftime("%Y-%m-%d")
    else:
        assignment_date = datetime.now().strftime("%Y-%m-%d")

    # Find the NBA table (first table on the page)
    table = soup.find("table")
    if not table:
        print("No referee assignments table found")
        return []

    rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]
    assignments = []
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 4:
            continue
        matchup = cells[0].strip()
        if not matchup:
            continue
        roles = ["Crew Chief", "Referee", "Umpire"]
        for i, role in enumerate(roles):
            name = cells[i + 1].strip() if i + 1 < len(cells) else ""
            # Strip jersey number like "Kevin Scott (#24)" → "Kevin Scott"
            if "(" in name:
                name = name[:name.index("(")].strip()
            if name:
                assignments.append({
                    "game_matchup": matchup,
                    "referee_name": name,
                    "role": role,
                    "assignment_date": assignment_date,
                })
    return assignments


def scrape_referees():
    """
    Fetch referee stats and today's assignments, save to database.
    Returns (stats_count, assignments_count).
    """
    conn = init_db()

    stats = fetch_referee_stats()
    if stats:
        clear_referee_stats(conn)
        upsert_referee_stats(conn, stats)
        print(f"Saved {len(stats)} referee stat records.")

    assignments = fetch_referee_assignments()
    if assignments:
        clear_referee_assignments(conn)
        upsert_referee_assignments(conn, assignments)
        print(f"Saved {len(assignments)} referee assignments.")

    conn.close()
    return len(stats), len(assignments)

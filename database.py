"""
database.py — SQLite database setup and helper functions for CloudScout.

Handles creating the database, tables, and all CRUD operations
for games and player statistics. Uses cloudscout.db as the default
database file.
"""

import sqlite3
import pandas as pd


def init_db(db_path="cloudscout.db"):
    """
    Create the SQLite database and both tables if they don't already exist.
    Returns an open connection to the database.

    Tables created:
        - games: stores completed game results
        - players: stores individual player box score stats
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the games table — uses the API game ID as the primary key
    # so we can easily check for duplicates before inserting
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_score INTEGER NOT NULL,
            away_score INTEGER NOT NULL,
            league TEXT NOT NULL DEFAULT 'NBA',
            season TEXT NOT NULL
        )
    """)

    # Create the players table — autoincrement PK with a unique constraint
    # on (name, game_id) to prevent duplicate player entries per game
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team TEXT NOT NULL,
            date TEXT NOT NULL,
            game_id INTEGER NOT NULL,
            points INTEGER,
            assists INTEGER,
            rebounds INTEGER,
            off_rebounds INTEGER,
            def_rebounds INTEGER,
            steals INTEGER,
            blocks INTEGER,
            turnovers INTEGER,
            minutes TEXT,
            field_goals_made INTEGER,
            field_goals_attempted INTEGER,
            field_goal_pct REAL,
            three_pointers_made INTEGER,
            three_pointers_attempted INTEGER,
            three_point_pct REAL,
            free_throws_made INTEGER,
            free_throws_attempted INTEGER,
            free_throw_pct REAL,
            plus_minus INTEGER,
            FOREIGN KEY (game_id) REFERENCES games(id),
            UNIQUE (name, game_id)
        )
    """)

    # Add new columns to existing players table if upgrading from older schema
    _add_column_if_missing(cursor, "players", "off_rebounds", "INTEGER")
    _add_column_if_missing(cursor, "players", "def_rebounds", "INTEGER")
    _add_column_if_missing(cursor, "players", "field_goals_made", "INTEGER")
    _add_column_if_missing(cursor, "players", "field_goals_attempted", "INTEGER")
    _add_column_if_missing(cursor, "players", "three_pointers_made", "INTEGER")
    _add_column_if_missing(cursor, "players", "three_pointers_attempted", "INTEGER")
    _add_column_if_missing(cursor, "players", "free_throws_made", "INTEGER")
    _add_column_if_missing(cursor, "players", "free_throws_attempted", "INTEGER")
    _add_column_if_missing(cursor, "players", "free_throw_pct", "REAL")
    _add_column_if_missing(cursor, "players", "plus_minus", "INTEGER")

    # MLB players table — separate from NBA players because stats differ
    # fundamentally between batters and pitchers. role = 'batter' or 'pitcher'.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mlb_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team TEXT NOT NULL,
            date TEXT NOT NULL,
            game_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            at_bats INTEGER,
            hits INTEGER,
            runs INTEGER,
            home_runs INTEGER,
            rbi INTEGER,
            walks INTEGER,
            strikeouts INTEGER,
            innings_pitched REAL,
            hits_allowed INTEGER,
            earned_runs INTEGER,
            walks_allowed INTEGER,
            strikeouts_pitched INTEGER,
            home_runs_allowed INTEGER,
            FOREIGN KEY (game_id) REFERENCES games(id),
            UNIQUE (name, game_id, role)
        )
    """)

    # Injury reports — stores official injury data from ESPN
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS injuries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            status TEXT NOT NULL,
            injury_type TEXT,
            body_part TEXT,
            detail TEXT,
            side TEXT,
            return_date TEXT,
            short_comment TEXT,
            long_comment TEXT,
            last_updated TEXT NOT NULL,
            league TEXT NOT NULL DEFAULT 'NBA',
            UNIQUE (player_name, team, league)
        )
    """)

    # Referee season stats — scraped from NBAStuffer
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referee_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            games_officiated INTEGER,
            total_ppg REAL,
            fouls_per_game REAL,
            home_win_pct REAL,
            last_updated TEXT NOT NULL,
            UNIQUE (name)
        )
    """)

    # Referee game assignments — scraped from official.nba.com
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referee_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_matchup TEXT NOT NULL,
            referee_name TEXT NOT NULL,
            role TEXT NOT NULL,
            assignment_date TEXT NOT NULL,
            UNIQUE (game_matchup, referee_name, assignment_date)
        )
    """)

    conn.commit()
    return conn


def _add_column_if_missing(cursor, table, column, col_type):
    """Add a column to a table if it doesn't already exist (for schema migrations)."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def game_exists(conn, game_id):
    """
    Check if a game with the given API ID already exists in the database.
    Used by the scraper to skip games we've already stored and conserve
    our daily API request quota.

    Args:
        conn: SQLite connection object
        game_id: the API-provided game ID to check

    Returns:
        True if the game exists, False otherwise
    """
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM games WHERE id = ?", (game_id,))
    return cursor.fetchone() is not None


def insert_game(conn, game):
    """
    Insert a single game record into the games table.
    Uses INSERT OR IGNORE so duplicate game IDs are silently skipped.

    Args:
        conn: SQLite connection object
        game: dict with keys: id, date, home_team, away_team,
              home_score, away_score, league, season
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO games
            (id, date, home_team, away_team, home_score, away_score, league, season)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        game["id"],
        game["date"],
        game["home_team"],
        game["away_team"],
        game["home_score"],
        game["away_score"],
        game["league"],
        game["season"],
    ))
    conn.commit()


def insert_players(conn, players):
    """
    Bulk insert player box score records for a game.
    Uses INSERT OR IGNORE with the (name, game_id) unique constraint
    to prevent duplicate entries.

    Args:
        conn: SQLite connection object
        players: list of dicts, each with keys matching the players
                 table columns (name, team, date, game_id, points, etc.)
    """
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR IGNORE INTO players
            (name, team, date, game_id, points, assists, rebounds,
             off_rebounds, def_rebounds, steals, blocks, turnovers, minutes,
             field_goals_made, field_goals_attempted, field_goal_pct,
             three_pointers_made, three_pointers_attempted, three_point_pct,
             free_throws_made, free_throws_attempted, free_throw_pct, plus_minus)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            p["name"], p["team"], p["date"], p["game_id"],
            p.get("points"), p.get("assists"), p.get("rebounds"),
            p.get("off_rebounds"), p.get("def_rebounds"),
            p.get("steals"), p.get("blocks"), p.get("turnovers"),
            p.get("minutes"),
            p.get("field_goals_made"), p.get("field_goals_attempted"), p.get("field_goal_pct"),
            p.get("three_pointers_made"), p.get("three_pointers_attempted"), p.get("three_point_pct"),
            p.get("free_throws_made"), p.get("free_throws_attempted"), p.get("free_throw_pct"),
            p.get("plus_minus"),
        )
        for p in players
    ])
    conn.commit()


def insert_mlb_players(conn, players):
    """
    Bulk insert MLB player stats (batters and pitchers) for a game.
    Uses INSERT OR IGNORE with the (name, game_id, role) unique constraint.

    Args:
        conn: SQLite connection object
        players: list of dicts with keys matching the mlb_players table columns
    """
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR IGNORE INTO mlb_players
            (name, team, date, game_id, role,
             at_bats, hits, runs, home_runs, rbi, walks, strikeouts,
             innings_pitched, hits_allowed, earned_runs, walks_allowed,
             strikeouts_pitched, home_runs_allowed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            p["name"], p["team"], p["date"], p["game_id"], p["role"],
            p.get("at_bats"), p.get("hits"), p.get("runs"),
            p.get("home_runs"), p.get("rbi"), p.get("walks"),
            p.get("strikeouts"),
            p.get("innings_pitched"), p.get("hits_allowed"),
            p.get("earned_runs"), p.get("walks_allowed"),
            p.get("strikeouts_pitched"), p.get("home_runs_allowed"),
        )
        for p in players
    ])
    conn.commit()


def load_mlb_players(conn, player_name=None, team=None, role=None):
    """
    Load MLB player statistics from the database into a pandas DataFrame.
    Optionally filter by player name (partial), team, and/or role ('batter'/'pitcher').

    Args:
        conn: SQLite connection object
        player_name: optional player name to search for (partial match)
        team: optional team name to filter by
        role: optional role to filter by ('batter' or 'pitcher')

    Returns:
        pandas DataFrame of matching MLB player stat records
    """
    query = "SELECT * FROM mlb_players WHERE 1=1"
    params = []

    if player_name:
        query += " AND name LIKE ?"
        params.append(f"%{player_name}%")

    if team:
        query += " AND team = ?"
        params.append(team)

    if role:
        query += " AND role = ?"
        params.append(role)

    query += " ORDER BY date DESC"
    return pd.read_sql_query(query, conn, params=params)


def load_games(conn, team=None, league="NBA"):
    """
    Load games from the database into a pandas DataFrame.
    Optionally filter by team name (matches either home or away team)
    and by league. Results are ordered by date descending (most recent first).
    Excludes corrupt 0-0 records automatically.

    Args:
        conn: SQLite connection object
        team: optional team name to filter by (matches home_team or away_team)
        league: league to filter by (default: "NBA")

    Returns:
        pandas DataFrame of matching game records
    """
    # Exclude games where both scores are 0 — these are corrupt/incomplete records
    query = "SELECT * FROM games WHERE league = ? AND NOT (home_score = 0 AND away_score = 0)"
    params = [league]

    # Filter for games involving the specified team on either side
    if team:
        query += " AND (home_team = ? OR away_team = ?)"
        params.extend([team, team])

    query += " ORDER BY date DESC"
    return pd.read_sql_query(query, conn, params=params)


def load_players(conn, player_name=None, team=None):
    """
    Load player statistics from the database into a pandas DataFrame.
    Optionally filter by player name (case-insensitive partial match)
    and/or team name. Results are ordered by date descending.

    Args:
        conn: SQLite connection object
        player_name: optional player name to search for (partial match)
        team: optional team name to filter by

    Returns:
        pandas DataFrame of matching player stat records
    """
    query = "SELECT * FROM players WHERE 1=1"
    params = []

    # Case-insensitive partial match on player name so users don't
    # need to type the exact full name
    if player_name:
        query += " AND name LIKE ?"
        params.append(f"%{player_name}%")

    if team:
        query += " AND team = ?"
        params.append(team)

    query += " ORDER BY date DESC"
    return pd.read_sql_query(query, conn, params=params)


def upsert_injuries(conn, injuries):
    """
    Insert or replace injury records. Uses UNIQUE(player_name, team, league)
    so each refresh replaces stale entries for the same player.

    Args:
        conn: SQLite connection object
        injuries: list of dicts with keys matching the injuries table columns
    """
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO injuries
            (player_name, team, status, injury_type, body_part, detail,
             side, return_date, short_comment, long_comment, last_updated, league)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            i["player_name"], i["team"], i["status"],
            i.get("injury_type"), i.get("body_part"), i.get("detail"),
            i.get("side"), i.get("return_date"),
            i.get("short_comment"), i.get("long_comment"),
            i["last_updated"], i.get("league", "NBA"),
        )
        for i in injuries
    ])
    conn.commit()


def clear_injuries(conn, league="NBA"):
    """Remove all injury records for a league before a full refresh."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM injuries WHERE league = ?", (league,))
    conn.commit()


def load_injuries(conn, team=None, league="NBA"):
    """
    Load injury records from the database into a pandas DataFrame.
    Optionally filter by team.

    Args:
        conn: SQLite connection object
        team: optional team name to filter by
        league: league to filter by (default: "NBA")

    Returns:
        pandas DataFrame of injury records
    """
    query = "SELECT * FROM injuries WHERE league = ?"
    params = [league]
    if team:
        query += " AND team = ?"
        params.append(team)
    query += " ORDER BY team, status, player_name"
    return pd.read_sql_query(query, conn, params=params)


# ── Referee helpers ───────────────────────────────────────────────────────────

def upsert_referee_stats(conn, stats):
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO referee_stats
            (name, games_officiated, total_ppg, fouls_per_game, home_win_pct, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (s["name"], s.get("games_officiated"), s.get("total_ppg"),
         s.get("fouls_per_game"), s.get("home_win_pct"), s["last_updated"])
        for s in stats
    ])
    conn.commit()


def clear_referee_stats(conn):
    conn.cursor().execute("DELETE FROM referee_stats")
    conn.commit()


def load_referee_stats(conn):
    return pd.read_sql_query("SELECT * FROM referee_stats ORDER BY name", conn)


def upsert_referee_assignments(conn, assignments):
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO referee_assignments
            (game_matchup, referee_name, role, assignment_date)
        VALUES (?, ?, ?, ?)
    """, [
        (a["game_matchup"], a["referee_name"], a["role"], a["assignment_date"])
        for a in assignments
    ])
    conn.commit()


def clear_referee_assignments(conn):
    conn.cursor().execute("DELETE FROM referee_assignments")
    conn.commit()


def load_referee_assignments(conn, date=None):
    if date:
        return pd.read_sql_query(
            "SELECT * FROM referee_assignments WHERE assignment_date = ? ORDER BY game_matchup",
            conn, params=[date])
    return pd.read_sql_query("SELECT * FROM referee_assignments ORDER BY assignment_date DESC, game_matchup", conn)

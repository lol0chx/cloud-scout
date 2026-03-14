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
            steals INTEGER,
            blocks INTEGER,
            turnovers INTEGER,
            minutes TEXT,
            field_goal_pct REAL,
            three_point_pct REAL,
            FOREIGN KEY (game_id) REFERENCES games(id),
            UNIQUE (name, game_id)
        )
    """)

    conn.commit()
    return conn


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
             steals, blocks, turnovers, minutes, field_goal_pct, three_point_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            p["name"], p["team"], p["date"], p["game_id"],
            p.get("points"), p.get("assists"), p.get("rebounds"),
            p.get("steals"), p.get("blocks"), p.get("turnovers"),
            p.get("minutes"), p.get("field_goal_pct"), p.get("three_point_pct"),
        )
        for p in players
    ])
    conn.commit()


def load_games(conn, team=None, league="NBA"):
    """
    Load games from the database into a pandas DataFrame.
    Optionally filter by team name (matches either home or away team)
    and by league. Results are ordered by date descending (most recent first).

    Args:
        conn: SQLite connection object
        team: optional team name to filter by (matches home_team or away_team)
        league: league to filter by (default: "NBA")

    Returns:
        pandas DataFrame of matching game records
    """
    query = "SELECT * FROM games WHERE league = ?"
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

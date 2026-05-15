"""
database.py — Database layer for CloudScout.

Backed by SQLAlchemy 2.0 so the same code talks to either Postgres
(production, e.g. Supabase) or SQLite (local development fallback).

Driver selection:
    1. DATABASE_URL env var, if set, wins (typically Postgres in prod).
    2. Otherwise falls back to sqlite:///cloudscout.db so local dev
       continues to work without any configuration.

The public surface intentionally mirrors the original sqlite3 layer:
each top-level function takes a `db` (Database) as its first argument,
which the rest of the codebase obtains via `init_db()`.
"""

import os
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Load .env at import time so every entry point (api.py, app.py, main.py,
# scraper.py, scheduler.py) picks up DATABASE_URL / ANTHROPIC_API_KEY without
# each having to call load_dotenv() itself. No-ops when python-dotenv isn't
# installed or when no .env file is present.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Connection wrapper ────────────────────────────────────────────────────────

class Database:
    """Thin wrapper around a SQLAlchemy Engine.

    Mirrors the small slice of sqlite3.Connection's API the codebase used to
    rely on (`.close()`, used as a context manager), so existing callers
    don't need to change.
    """

    def __init__(self, url: str):
        self.url = url
        # pool_pre_ping handles Supabase / managed-Postgres idle disconnects;
        # pool_recycle keeps a long-lived API process from holding stale conns.
        connect_args = {}
        if url.startswith("sqlite"):
            # Allow the same SQLite connection to be used across threads
            # (FastAPI/uvicorn workers, Streamlit reruns, scheduler.py).
            connect_args["check_same_thread"] = False
        self.engine: Engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            future=True,
            connect_args=connect_args,
        )

    @property
    def is_postgres(self) -> bool:
        return self.engine.dialect.name == "postgresql"

    def close(self) -> None:
        self.engine.dispose()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_) -> None:
        self.close()


# ── Init / schema ─────────────────────────────────────────────────────────────

def init_db(db_path: Optional[str] = None) -> Database:
    """Open (and lazily create) the CloudScout database.

    Returns a `Database` whose engine targets DATABASE_URL when set,
    or sqlite:///cloudscout.db otherwise. Tables are created lazily
    via CREATE TABLE IF NOT EXISTS so this is safe to call repeatedly.
    """
    url = os.environ.get("DATABASE_URL") or _legacy_sqlite_url(db_path)
    # Heroku-style postgres:// → SQLAlchemy expects postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    db = Database(url)
    _ensure_schema(db)
    return db


def _legacy_sqlite_url(db_path: Optional[str]) -> str:
    return f"sqlite:///{db_path or 'cloudscout.db'}"


def _ensure_schema(db: Database) -> None:
    """Idempotent CREATE TABLE IF NOT EXISTS for all CloudScout tables."""
    auto_pk = "SERIAL PRIMARY KEY" if db.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

    stmts = [
        # ── games: API-supplied integer ID is the PK (not autoincrement)
        """
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
        """,
        # ── NBA player box scores
        f"""
        CREATE TABLE IF NOT EXISTS players (
            id {auto_pk},
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
            UNIQUE (name, game_id)
        )
        """,
        # ── MLB batters + pitchers (role discriminates)
        f"""
        CREATE TABLE IF NOT EXISTS mlb_players (
            id {auto_pk},
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
            UNIQUE (name, game_id, role)
        )
        """,
        # ── Injury reports (scraped from ESPN)
        f"""
        CREATE TABLE IF NOT EXISTS injuries (
            id {auto_pk},
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
        """,
        # ── Referee season stats (NBAStuffer)
        f"""
        CREATE TABLE IF NOT EXISTS referee_stats (
            id {auto_pk},
            name TEXT NOT NULL,
            games_officiated INTEGER,
            total_ppg REAL,
            fouls_per_game REAL,
            home_win_pct REAL,
            last_updated TEXT NOT NULL,
            UNIQUE (name)
        )
        """,
        # ── Referee per-game assignments (official.nba.com)
        f"""
        CREATE TABLE IF NOT EXISTS referee_assignments (
            id {auto_pk},
            game_matchup TEXT NOT NULL,
            referee_name TEXT NOT NULL,
            role TEXT NOT NULL,
            assignment_date TEXT NOT NULL,
            UNIQUE (game_matchup, referee_name, assignment_date)
        )
        """,
    ]

    with db.engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))


# ── Dialect-aware insert helpers ──────────────────────────────────────────────

def _insert_or_ignore_sql(db: Database, table: str, cols: list[str]) -> str:
    """SQLite-style INSERT OR IGNORE; on Postgres uses ON CONFLICT DO NOTHING."""
    col_list = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    if db.is_postgres:
        return (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            "ON CONFLICT DO NOTHING"
        )
    return f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"


def _upsert_sql(
    db: Database, table: str, cols: list[str], conflict_cols: list[str]
) -> str:
    """SQLite-style INSERT OR REPLACE; on Postgres uses ON CONFLICT (..) DO UPDATE."""
    col_list = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    if db.is_postgres:
        cc = ", ".join(conflict_cols)
        updates = ", ".join(
            f"{c}=EXCLUDED.{c}" for c in cols if c not in conflict_cols
        )
        return (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT ({cc}) DO UPDATE SET {updates}"
        )
    return f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"


def _read_sql(db: Database, query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """Run a SELECT and return a pandas DataFrame. Uses named-bind params (:name)."""
    return pd.read_sql_query(text(query), db.engine, params=params or {})


# ── Games ─────────────────────────────────────────────────────────────────────

def game_exists(db: Database, game_id: int) -> bool:
    """True if a row in `games` already has the given id."""
    with db.engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM games WHERE id = :id"), {"id": game_id}
        ).first()
    return row is not None


_GAME_COLS = [
    "id", "date", "home_team", "away_team",
    "home_score", "away_score", "league", "season",
]


def insert_game(db: Database, game: dict) -> None:
    """Insert one game row; ignores duplicate primary keys."""
    sql = _insert_or_ignore_sql(db, "games", _GAME_COLS)
    record = {k: game.get(k) for k in _GAME_COLS}
    with db.engine.begin() as conn:
        conn.execute(text(sql), record)


def load_games(db: Database, team: Optional[str] = None, league: str = "NBA") -> pd.DataFrame:
    """Load games (excluding corrupt 0-0 records). Optional filter by team / league."""
    query = (
        "SELECT * FROM games WHERE league = :league "
        "AND NOT (home_score = 0 AND away_score = 0)"
    )
    params: dict = {"league": league}
    if team:
        query += " AND (home_team = :team_home OR away_team = :team_away)"
        params["team_home"] = team
        params["team_away"] = team
    query += " ORDER BY date DESC"
    return _read_sql(db, query, params)


# ── NBA players ───────────────────────────────────────────────────────────────

_PLAYER_COLS = [
    "name", "team", "date", "game_id",
    "points", "assists", "rebounds",
    "off_rebounds", "def_rebounds",
    "steals", "blocks", "turnovers",
    "minutes",
    "field_goals_made", "field_goals_attempted", "field_goal_pct",
    "three_pointers_made", "three_pointers_attempted", "three_point_pct",
    "free_throws_made", "free_throws_attempted", "free_throw_pct",
    "plus_minus",
]


def insert_players(db: Database, players: list[dict]) -> None:
    """Bulk insert NBA player box scores; ignores duplicates on (name, game_id)."""
    if not players:
        return
    sql = _insert_or_ignore_sql(db, "players", _PLAYER_COLS)
    records = [{k: p.get(k) for k in _PLAYER_COLS} for p in players]
    with db.engine.begin() as conn:
        conn.execute(text(sql), records)


def load_players(
    db: Database,
    player_name: Optional[str] = None,
    team: Optional[str] = None,
) -> pd.DataFrame:
    """Load NBA player rows, optionally filtered by partial name match / team."""
    query = "SELECT * FROM players WHERE 1=1"
    params: dict = {}
    if player_name:
        query += " AND name LIKE :name"
        params["name"] = f"%{player_name}%"
    if team:
        query += " AND team = :team"
        params["team"] = team
    query += " ORDER BY date DESC"
    return _read_sql(db, query, params)


# ── MLB players ───────────────────────────────────────────────────────────────

_MLB_PLAYER_COLS = [
    "name", "team", "date", "game_id", "role",
    "at_bats", "hits", "runs", "home_runs", "rbi", "walks", "strikeouts",
    "innings_pitched", "hits_allowed", "earned_runs", "walks_allowed",
    "strikeouts_pitched", "home_runs_allowed",
]


def insert_mlb_players(db: Database, players: list[dict]) -> None:
    """Bulk insert MLB player rows; ignores duplicates on (name, game_id, role)."""
    if not players:
        return
    sql = _insert_or_ignore_sql(db, "mlb_players", _MLB_PLAYER_COLS)
    records = [{k: p.get(k) for k in _MLB_PLAYER_COLS} for p in players]
    with db.engine.begin() as conn:
        conn.execute(text(sql), records)


def load_mlb_players(
    db: Database,
    player_name: Optional[str] = None,
    team: Optional[str] = None,
    role: Optional[str] = None,
) -> pd.DataFrame:
    """Load MLB player rows, optionally filtered by partial name / team / role."""
    query = "SELECT * FROM mlb_players WHERE 1=1"
    params: dict = {}
    if player_name:
        query += " AND name LIKE :name"
        params["name"] = f"%{player_name}%"
    if team:
        query += " AND team = :team"
        params["team"] = team
    if role:
        query += " AND role = :role"
        params["role"] = role
    query += " ORDER BY date DESC"
    return _read_sql(db, query, params)


# ── Injuries ──────────────────────────────────────────────────────────────────

_INJURY_COLS = [
    "player_name", "team", "status", "injury_type", "body_part", "detail",
    "side", "return_date", "short_comment", "long_comment", "last_updated", "league",
]


def upsert_injuries(db: Database, injuries: list[dict]) -> None:
    """Insert-or-replace injury rows keyed on (player_name, team, league)."""
    if not injuries:
        return
    sql = _upsert_sql(
        db, "injuries", _INJURY_COLS,
        conflict_cols=["player_name", "team", "league"],
    )
    records = [
        {**{k: i.get(k) for k in _INJURY_COLS},
         "league": i.get("league", "NBA")}
        for i in injuries
    ]
    with db.engine.begin() as conn:
        conn.execute(text(sql), records)


def clear_injuries(db: Database, league: str = "NBA") -> None:
    """Wipe all injury rows for a league (used before a full refresh)."""
    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM injuries WHERE league = :league"), {"league": league})


def load_injuries(db: Database, team: Optional[str] = None, league: str = "NBA") -> pd.DataFrame:
    query = "SELECT * FROM injuries WHERE league = :league"
    params: dict = {"league": league}
    if team:
        query += " AND team = :team"
        params["team"] = team
    query += " ORDER BY team, status, player_name"
    return _read_sql(db, query, params)


# ── Referees ──────────────────────────────────────────────────────────────────

_REFEREE_STATS_COLS = [
    "name", "games_officiated", "total_ppg",
    "fouls_per_game", "home_win_pct", "last_updated",
]


def upsert_referee_stats(db: Database, stats: list[dict]) -> None:
    if not stats:
        return
    sql = _upsert_sql(db, "referee_stats", _REFEREE_STATS_COLS, conflict_cols=["name"])
    records = [{k: s.get(k) for k in _REFEREE_STATS_COLS} for s in stats]
    with db.engine.begin() as conn:
        conn.execute(text(sql), records)


def clear_referee_stats(db: Database) -> None:
    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM referee_stats"))


def load_referee_stats(db: Database) -> pd.DataFrame:
    return _read_sql(db, "SELECT * FROM referee_stats ORDER BY name")


_REFEREE_ASSIGNMENT_COLS = ["game_matchup", "referee_name", "role", "assignment_date"]


def upsert_referee_assignments(db: Database, assignments: list[dict]) -> None:
    if not assignments:
        return
    sql = _upsert_sql(
        db, "referee_assignments", _REFEREE_ASSIGNMENT_COLS,
        conflict_cols=["game_matchup", "referee_name", "assignment_date"],
    )
    records = [{k: a.get(k) for k in _REFEREE_ASSIGNMENT_COLS} for a in assignments]
    with db.engine.begin() as conn:
        conn.execute(text(sql), records)


def clear_referee_assignments(db: Database) -> None:
    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM referee_assignments"))


def load_referee_assignments(db: Database, date: Optional[str] = None) -> pd.DataFrame:
    if date:
        return _read_sql(
            db,
            "SELECT * FROM referee_assignments WHERE assignment_date = :d ORDER BY game_matchup",
            {"d": date},
        )
    return _read_sql(
        db,
        "SELECT * FROM referee_assignments ORDER BY assignment_date DESC, game_matchup",
    )

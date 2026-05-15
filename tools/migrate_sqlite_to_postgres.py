"""
migrate_sqlite_to_postgres.py — one-time data migration.

Reads every row from a local SQLite cloudscout.db and copies it into the
Postgres database pointed to by DATABASE_URL (typically Supabase).

Usage:
    export DATABASE_URL='postgresql://postgres.xxx:PASSWORD@aws-0-us-east-2.pooler.supabase.com:6543/postgres'
    venv/bin/python tools/migrate_sqlite_to_postgres.py [--sqlite cloudscout.db] [--truncate]

Flags:
    --sqlite PATH   Path to the SQLite file. Defaults to ./cloudscout.db.
    --truncate      DELETE all rows in each Postgres table before copying.
                    Use this on a fresh database OR when re-running the
                    migration; omit if you want to append.
    --chunksize N   Pandas to_sql chunk size (default 1000).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


TABLES = [
    "games",
    "players",
    "mlb_players",
    "injuries",
    "referee_stats",
    "referee_assignments",
]


def _connect_sqlite(path: str):
    if not Path(path).exists():
        sys.exit(f"❌ SQLite file not found: {path}")
    return create_engine(f"sqlite:///{path}")


def _connect_postgres():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit(
            "❌ DATABASE_URL is not set. Export your Supabase connection "
            "string before running this script."
        )
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return create_engine(url, pool_pre_ping=True, future=True)


def _ensure_schema_target(pg_engine) -> None:
    """Make sure Postgres has the target schema. Imports init_db so the
    canonical CREATE TABLE statements come from database.py."""
    # database.py reads DATABASE_URL, so init_db() already targets Postgres
    # when this script is run. Importing it has the side effect we want.
    from database import init_db
    db = init_db()
    db.close()  # we're done with that handle; we'll use our own engine here
    _ = pg_engine  # silence unused-arg lint when the import succeeds


def _row_count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0


def _truncate(pg_engine, table: str) -> None:
    with pg_engine.begin() as conn:
        # RESTART IDENTITY resets the SERIAL counters; CASCADE is safe here
        # since we delete dependent tables in dependency order anyway.
        conn.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))


def _copy_table(sqlite_engine, pg_engine, table: str, chunksize: int) -> int:
    """Copy every row from the SQLite table to the Postgres table.

    Drops the local SQLite `id` for autoincrement tables so Postgres can
    generate fresh SERIAL ids — except for `games`, where `id` is API-supplied
    and stable across stores.
    """
    df = pd.read_sql_query(f"SELECT * FROM {table}", sqlite_engine)
    if df.empty:
        print(f"  {table}: empty in source, skipping")
        return 0

    if table != "games" and "id" in df.columns:
        df = df.drop(columns=["id"])

    df.to_sql(
        table,
        pg_engine,
        if_exists="append",
        index=False,
        chunksize=chunksize,
        method="multi",
    )
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time SQLite → Postgres data migration for CloudScout."
    )
    parser.add_argument("--sqlite", default="cloudscout.db",
                        help="Path to the SQLite source file.")
    parser.add_argument("--truncate", action="store_true",
                        help="DELETE all rows in the target tables first.")
    parser.add_argument("--chunksize", type=int, default=1000,
                        help="Rows per insert batch (default 1000).")
    args = parser.parse_args()

    print("→ connecting to source SQLite:", args.sqlite)
    sqlite_engine = _connect_sqlite(args.sqlite)

    print("→ connecting to target Postgres via DATABASE_URL")
    pg_engine = _connect_postgres()

    print("→ ensuring target schema exists")
    _ensure_schema_target(pg_engine)

    if args.truncate:
        print("→ truncating target tables (in reverse-dependency order)")
        # mlb_players / players reference games via game_id, so wipe them first.
        for t in reversed(TABLES):
            _truncate(pg_engine, t)

    print("→ copying tables")
    total = 0
    for t in TABLES:
        copied = _copy_table(sqlite_engine, pg_engine, t, args.chunksize)
        target_count = _row_count(pg_engine, t)
        print(f"  {t:22s} copied={copied:>7d}   target_now={target_count}")
        total += copied

    print(f"\n✓ migration complete: {total} rows copied across {len(TABLES)} tables")


if __name__ == "__main__":
    main()

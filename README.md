# CloudScout

Multi-sport (NBA + MLB) stats, analytics, and game-prediction platform.
A FastAPI backend powers a native SwiftUI iOS app and a Streamlit web
dashboard; data is scraped from public NBA / MLB / ESPN sources and stored
in Postgres (Supabase in production, SQLite locally).

## Architecture

```
              ┌─────────────────────────────┐
              │  scraper.py / mlb_scraper.py│  ◀── NBA-API · MLB-StatsAPI · ESPN
              │  (writes via database.py)   │
              └──────────────┬──────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │   Postgres  (Supabase)      │  ◀── DATABASE_URL env var
              │   – games, players, injuries│
              │   – mlb_players, referees   │
              └──────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  FastAPI     │     │  Streamlit   │     │  CLI tools   │
│  api.py      │     │  app.py      │     │  main.py     │
│  (Fly.io)    │     │  (Streamlit  │     │              │
└──────┬───────┘     │   Cloud)     │     └──────────────┘
       │             └──────────────┘
       ▼
┌──────────────┐
│  iOS app     │
│  SwiftUI     │
└──────────────┘
```

- **`database.py`** — SQLAlchemy 2.0 data-access layer. Reads `DATABASE_URL`;
  falls back to `sqlite:///cloudscout.db` if unset.
- **`api.py`** — FastAPI REST backend. Deployed to Fly.io as a container.
- **`app.py`** — Streamlit web dashboard. Deployed to Streamlit Community Cloud.
- **`ios/`** — SwiftUI iOS app, talks to the FastAPI backend over HTTPS.
- **`mobile/`** — Expo / React Native alternate client.
- **`scraper.py`, `mlb_scraper.py`** — data ingestion.
- **`analytics.py`, `mlb_analytics.py`** — pure-Python stat / prediction logic
  (8-Pillar MLB model + Pythagorean blend lives here).

## Quickstart (local development)

```bash
# 1. Clone & install
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 2. (Optional) populate a local SQLite DB so you have something to look at.
#    Without a Supabase URL, database.py uses sqlite:///cloudscout.db.
venv/bin/python main.py --scrape-all --last 10

# 3. Run things
venv/bin/uvicorn api:app --reload                  # FastAPI on :8000
venv/bin/python -m streamlit run app.py            # Streamlit on :8501
```

See **[COMMANDS.txt](COMMANDS.txt)** for the full menu of run modes
(same-WiFi iOS, different-WiFi iOS via ngrok, Expo, CLI tools, etc.).

## Environment variables

All optional during local dev. Required for production deploys.

| Variable             | Purpose                                                                  |
|----------------------|--------------------------------------------------------------------------|
| `DATABASE_URL`       | Postgres connection string (Supabase pooler URL). Falls back to SQLite.  |
| `ANTHROPIC_API_KEY`  | Enables the AI Scout chat in `api.py` / `app.py`.                        |
| `API_BASE` (iOS)     | Override the FastAPI base URL inside the iOS app.                        |
| `EXPO_PUBLIC_API_URL`| Same idea for the Expo client.                                           |

A starter template lives in [`.env.example`](.env.example). Copy it to
`.env` and fill in your values (the file is gitignored).

## Production deployment

The free-tier production stack is:

| Component | Host                       | Free tier              |
|-----------|----------------------------|------------------------|
| Database  | Supabase (Postgres)        | 500 MB                 |
| Backend   | Fly.io (Docker container)  | 3 shared-cpu machines  |
| Web app   | Streamlit Community Cloud  | 1 public app           |

### 1) Postgres on Supabase

1. Create a project at <https://supabase.com> (free tier).
2. **Project Settings → Database → Connection string** — copy the
   *Connection pooling* URL (transaction mode, port `6543`). It looks like:
   ```
   postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
   ```
3. Export it locally and create the schema by simply opening a connection
   (the FastAPI app does this on startup, but you can pre-create with):
   ```bash
   export DATABASE_URL='postgresql://...'
   venv/bin/python -c "from database import init_db; init_db().close(); print('schema OK')"
   ```
4. Migrate your existing local data:
   ```bash
   venv/bin/python tools/migrate_sqlite_to_postgres.py --sqlite cloudscout.db --truncate
   ```
   The script reads every row from `cloudscout.db` and copies it into
   the Postgres database that `DATABASE_URL` points at.

### 2) FastAPI backend on Fly.io

```bash
# Install the CLI (macOS):
brew install flyctl

# One-time:
fly auth login
fly launch --no-deploy           # accept the suggested app name + region
fly secrets set \
    DATABASE_URL="$DATABASE_URL" \
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
fly volumes list                 # nothing needed — we use Supabase for storage

# Every deploy:
fly deploy
```

`fly.toml` keeps one machine warm (`min_machines_running = 1`) so the first
iOS request after idle isn't slow. The healthcheck hits `/health` every 30s.

Once deployed, point the iOS app at the Fly hostname:

```swift
// ios/CloudScout/APIClient.swift, line 5
let API_BASE = ProcessInfo.processInfo.environment["API_BASE"]
               ?? "https://cloudscout-api.fly.dev"
```

### 3) Streamlit dashboard on Streamlit Cloud

1. Push the repo to GitHub.
2. <https://share.streamlit.io> → *New app* → point at `app.py`.
3. **Settings → Secrets** — add the same `DATABASE_URL` (and
   `ANTHROPIC_API_KEY` if you want AI Scout chat). Streamlit Cloud will
   inject them as `os.environ` at runtime.

## Database layer notes

`database.py` is dialect-agnostic via SQLAlchemy 2.0 Core. Every public
function (`init_db`, `load_games`, `insert_players`, …) accepts a
`Database` wrapper as its first arg — internally the wrapper holds a
SQLAlchemy `Engine`, exposes `.close()` for backward compatibility, and
flips its INSERT dialect (`INSERT OR IGNORE` vs `INSERT … ON CONFLICT DO
NOTHING`) based on `engine.dialect.name`.

Adding a new table:

1. Append a `CREATE TABLE IF NOT EXISTS …` block to `_ensure_schema()`.
   Use `{auto_pk}` for `INTEGER PRIMARY KEY AUTOINCREMENT` /
   `SERIAL PRIMARY KEY` portability.
2. Add a `_TABLE_COLS` constant + thin `insert_*` / `load_*` helpers
   alongside the existing ones.

## Prediction model

The MLB win-probability + projected-runs formula lives in
`mlb_analytics.mlb_win_probability()` and powers both the iOS Predict tab
and the Streamlit Predict view. It is a 70% / 30% blend of an 8-pillar
weighted composite (pitching · offense · bullpen · defense · plate
discipline · baserunning · home/park · situational) and a Pythagorean
expectation (`RS^1.83 / (RS^1.83 + RA^1.83)`) computed on team-by-team
projected runs. The run-line margin is the direct projected-run
differential, no logit conversion.

NBA win probability uses the 6-factor model in
`analytics.win_probability()` (overall W%, point differential, H2H, H2H
margin, home/away splits, recent form).

See **[ALGO.md](ALGO.md)** for the home-feed insight logic (private notes).

## Repository layout

```
.
├── api.py                 FastAPI backend (deployed to Fly.io)
├── app.py                 Streamlit dashboard
├── main.py                CLI analytics tool
├── database.py            SQLAlchemy data-access layer (Postgres/SQLite)
├── analytics.py           NBA + shared team analytics
├── mlb_analytics.py       MLB-specific analytics + 8-pillar win prob
├── scraper.py             NBA / injury / referee scrapers
├── mlb_scraper.py         MLB-StatsAPI scraper
├── scheduler.py           Nightly cron entry point
├── tools/
│   └── migrate_sqlite_to_postgres.py
├── ios/                   SwiftUI app
├── mobile/                Expo / React Native app
├── Dockerfile             Fly.io container build
├── fly.toml               Fly.io deploy config
├── requirements.txt
├── COMMANDS.txt           Run / dev mode reference
├── ALGO.md                Home-feed algorithm notes (private)
└── CHANGES.md             Project changelog
```

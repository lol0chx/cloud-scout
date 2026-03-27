"""
api.py — FastAPI REST backend for CloudScout mobile and web clients.

Wraps all scraper and analytics functions as HTTP endpoints.
Run with: uvicorn api:app --reload
"""

import os

import anthropic
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from nba_api.stats.static import teams as nba_teams
from pydantic import BaseModel

from analytics import (
    head_to_head,
    home_away_stats,
    last_n_avg,
    player_avg,
    player_vs_team,
    rolling_form,
    season_standings,
    top_performers,
    win_probability,
    win_streak,
)
from database import init_db, load_games, load_mlb_players, load_players
from mlb_analytics import (
    mlb_batter_avg,
    mlb_batter_vs_team,
    mlb_pitcher_avg,
    mlb_top_batters,
    mlb_top_pitchers,
)
from mlb_scraper import DEFAULT_SEASON as MLB_DEFAULT_SEASON
from mlb_scraper import get_all_mlb_teams, scrape_mlb_team
from scraper import scrape_team

app = FastAPI(title="CloudScout API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _conn():
    return init_db()


def _to_json(df: pd.DataFrame) -> list:
    return df.where(pd.notnull(df), None).to_dict(orient="records")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Teams ─────────────────────────────────────────────────────────────────────

@app.get("/teams")
def list_teams(league: str = "NBA"):
    if league.upper() == "MLB":
        return get_all_mlb_teams()
    return sorted([t["full_name"] for t in nba_teams.get_teams()])


# ── Games ─────────────────────────────────────────────────────────────────────

@app.get("/games")
def get_games(league: str = "NBA", team: str = "", limit: int = 30):
    conn = _conn()
    try:
        df = load_games(conn, team=team or None, league=league.upper())
        return _to_json(df.head(limit))
    finally:
        conn.close()


# ── Standings ─────────────────────────────────────────────────────────────────

@app.get("/standings")
def get_standings(league: str = "NBA"):
    conn = _conn()
    try:
        df = load_games(conn, league=league.upper())
        if df.empty:
            return []
        return _to_json(season_standings(df))
    finally:
        conn.close()


# ── Team Form ─────────────────────────────────────────────────────────────────

@app.get("/team/form")
def get_team_form(team: str, league: str = "NBA", n: int = 15):
    conn = _conn()
    try:
        df = load_games(conn, league=league.upper())
        if df.empty:
            raise HTTPException(404, "No games in database")
        avg = last_n_avg(team, n, df).iloc[0]
        streak_count, streak_type = win_streak(team, df)
        form_log = rolling_form(team, n, df)
        return {
            "team": team,
            "games": int(avg["games"]),
            "streak_count": streak_count,
            "streak_type": streak_type,
            "avg_scored": float(avg["avg_scored"]),
            "avg_conceded": float(avg["avg_conceded"]),
            "net_rating": round(float(avg["avg_scored"]) - float(avg["avg_conceded"]), 1),
            "form_log": _to_json(form_log),
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()


# ── Head-to-Head ──────────────────────────────────────────────────────────────

@app.get("/team/h2h")
def get_h2h(team_a: str, team_b: str, league: str = "NBA", n: int = 10):
    conn = _conn()
    try:
        df = load_games(conn, league=league.upper())
        if df.empty:
            return {"games": [], "team_a_wins": 0, "team_b_wins": 0, "avg_total": 0}
        h2h = head_to_head(team_a, team_b, n, df)
        if h2h.empty:
            return {"games": [], "team_a_wins": 0, "team_b_wins": 0, "avg_total": 0}
        a_col = f"{team_a}_score"
        b_col = f"{team_b}_score"
        return {
            "games": _to_json(h2h),
            "team_a_wins": int((h2h["winner"] == team_a).sum()),
            "team_b_wins": int((h2h["winner"] == team_b).sum()),
            "avg_total": round(float(h2h[a_col].mean() + h2h[b_col].mean()), 1),
        }
    finally:
        conn.close()


# ── Home / Away ───────────────────────────────────────────────────────────────

@app.get("/team/home-away")
def get_home_away(team: str, league: str = "NBA"):
    conn = _conn()
    try:
        df = load_games(conn, league=league.upper())
        stats = home_away_stats(team, df)
        if stats is None:
            raise HTTPException(404, f"No data for {team}")
        return stats
    finally:
        conn.close()


# ── Prediction ────────────────────────────────────────────────────────────────

@app.get("/team/prediction")
def get_prediction(team_a: str, team_b: str, league: str = "NBA", home: str = ""):
    conn = _conn()
    try:
        df = load_games(conn, league=league.upper())
        if df.empty:
            raise HTTPException(404, "No games in database")
        home_team = home if home in [team_a, team_b] else None
        prob_a, prob_b, margin = win_probability(team_a, team_b, df, home_team=home_team)

        def _record(team):
            tg = df[(df["home_team"] == team) | (df["away_team"] == team)]
            if tg.empty:
                return {"wins": 0, "losses": 0, "win_pct": 0.0}
            s = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
            c = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
            w = int((s.values > c.values).sum())
            return {"wins": w, "losses": len(tg) - w, "win_pct": round(w / len(tg) * 100, 1)}

        sc_a, st_a = win_streak(team_a, df)
        sc_b, st_b = win_streak(team_b, df)
        return {
            "team_a": team_a, "team_b": team_b,
            "prob_a": prob_a, "prob_b": prob_b, "margin": margin,
            "team_a_record": _record(team_a), "team_b_record": _record(team_b),
            "team_a_streak": {"count": sc_a, "type": st_a},
            "team_b_streak": {"count": sc_b, "type": st_b},
        }
    finally:
        conn.close()


# ── Top Performers ────────────────────────────────────────────────────────────

@app.get("/team/top-performers")
def get_top_performers(team: str, league: str = "NBA", n: int = 15):
    conn = _conn()
    try:
        games_df = load_games(conn, league=league.upper())
        if league.upper() == "MLB":
            players_df = load_mlb_players(conn)
            return {
                "batters": _to_json(mlb_top_batters(team, n, players_df, games_df)),
                "pitchers": _to_json(mlb_top_pitchers(team, n, players_df, games_df)),
            }
        players_df = load_players(conn)
        return {"players": _to_json(top_performers(team, n, players_df, games_df))}
    finally:
        conn.close()


# ── Players ───────────────────────────────────────────────────────────────────

@app.get("/players")
def list_players(league: str = "NBA", team: str = "", name: str = "", role: str = ""):
    conn = _conn()
    try:
        if league.upper() == "MLB":
            df = load_mlb_players(conn, player_name=name or None, team=team or None, role=role or None)
        else:
            df = load_players(conn, player_name=name or None, team=team or None)
        return sorted(df["name"].unique().tolist())
    finally:
        conn.close()


@app.get("/player/stats")
def get_player_stats(name: str, league: str = "NBA", n: int = 15, role: str = "batter"):
    conn = _conn()
    try:
        if league.upper() == "MLB":
            df = load_mlb_players(conn)
            result = mlb_pitcher_avg(name, n, df) if role == "pitcher" else mlb_batter_avg(name, n, df)
        else:
            df = load_players(conn)
            result = player_avg(name, n, df)
        return _to_json(result)[0] if not result.empty else {}
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()


@app.get("/player/vs-team")
def get_player_vs_team(name: str, opponent: str, league: str = "NBA", n: int = 15, role: str = "batter"):
    conn = _conn()
    try:
        games_df = load_games(conn, league=league.upper())
        if league.upper() == "MLB":
            players_df = load_mlb_players(conn)
            result = mlb_batter_vs_team(name, opponent, n, players_df, games_df)
        else:
            players_df = load_players(conn)
            result = player_vs_team(name, opponent, n, players_df, games_df)
        return _to_json(result)[0] if not result.empty else {}
    finally:
        conn.close()


@app.get("/player/log")
def get_player_log(name: str, league: str = "NBA", n: int = 20, role: str = "batter"):
    conn = _conn()
    try:
        games_df = load_games(conn, league=league.upper())
        if league.upper() == "MLB":
            df = load_mlb_players(conn)
            rows = df[(df["name"] == name) & (df["role"] == role)]
        else:
            df = load_players(conn)
            rows = df[df["name"] == name]
        rows = rows.sort_values("date", ascending=False).head(n)
        rows = rows.merge(games_df[["id", "home_team", "away_team"]], left_on="game_id", right_on="id", how="left")
        rows["opponent"] = rows.apply(
            lambda r: r["away_team"] if r["team"] == r["home_team"] else r["home_team"], axis=1
        )
        return _to_json(rows)
    finally:
        conn.close()


# ── Scrape ────────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    league: str = "NBA"
    team: str
    last: int = 15
    season: int = MLB_DEFAULT_SEASON


@app.post("/scrape/team")
def scrape(req: ScrapeRequest):
    try:
        if req.league.upper() == "MLB":
            g, p = scrape_mlb_team(req.team, season=req.season, last=req.last)
        else:
            g, p = scrape_team(req.team, last=req.last)
        return {"games_added": len(g), "players_added": len(p)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── AI Chat ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    league: str = "NBA"
    message: str
    history: list = []


@app.post("/ai/chat")
def ai_chat(req: ChatRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set on server")

    conn = _conn()
    try:
        league = req.league.upper()
        games_df = load_games(conn, league=league)
        context_parts = []

        if not games_df.empty:
            recent = games_df.sort_values("date", ascending=False).head(30)
            context_parts.append(
                "Recent games:\n" +
                recent[["date", "home_team", "away_team", "home_score", "away_score"]].to_string(index=False)
            )
            context_parts.append("Standings:\n" + season_standings(games_df).to_string(index=False))

        if league == "MLB":
            pdf = load_mlb_players(conn)
            if not pdf.empty:
                b = pdf[pdf["role"] == "batter"]
                top = (b.groupby("name")
                       .agg(HR=("home_runs", "sum"), RBI=("rbi", "sum"),
                            H=("hits", "sum"), AB=("at_bats", "sum"))
                       .reset_index())
                top["AVG"] = top.apply(lambda r: round(r["H"] / r["AB"], 3) if r["AB"] > 0 else 0.0, axis=1)
                context_parts.append("Top batters:\n" + top.sort_values("HR", ascending=False).head(20).to_string(index=False))
        else:
            pdf = load_players(conn)
            if not pdf.empty:
                top = (pdf.groupby("name")
                       .agg(avg_pts=("points", "mean"), avg_reb=("rebounds", "mean"), avg_ast=("assists", "mean"))
                       .sort_values("avg_pts", ascending=False).head(30).round(1))
                context_parts.append("Top scorers:\n" + top.to_string())

        context = "\n\n".join(context_parts) or "No data in the database yet."
        messages = req.history[-10:] + [{"role": "user", "content": f"Stats:\n{context}\n\nQuestion: {req.message}"}]

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=f"You are AI Scout, an expert {league} analyst. Answer using only the provided stats. Be concise.",
            messages=messages,
        )
        return {"response": resp.content[0].text}
    finally:
        conn.close()

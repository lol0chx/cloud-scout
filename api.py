"""
api.py — FastAPI REST backend for CloudScout mobile and web clients.

Wraps all scraper and analytics functions as HTTP endpoints.
Run with: uvicorn api:app --reload
"""

import os

import anthropic
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from nba_api.stats.static import teams as nba_teams
from pydantic import BaseModel

from analytics import (
    advanced_team_stats,
    head_to_head,
    h2h_pace,
    home_away_stats,
    last_n_avg,
    player_avg,
    player_projected_stats,
    player_vs_team,
    projected_total,
    rolling_form,
    season_standings,
    top_performers,
    win_probability,
    win_streak,
)
from database import init_db, load_games, load_mlb_players, load_players, load_injuries, load_referee_stats, load_referee_assignments
from mlb_analytics import (
    mlb_batter_avg,
    mlb_batter_vs_team,
    mlb_pitcher_avg,
    mlb_top_batters,
    mlb_top_pitchers,
    mlb_win_probability,
    mlb_player_projected_stats,
)
from mlb_scraper import DEFAULT_SEASON as MLB_DEFAULT_SEASON
from mlb_scraper import get_all_mlb_teams, scrape_mlb_team, fetch_todays_mlb_games
from scraper import scrape_team, scrape_injuries, fetch_todays_games, fetch_starters, scrape_referees, live_injuries

app = FastAPI(title="CloudScout API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Shared-secret guard for mutating / cost-bearing endpoints.

    Disabled when API_KEY is unset on the server (so deploying this code
    before the secret is configured doesn't break scrape/AI). Once API_KEY
    is set as a Fly secret, these endpoints require a matching X-API-Key
    header — blocking anonymous internet abuse of scrape jobs and /ai/chat.
    Read (GET) endpoints stay open: they serve public sports data.
    """
    expected = os.environ.get("API_KEY")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(401, "Unauthorized")


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
        # Always use only the most recent season's games
        latest_season = df["season"].max()
        df = df[df["season"] == latest_season]
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


# ── Advanced Stats ────────────────────────────────────────────────────────────

@app.get("/team/advanced")
def get_advanced_stats(team: str, league: str = "NBA", n: int = 10):
    """
    Return advanced team analytics for the last N games:
    pace, offensive/defensive rating, net rating, eFG%, TS%,
    3PAr, FTr, TOV%, OREB%, DREB%, FG%/3P%/FT%, and rest days.
    """
    if league.upper() != "NBA":
        raise HTTPException(400, "Advanced stats only available for NBA")
    conn = _conn()
    try:
        games_df = load_games(conn, league="NBA")
        players_df = load_players(conn)
        if games_df.empty:
            raise HTTPException(404, "No games in database")
        stats = advanced_team_stats(team, games_df, players_df, n)
        return stats
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()


@app.get("/team/advanced/h2h")
def get_h2h_advanced(team_a: str, team_b: str, league: str = "NBA", n: int = 10):
    """
    Return advanced stats for both teams side-by-side plus H2H pace.
    Used by the Predict tab to show a full analytical breakdown.
    """
    if league.upper() != "NBA":
        raise HTTPException(400, "Advanced stats only available for NBA")
    conn = _conn()
    try:
        games_df = load_games(conn, league="NBA")
        players_df = load_players(conn)
        if games_df.empty:
            raise HTTPException(404, "No games in database")
        stats_a = advanced_team_stats(team_a, games_df, players_df, n)
        stats_b = advanced_team_stats(team_b, games_df, players_df, n)
        pace = h2h_pace(team_a, team_b, games_df, players_df, n)
        return {
            "team_a": stats_a,
            "team_b": stats_b,
            "h2h_pace": pace,
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()


# ── Over/Under Projected Total ────────────────────────────────────────────────

@app.get("/predict/total")
def get_projected_total(team_a: str, team_b: str, home: str = "", n: int = 10):
    """
    9-step projected over/under total with full step-by-step breakdown.
    Includes injury and referee adjustments when data is available.
    """
    conn = _conn()
    try:
        games_df = load_games(conn, league="NBA")
        players_df = load_players(conn)
        injuries_df = load_injuries(conn, league="NBA")
        ref_stats_df = load_referee_stats(conn)
        ref_assign_df = load_referee_assignments(conn)
        if games_df.empty:
            raise HTTPException(404, "No games in database")
        home_team = home if home in [team_a, team_b] else None
        result = projected_total(team_a, team_b, games_df, players_df,
                                  home_team=home_team, n=n,
                                  injuries_df=injuries_df,
                                  referee_stats_df=ref_stats_df,
                                  referee_assignments_df=ref_assign_df)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()


# ── Prediction ────────────────────────────────────────────────────────────────

@app.get("/team/prediction")
def get_prediction(team_a: str, team_b: str, league: str = "NBA", home: str = ""):
    conn = _conn()
    try:
        league_u = league.upper()
        df = load_games(conn, league=league_u)
        if df.empty:
            raise HTTPException(404, "No games in database")
        home_team = home if home in [team_a, team_b] else None

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
        base = {
            "team_a": team_a, "team_b": team_b,
            "team_a_record": _record(team_a), "team_b_record": _record(team_b),
            "team_a_streak": {"count": sc_a, "type": st_a},
            "team_b_streak": {"count": sc_b, "type": st_b},
        }

        if league_u == "MLB":
            players_df = load_mlb_players(conn)
            mlb = mlb_win_probability(team_a, team_b, df, players_df, home_team=home_team, n=20)
            base.update({
                "prob_a": mlb["prob_a"],
                "prob_b": mlb["prob_b"],
                "margin": mlb["margin"],
                "proj_runs_a": mlb["proj_runs_a"],
                "proj_runs_b": mlb["proj_runs_b"],
                "projected_total": mlb["projected_total"],
                "pythagorean_prob_a": mlb["pythagorean_prob_a"],
                "pillars": mlb["pillars"],
                "h2h_avg_total": mlb["h2h_avg_total"],
            })
        else:
            prob_a, prob_b, margin = win_probability(team_a, team_b, df, home_team=home_team, pts_per_logit=6.0)
            base.update({"prob_a": prob_a, "prob_b": prob_b, "margin": margin})

        return base
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


@app.get("/player/projected")
def get_player_projected(name: str, opponent: str, league: str = "NBA",
                         role: str = "batter", n: int = 15):
    """
    Project a player's per-game line vs a specific opponent.

    NBA: pts/ast/reb/stl. MLB (`league=MLB`): batter (H/HR/RBI/R/BB/SO + AVG)
    or pitcher (SO/ER/H/BB/IP + ERA/WHIP) via `role`. Both blend a decayed
    baseline, recent 5-game form, Bayesian-shrunk head-to-head vs the
    opponent, and an opponent factor. Returns breakdown, H2H log, injury
    flag, streak context, and confidence.
    """
    conn = _conn()
    try:
        league_u = league.upper()
        games_df = load_games(conn, league=league_u)
        injuries_df = load_injuries(conn, league=league_u)
        if league_u == "MLB":
            players_df = load_mlb_players(conn)
            if players_df.empty:
                raise HTTPException(404, "No player data in database")
            result = mlb_player_projected_stats(
                name, opponent, players_df, games_df,
                role=role, injuries_df=injuries_df, n=n
            )
        else:
            players_df = load_players(conn)
            if players_df.empty:
                raise HTTPException(404, "No player data in database")
            result = player_projected_stats(
                name, opponent, players_df, games_df,
                injuries_df=injuries_df, n=n
            )
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result
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


@app.post("/scrape/team", dependencies=[Depends(require_key)])
def scrape(req: ScrapeRequest):
    try:
        if req.league.upper() == "MLB":
            g, p = scrape_mlb_team(req.team, season=req.season, last=req.last)
        else:
            g, p = scrape_team(req.team, last=req.last)
        return {"games_added": len(g), "players_added": len(p)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Injuries ─────────────────────────────────────────────────────────────────

@app.post("/injuries/refresh", dependencies=[Depends(require_key)])
def refresh_injuries(league: str = "NBA"):
    """Fetch latest injury report from ESPN and save to database."""
    result = scrape_injuries(league.upper())
    return {"injuries_updated": len(result)}


@app.get("/injuries")
def get_injuries(league: str = "NBA", team: str = ""):
    """
    Get the current injury report, optionally filtered by team.

    Always pulls a fresh ESPN snapshot first (and persists it to the local
    DB), matching the live behavior of /games/today. Falls back to the
    cached DB rows if the ESPN fetch fails.
    """
    df = live_injuries(league.upper())
    if team:
        df = df[df["team"] == team]
    return _to_json(df)


# ── Today's Games & Starters ────────────────────────────────────────────────

@app.get("/games/today")
def get_todays_games():
    """Today's NBA + MLB scoreboard (scheduled, live, completed).

    Each item carries a `league` field so the feed can route/style it.
    NBA first (matches prior ordering), then MLB.
    """
    nba = fetch_todays_games()
    for g in nba:
        g.setdefault("league", "NBA")
    try:
        mlb = fetch_todays_mlb_games()
    except Exception as e:
        print(f"MLB today's games failed: {e}")
        mlb = []
    return nba + mlb


@app.get("/games/starters/{game_id}")
def get_game_starters(game_id: str):
    """Get confirmed starters for a live or completed NBA game."""
    result = fetch_starters(game_id)
    if not result.get("home") and not result.get("away"):
        raise HTTPException(404, "Starters not yet available — game may not have started")
    return result


# ── Referees ──────────────────────────────────────────────────────────────────

@app.post("/referees/refresh", dependencies=[Depends(require_key)])
def refresh_referees():
    """Fetch latest referee stats and today's assignments."""
    stats_count, assign_count = scrape_referees()
    return {"stats_updated": stats_count, "assignments_updated": assign_count}


@app.get("/referees/stats")
def get_referee_stats():
    """Get all referee season stats."""
    conn = _conn()
    try:
        return _to_json(load_referee_stats(conn))
    finally:
        conn.close()


@app.get("/referees/assignments")
def get_referee_assignments(date: str = ""):
    """Get referee assignments, optionally filtered by date (YYYY-MM-DD)."""
    conn = _conn()
    try:
        return _to_json(load_referee_assignments(conn, date=date or None))
    finally:
        conn.close()


# ── AI Chat ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    league: str = "NBA"
    message: str
    history: list = []


@app.post("/ai/chat", dependencies=[Depends(require_key)])
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

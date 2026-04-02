"""
app.py — Streamlit dashboard for CloudScout.

Multi-sport analytics: NBA and MLB. Switch sports with the sidebar selector.
Run with: streamlit run app.py
"""

import os

import anthropic
import streamlit as st
import pandas as pd
from nba_api.stats.static import teams as nba_teams

from database import init_db, load_games, load_players, load_mlb_players, load_injuries, load_referee_stats, load_referee_assignments
from scraper import scrape_team, scrape_injuries, fetch_todays_games, fetch_starters, scrape_referees
from mlb_scraper import scrape_mlb_team, get_all_mlb_teams, DEFAULT_SEASON as MLB_DEFAULT_SEASON
from analytics import (
    last_n_avg,
    head_to_head,
    rolling_form,
    player_avg,
    player_vs_team,
    top_performers,
    home_away_stats,
    win_streak,
    season_standings,
    win_probability,
    possible_injured_players,
    projected_total,
)
from mlb_analytics import (
    mlb_batter_avg,
    mlb_pitcher_avg,
    mlb_batter_vs_team,
    mlb_top_batters,
    mlb_top_pitchers,
    mlb_possible_injured_players,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="CloudScout", page_icon="🏟", layout="wide")
st.title("🏟 CloudScout")
st.caption("Multi-Sport Stats & Analytics Dashboard")

# ── Sport selector ────────────────────────────────────────────────────────────
sport = st.sidebar.radio("Sport", ["🏀 NBA", "⚾ MLB"], horizontal=True)
IS_MLB = sport == "⚾ MLB"
st.sidebar.divider()

# ── Team lists ────────────────────────────────────────────────────────────────
NBA_TEAMS = sorted([t["full_name"] for t in nba_teams.get_teams()])


@st.cache_data
def _mlb_teams():
    try:
        return get_all_mlb_teams()
    except Exception:
        return [
            "Arizona Diamondbacks", "Atlanta Braves", "Baltimore Orioles",
            "Boston Red Sox", "Chicago Cubs", "Chicago White Sox",
            "Cincinnati Reds", "Cleveland Guardians", "Colorado Rockies",
            "Detroit Tigers", "Houston Astros", "Kansas City Royals",
            "Los Angeles Angels", "Los Angeles Dodgers", "Miami Marlins",
            "Milwaukee Brewers", "Minnesota Twins", "New York Mets",
            "New York Yankees", "Athletics", "Philadelphia Phillies",
            "Pittsburgh Pirates", "San Diego Padres", "San Francisco Giants",
            "Seattle Mariners", "St. Louis Cardinals", "Tampa Bay Rays",
            "Texas Rangers", "Toronto Blue Jays", "Washington Nationals",
        ]


MLB_TEAMS = _mlb_teams()
ALL_TEAMS = MLB_TEAMS if IS_MLB else NBA_TEAMS

# ── Database connection & data load ──────────────────────────────────────────
conn = init_db()
games_df = load_games(conn, league="MLB" if IS_MLB else "NBA")
players_df = load_mlb_players(conn) if IS_MLB else load_players(conn)

# ── Sidebar: Settings ─────────────────────────────────────────────────────────
st.sidebar.header("Settings")
_max_games = 200 if IS_MLB else 100
num_games = st.sidebar.slider("Number of games", 1, _max_games, 10)
if IS_MLB:
    mlb_season = st.sidebar.slider("Season", 2020, 2026, MLB_DEFAULT_SEASON)

st.sidebar.divider()

# ── Sidebar: Scrape Data ──────────────────────────────────────────────────────
st.sidebar.header("Scrape Data")
scrape_team_name = st.sidebar.selectbox("Team to scrape", ALL_TEAMS, key="scrape_team")
_max_scrape = 200 if IS_MLB else 82
scrape_count = st.sidebar.slider("Games to scrape", 5, _max_scrape, 15, key="scrape_count")

if st.sidebar.button("Scrape Team"):
    with st.sidebar.status(f"Scraping {scrape_team_name}...", expanded=True):
        try:
            if IS_MLB:
                g, p = scrape_mlb_team(scrape_team_name, season=mlb_season, last=scrape_count)
            else:
                g, p = scrape_team(scrape_team_name, last=scrape_count)
            st.sidebar.success(f"Saved {len(g)} games, {len(p)} player lines.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
    conn.close()
    conn = init_db()
    games_df = load_games(conn, league="MLB" if IS_MLB else "NBA")
    players_df = load_mlb_players(conn) if IS_MLB else load_players(conn)

if st.sidebar.button("Scrape All Teams"):
    with st.sidebar.status(f"Scraping all {len(ALL_TEAMS)} teams...", expanded=True):
        for i, team in enumerate(ALL_TEAMS):
            st.write(f"[{i+1}/{len(ALL_TEAMS)}] {team}")
            try:
                if IS_MLB:
                    scrape_mlb_team(team, season=mlb_season, last=scrape_count)
                else:
                    scrape_team(team, last=scrape_count)
            except Exception as e:
                st.write(f"  Error: {e}")
        st.sidebar.success("All teams scraped!")
    conn.close()
    conn = init_db()
    games_df = load_games(conn, league="MLB" if IS_MLB else "NBA")
    players_df = load_mlb_players(conn) if IS_MLB else load_players(conn)

# ── Sidebar: Injury Report ───────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("Injury Report")
if st.sidebar.button("Refresh Injuries"):
    with st.sidebar.status("Fetching injury report from ESPN...", expanded=True):
        league_key = "MLB" if IS_MLB else "NBA"
        result = scrape_injuries(league_key)
        st.sidebar.success(f"Updated {len(result)} injury entries.")
    conn.close()
    conn = init_db()

injuries_df = load_injuries(conn, league="MLB" if IS_MLB else "NBA")
if not injuries_df.empty:
    out_count = len(injuries_df[injuries_df["status"].str.lower().isin(["out", "doubtful"])])
    st.sidebar.caption(f"{len(injuries_df)} players on report ({out_count} Out/Doubtful)")
else:
    st.sidebar.caption("No injury data — click Refresh to fetch.")

# ── Sidebar: Referee Data ────────────────────────────────────────────────────
if not IS_MLB:
    st.sidebar.divider()
    st.sidebar.header("Referee Data")
    if st.sidebar.button("Refresh Referees"):
        with st.sidebar.status("Fetching referee stats & assignments...", expanded=True):
            stats_n, assign_n = scrape_referees()
            st.sidebar.success(f"Updated {stats_n} ref stats, {assign_n} assignments.")
        conn.close()
        conn = init_db()

    ref_stats_df = load_referee_stats(conn)
    ref_assign_df = load_referee_assignments(conn)
    if not ref_stats_df.empty:
        st.sidebar.caption(f"{len(ref_stats_df)} referees tracked, {len(ref_assign_df)} assignments today")
    else:
        st.sidebar.caption("No referee data — click Refresh to fetch.")
else:
    ref_stats_df = pd.DataFrame()
    ref_assign_df = pd.DataFrame()

st.sidebar.divider()

# ── Sidebar: Watchlist ────────────────────────────────────────────────────────
st.sidebar.header("Watchlist")
wl_key = "mlb_watchlist" if IS_MLB else "nba_watchlist"
if wl_key not in st.session_state:
    st.session_state[wl_key] = []

wl_add = st.sidebar.selectbox("Add team to watchlist", [""] + ALL_TEAMS, key=f"wl_add_{sport}")
if st.sidebar.button("Add") and wl_add and wl_add not in st.session_state[wl_key]:
    st.session_state[wl_key].append(wl_add)

for wl_team in list(st.session_state[wl_key]):
    wl_col1, wl_col2 = st.sidebar.columns([3, 1])
    if not games_df.empty:
        tg = games_df[(games_df["home_team"] == wl_team) | (games_df["away_team"] == wl_team)]
        if not tg.empty:
            latest = tg.sort_values("date", ascending=False).iloc[0]
            is_home = latest["home_team"] == wl_team
            scored = latest["home_score"] if is_home else latest["away_score"]
            conceded = latest["away_score"] if is_home else latest["home_score"]
            result = "W" if scored > conceded else "L"
            sc, st_type = win_streak(wl_team, games_df)
            streak_str = f"{st_type}{sc}"
            color = "🟢" if result == "W" else "🔴"
            wl_col1.markdown(f"{color} **{wl_team.split()[-1]}** {int(scored)}-{int(conceded)} · {streak_str}")
        else:
            wl_col1.markdown(f"**{wl_team.split()[-1]}** — no data")
    else:
        wl_col1.markdown(f"**{wl_team}**")
    if wl_col2.button("✕", key=f"rm_{sport}_{wl_team}"):
        st.session_state[wl_key].remove(wl_team)
        st.rerun()

st.sidebar.divider()

if st.sidebar.button("Update All Teams", type="primary"):
    with st.sidebar.status("Checking for new games...", expanded=True):
        total_new = 0
        for i, team in enumerate(ALL_TEAMS):
            st.write(f"[{i+1}/{len(ALL_TEAMS)}] {team}")
            try:
                if IS_MLB:
                    g, _ = scrape_mlb_team(team, season=mlb_season, last=10)
                else:
                    g, _ = scrape_team(team, last=10)
                if not g.empty:
                    total_new += len(g)
                    st.write(f"  +{len(g)} new game(s)")
            except Exception as e:
                st.write(f"  Error: {e}")
        st.sidebar.success(f"Done! {total_new} new game(s) added.")
    conn.close()
    conn = init_db()
    games_df = load_games(conn, league="MLB" if IS_MLB else "NBA")
    players_df = load_mlb_players(conn) if IS_MLB else load_players(conn)

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_games, tab_team, tab_player, tab_pred, tab_top, tab_standings, tab_ai = st.tabs(
    ["Game Results", "Team Form", "Player Stats", "Predictions",
     "Top Performers", "Standings", "AI Scout"]
)

# ═════════════════════════════════════════════════════════════════════════════
# Tab 1: Game Results
# ═════════════════════════════════════════════════════════════════════════════
with tab_games:
    st.subheader("Game Results")
    team_filter = st.selectbox("Select team", ["All"] + ALL_TEAMS, key="games_team")

    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    else:
        filtered = games_df.copy()
        if team_filter != "All":
            filtered = filtered[
                (filtered["home_team"] == team_filter) | (filtered["away_team"] == team_filter)
            ]
        filtered = filtered.sort_values("date", ascending=False).head(num_games)

        if team_filter != "All" and not filtered.empty:
            score_label = "Score (R)" if IS_MLB else "Score"
            results = []
            for _, row in filtered.iterrows():
                is_home = row["home_team"] == team_filter
                opponent = row["away_team"] if is_home else row["home_team"]
                team_score = row["home_score"] if is_home else row["away_score"]
                opp_score = row["away_score"] if is_home else row["home_score"]
                results.append({
                    "Date": row["date"],
                    "Opponent": opponent,
                    "Result": "W" if team_score > opp_score else "L",
                    score_label: f"{team_score}-{opp_score}",
                    "Location": "Home" if is_home else "Away",
                })
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        else:
            st.dataframe(
                filtered[["date", "home_team", "away_team", "home_score", "away_score"]],
                use_container_width=True, hide_index=True,
            )

# ═════════════════════════════════════════════════════════════════════════════
# Tab 2: Team Form
# ═════════════════════════════════════════════════════════════════════════════
with tab_team:
    st.subheader("Team Form")
    team_sel = st.selectbox("Select team", ALL_TEAMS, key="form_team")

    scored_label = "Avg Runs" if IS_MLB else "Avg Scored"
    conceded_label = "Avg Allowed" if IS_MLB else "Avg Conceded"
    net_label = "Run Diff" if IS_MLB else "Net Rating"

    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    else:
        try:
            avg_df = last_n_avg(team_sel, num_games, games_df)
            streak_count, streak_type = win_streak(team_sel, games_df)
            avg_scored = avg_df["avg_scored"].iloc[0]
            avg_conceded = avg_df["avg_conceded"].iloc[0]
            avg_total = round(avg_scored + avg_conceded, 1)
            net = round(avg_scored - avg_conceded, 1)

            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("Games", int(avg_df["games"].iloc[0]))
            streak_label = f"{streak_type}{streak_count}"
            streak_color = "normal" if streak_type == "W" else "inverse"
            col2.metric("Streak", streak_label, delta=f"{streak_count} in a row", delta_color=streak_color)
            col3.metric(scored_label, avg_scored)
            col4.metric("Avg Total", avg_total)
            col5.metric(conceded_label, avg_conceded)
            col6.metric(net_label, f"{'+' if net >= 0 else ''}{net}")

            st.subheader("Rolling Form")
            form_df = rolling_form(team_sel, num_games, games_df)
            st.line_chart(form_df.set_index("date")["rolling_avg"])

            display_df = form_df.copy()
            display_df["margin"] = display_df["margin"].apply(
                lambda x: f"+{int(x)}" if x > 0 else str(int(x))
            )
            if IS_MLB:
                display_df.columns = ["Date", "Location", "Opponent", "W/L", "R", "RA", "Margin", "Rolling Avg"]
            else:
                display_df.columns = ["Date", "Location", "Opponent", "W/L", "Pts", "Opp Pts", "Margin", "Rolling Avg"]
            st.dataframe(display_df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
        except ValueError as e:
            st.warning(str(e))

# ═════════════════════════════════════════════════════════════════════════════
# Tab 3: Player Stats
# ═════════════════════════════════════════════════════════════════════════════
with tab_player:
    st.subheader("Player Stats")

    if players_df.empty:
        st.info("No player data yet. Use the sidebar to scrape some teams first.")
    elif IS_MLB:
        # ── MLB: separate Batters / Pitchers sub-tabs ─────────────────────
        batter_tab, pitcher_tab = st.tabs(["Batters", "Pitchers"])

        batters_df = players_df[players_df["role"] == "batter"]
        pitchers_df = players_df[players_df["role"] == "pitcher"]

        with batter_tab:
            search_query = st.text_input("Search batter", placeholder="e.g. Judge", key="batter_search")
            batter_names = sorted(batters_df["name"].unique().tolist())
            if search_query:
                batter_names = [n for n in batter_names if search_query.lower() in n.lower()]
            if not batter_names:
                st.warning("No batters match your search.")
            else:
                batter_sel = st.selectbox("Select batter", batter_names, key="batter_sel")

                # Injury watch
                batter_team_rows = batters_df[batters_df["name"] == batter_sel]
                if not batter_team_rows.empty:
                    batter_team = batter_team_rows.iloc[0]["team"]
                    injured = mlb_possible_injured_players(batter_team, players_df, games_df)
                    if batter_sel in injured:
                        st.warning(f"⚠️ {batter_sel} did not play in {batter_team}'s most recent game.")

                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("**Season Totals / Averages**")
                    try:
                        st.dataframe(mlb_batter_avg(batter_sel, num_games, players_df),
                                     use_container_width=True, hide_index=True)
                    except ValueError as e:
                        st.warning(str(e))

                with col_right:
                    st.markdown("**vs Specific Team**")
                    opp_sel = st.selectbox("Opponent", MLB_TEAMS, key="bvt_opp")
                    try:
                        pvt = mlb_batter_vs_team(batter_sel, opp_sel, num_games, players_df, games_df)
                        if pvt.empty:
                            st.info(f"No data for {batter_sel} vs {opp_sel}.")
                        else:
                            st.dataframe(pvt, use_container_width=True, hide_index=True)
                    except Exception as e:
                        st.warning(str(e))

                st.markdown("**Game Log**")
                log = batters_df[batters_df["name"] == batter_sel].sort_values("date", ascending=False).head(num_games)
                log = log.merge(games_df[["id", "home_team", "away_team"]], left_on="game_id", right_on="id", how="left")
                log["opponent"] = log.apply(
                    lambda r: r["away_team"] if r["team"] == r["home_team"] else r["home_team"], axis=1
                )
                st.dataframe(
                    log[["date", "opponent", "at_bats", "hits", "home_runs", "rbi", "runs", "walks", "strikeouts"]],
                    use_container_width=True, hide_index=True,
                )

        with pitcher_tab:
            search_query = st.text_input("Search pitcher", placeholder="e.g. Cole", key="pitcher_search")
            pitcher_names = sorted(pitchers_df["name"].unique().tolist())
            if search_query:
                pitcher_names = [n for n in pitcher_names if search_query.lower() in n.lower()]
            if not pitcher_names:
                st.warning("No pitchers match your search.")
            else:
                pitcher_sel = st.selectbox("Select pitcher", pitcher_names, key="pitcher_sel")

                st.markdown("**Season Stats**")
                try:
                    st.dataframe(mlb_pitcher_avg(pitcher_sel, num_games, players_df),
                                 use_container_width=True, hide_index=True)
                except ValueError as e:
                    st.warning(str(e))

                st.markdown("**Game Log**")
                log = pitchers_df[pitchers_df["name"] == pitcher_sel].sort_values("date", ascending=False).head(num_games)
                log = log.merge(games_df[["id", "home_team", "away_team"]], left_on="game_id", right_on="id", how="left")
                log["opponent"] = log.apply(
                    lambda r: r["away_team"] if r["team"] == r["home_team"] else r["home_team"], axis=1
                )
                st.dataframe(
                    log[["date", "opponent", "innings_pitched", "hits_allowed", "earned_runs",
                          "walks_allowed", "strikeouts_pitched", "home_runs_allowed"]],
                    use_container_width=True, hide_index=True,
                )

    else:
        # ── NBA player stats ──────────────────────────────────────────────
        search_query = st.text_input("Search player", placeholder="e.g. LeBron", key="player_search")
        player_names = sorted(players_df["name"].unique().tolist())
        if search_query:
            player_names = [n for n in player_names if search_query.lower() in n.lower()]
        if not player_names:
            st.warning("No players match your search.")
            st.stop()
        player_sel = st.selectbox("Select player", player_names, key="player_sel")

        player_team_rows = players_df[players_df["name"] == player_sel]
        if not player_team_rows.empty:
            player_team = player_team_rows.iloc[0]["team"]
            injured = possible_injured_players(player_team, players_df, games_df)
            if player_sel in injured:
                st.warning(f"⚠️ {player_sel} did not play in {player_team}'s most recent game — may be injured or resting.")

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("**Season Averages**")
            try:
                pavg = player_avg(player_sel, num_games, players_df)
                st.dataframe(pavg, use_container_width=True, hide_index=True)
            except ValueError as e:
                st.warning(str(e))

        with col_right:
            st.markdown("**vs Specific Team**")
            opponent_sel = st.selectbox("Opponent", NBA_TEAMS, key="pvt_opponent")
            try:
                pvt_df = player_vs_team(player_sel, opponent_sel, num_games, players_df, games_df)
                if pvt_df.empty:
                    st.info(f"No matchup data for {player_sel} vs {opponent_sel}.")
                else:
                    st.dataframe(pvt_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(str(e))

        st.markdown("**Game Log**")
        player_log = players_df[players_df["name"] == player_sel].sort_values("date", ascending=False).head(num_games)
        player_log = player_log.merge(
            games_df[["id", "home_team", "away_team"]], left_on="game_id", right_on="id", how="left"
        )
        player_log["opponent"] = player_log.apply(
            lambda row: row["away_team"] if row["team"] == row["home_team"] else row["home_team"], axis=1
        )
        st.dataframe(
            player_log[["date", "opponent", "points", "assists", "rebounds", "steals", "blocks", "turnovers", "minutes"]],
            use_container_width=True, hide_index=True,
        )

# ═════════════════════════════════════════════════════════════════════════════
# Tab 4: Predictions (win probability + H2H)
# ═════════════════════════════════════════════════════════════════════════════
with tab_pred:
    st.subheader("Predictions")
    col1, col2 = st.columns(2)
    h2h_team_a = col1.selectbox("Team A", ALL_TEAMS, index=0, key="h2h_a")
    h2h_team_b = col2.selectbox("Team B", ALL_TEAMS, index=1, key="h2h_b")

    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    elif h2h_team_a == h2h_team_b:
        st.warning("Please select two different teams.")
    else:
        # ── Season Record ─────────────────────────────────────────────────────
        def team_season_record(team, all_games):
            tg = all_games[(all_games["home_team"] == team) | (all_games["away_team"] == team)]
            if tg.empty:
                return None
            scored = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
            conceded = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
            wins = int((scored.values > conceded.values).sum())
            losses = len(tg) - wins
            streak_count, streak_type = win_streak(team, all_games)
            return {"wins": wins, "losses": losses, "win_pct": round(wins / len(tg) * 100, 1),
                    "streak": f"{streak_type}{streak_count}", "streak_type": streak_type}

        st.markdown("#### Season Record")
        rec_col1, rec_col2 = st.columns(2)
        for rec_col, team in [(rec_col1, h2h_team_a), (rec_col2, h2h_team_b)]:
            rec = team_season_record(team, games_df)
            with rec_col:
                if rec:
                    streak_color = "#2ea44f" if rec["streak_type"] == "W" else "#cf222e"
                    st.markdown(
                        f'<div style="background:#1c1c2e;border-radius:10px;padding:14px;">'
                        f'<div style="font-weight:700;font-size:15px;margin-bottom:8px;">{team}</div>'
                        f'<div style="font-size:13px;color:#8a8a9a;">{rec["wins"]}W – {rec["losses"]}L</div>'
                        f'<div style="font-size:13px;color:#8a8a9a;">{rec["win_pct"]}% win</div>'
                        f'<div style="font-size:13px;color:{streak_color};font-weight:600;">{rec["streak"]} streak</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        # ── Injury Report for Selected Teams ─────────────────────────────────
        if not IS_MLB and not injuries_df.empty:
            inj_a = injuries_df[injuries_df["team"] == h2h_team_a]
            inj_b = injuries_df[injuries_df["team"] == h2h_team_b]
            if not inj_a.empty or not inj_b.empty:
                st.markdown("#### Injury Report")
                inj_col1, inj_col2 = st.columns(2)
                for inj_col, team, inj_team_df in [(inj_col1, h2h_team_a, inj_a), (inj_col2, h2h_team_b, inj_b)]:
                    with inj_col:
                        if inj_team_df.empty:
                            st.markdown(f"**{team}** — All healthy ✅")
                        else:
                            st.markdown(f"**{team}** — {len(inj_team_df)} player(s)")
                            for _, row in inj_team_df.iterrows():
                                status = row["status"]
                                if status.lower() == "out":
                                    icon = "🔴"
                                elif status.lower() == "doubtful":
                                    icon = "🟠"
                                elif status.lower() in ("questionable", "day-to-day"):
                                    icon = "🟡"
                                else:
                                    icon = "⚪"
                                parts = []
                                if row.get("body_part") and str(row["body_part"]) != "nan":
                                    part_str = str(row["body_part"])
                                    if row.get("side") and str(row["side"]) != "nan":
                                        part_str = f"{row['side']} {part_str}"
                                    parts.append(part_str)
                                if row.get("detail") and str(row["detail"]) != "nan":
                                    parts.append(str(row["detail"]))
                                injury_desc = " — ".join(parts) if parts else ""
                                ret = row.get("return_date")
                                ret_str = f" · Est. return: {ret}" if ret and str(ret) != "nan" else ""
                                st.markdown(
                                    f"{icon} **{row['player_name']}** ({status})"
                                    f"{' — ' + injury_desc if injury_desc else ''}"
                                    f"{ret_str}"
                                )

        st.markdown("---")

        # ── Today's Games & Starters ─────────────────────────────────────────
        if not IS_MLB:
            todays_games = fetch_todays_games()
            # Find if the selected matchup is playing today
            matchup_game = None
            for tg in todays_games:
                if (h2h_team_a in tg["home_team_full"] or h2h_team_a in tg["away_team_full"]) and \
                   (h2h_team_b in tg["home_team_full"] or h2h_team_b in tg["away_team_full"]):
                    matchup_game = tg
                    break

            if matchup_game:
                st.markdown("#### Today's Matchup")
                st.markdown(
                    f"**{matchup_game['away_team_full']}** @ **{matchup_game['home_team_full']}** "
                    f"— {matchup_game['status']}"
                )
                # Show confirmed starters if game is live or completed
                if matchup_game["game_status"] >= 2:
                    starters = fetch_starters(matchup_game["game_id"])
                    if starters.get("home") or starters.get("away"):
                        st.markdown("**Confirmed Starters:**")
                        s_col1, s_col2 = st.columns(2)
                        with s_col1:
                            st.markdown(f"**{starters.get('away_team', 'Away')}**")
                            for s in starters.get("away", []):
                                st.markdown(f"- {s['name']} ({s['position']})")
                        with s_col2:
                            st.markdown(f"**{starters.get('home_team', 'Home')}**")
                            for s in starters.get("home", []):
                                st.markdown(f"- {s['name']} ({s['position']})")
                st.markdown("---")

        h2h_df = head_to_head(h2h_team_a, h2h_team_b, num_games, games_df)
        if h2h_df.empty:
            st.info(f"No head-to-head data between {h2h_team_a} and {h2h_team_b} in the database.")
        else:
            a_col = f"{h2h_team_a}_score"
            b_col = f"{h2h_team_b}_score"
            a_wins = (h2h_df["winner"] == h2h_team_a).sum()
            b_wins = (h2h_df["winner"] == h2h_team_b).sum()
            score_tip = "R" if IS_MLB else "pts"

            st.markdown("#### Recent Form (Last 5)")

            def wl_strip_overall(team, all_games):
                team_games = all_games[
                    (all_games["home_team"] == team) | (all_games["away_team"] == team)
                ].sort_values("date", ascending=False).head(5)
                boxes = []
                for _, row in team_games.iterrows():
                    is_home = row["home_team"] == team
                    scored = row["home_score"] if is_home else row["away_score"]
                    conceded = row["away_score"] if is_home else row["home_score"]
                    opponent = row["away_team"] if is_home else row["home_team"]
                    won = scored > conceded
                    diff = abs(scored - conceded)
                    color = "#2ea44f" if won else "#cf222e"
                    label = "W" if won else "L"
                    tip = f"{row['date']} vs {opponent}: {int(scored)}-{int(conceded)}"
                    total = int(scored) + int(conceded)
                    boxes.append(
                        f'<span title="{tip}" style="display:inline-flex;flex-direction:column;'
                        f'align-items:center;justify-content:center;width:64px;height:74px;'
                        f'background:{color};border-radius:6px;margin:3px;'
                        f'color:white;font-weight:bold;">'
                        f'<span style="font-size:15px;">{label}</span>'
                        f'<span style="font-size:12px;">{int(scored)}-{int(conceded)}</span>'
                        f'<span style="font-size:10px;opacity:0.75;">{total}</span>'
                        f'<span style="font-size:10px;opacity:0.85;">{("+" if won else "-")}{diff}</span>'
                        f'</span>'
                    )
                return "".join(boxes)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{h2h_team_a}**")
                st.markdown(wl_strip_overall(h2h_team_a, games_df), unsafe_allow_html=True)
            with col2:
                st.markdown(f"**{h2h_team_b}**")
                st.markdown(wl_strip_overall(h2h_team_b, games_df), unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### H2H Summary")
            avg_diff_a = round((h2h_df[a_col] - h2h_df[b_col]).mean(), 1)
            avg_diff_b = round((h2h_df[b_col] - h2h_df[a_col]).mean(), 1)

            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            col1.metric(f"{h2h_team_a} Wins", int(a_wins))
            col2.metric(f"Avg {score_tip}", round(h2h_df[a_col].mean(), 1))
            col3.metric("Avg Margin", f"{'+' if avg_diff_a >= 0 else ''}{avg_diff_a}")
            col4.metric("Avg Total", round((h2h_df[a_col] + h2h_df[b_col]).mean(), 1))
            col5.metric(f"{h2h_team_b} Wins", int(b_wins))
            col6.metric(f"Avg {score_tip}", round(h2h_df[b_col].mean(), 1))
            col7.metric("Avg Margin", f"{'+' if avg_diff_b >= 0 else ''}{avg_diff_b}")

            st.markdown("---")
            st.markdown("#### Season Averages")

            def season_avg(team, all_games):
                tg = all_games[(all_games["home_team"] == team) | (all_games["away_team"] == team)]
                if tg.empty:
                    return None
                scored = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
                conceded = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
                wins = (scored.values > conceded.values).sum()
                return {
                    "games": len(tg),
                    "avg_scored": round(scored.mean(), 1),
                    "avg_conceded": round(conceded.mean(), 1),
                    "win_pct": round(wins / len(tg) * 100, 1),
                }

            sa = season_avg(h2h_team_a, games_df)
            sb = season_avg(h2h_team_b, games_df)

            if sa and sb:
                scored_stat_label = "Avg Runs Scored" if IS_MLB else "Avg Points Scored"
                conceded_stat_label = "Avg Runs Allowed" if IS_MLB else "Avg Points Conceded"
                stats_config = [
                    (scored_stat_label, "avg_scored", True),
                    (conceded_stat_label, "avg_conceded", False),
                    ("Win %", "win_pct", True),
                    ("Games Played", "games", None),
                ]
                header_cols = st.columns([2, 1, 1])
                header_cols[0].markdown("**Stat**")
                header_cols[1].markdown(f"**{h2h_team_a}**")
                header_cols[2].markdown(f"**{h2h_team_b}**")

                for label, key, higher_is_better in stats_config:
                    val_a = sa[key]
                    val_b = sb[key]
                    if higher_is_better is None or val_a == val_b:
                        color_a = color_b = "#ffffff00"
                    elif higher_is_better:
                        color_a = "#2ea44f22" if val_a > val_b else "#ffffff00"
                        color_b = "#2ea44f22" if val_b > val_a else "#ffffff00"
                    else:
                        color_a = "#2ea44f22" if val_a < val_b else "#ffffff00"
                        color_b = "#2ea44f22" if val_b < val_a else "#ffffff00"

                    disp_a = f"{val_a}%" if key == "win_pct" else val_a
                    disp_b = f"{val_b}%" if key == "win_pct" else val_b

                    row_cols = st.columns([2, 1, 1])
                    row_cols[0].markdown(label)
                    row_cols[1].markdown(
                        f'<div style="background:{color_a};padding:4px 8px;border-radius:4px;">{disp_a}</div>',
                        unsafe_allow_html=True,
                    )
                    row_cols[2].markdown(
                        f'<div style="background:{color_b};padding:4px 8px;border-radius:4px;">{disp_b}</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
            st.markdown("#### Home & Away Performance (Overall)")
            col1, col2 = st.columns(2)
            for col, team in [(col1, h2h_team_a), (col2, h2h_team_b)]:
                stats = home_away_stats(team, games_df)
                with col:
                    st.markdown(f"**{team}**")
                    if stats:
                        ha_df = pd.DataFrame([
                            {"Location": "Home", "Games": stats["home"]["games"],
                             "Avg Scored": stats["home"]["avg_scored"],
                             "Avg Conceded": stats["home"]["avg_conceded"],
                             "Win %": f"{stats['home']['win_pct']}%"},
                            {"Location": "Away", "Games": stats["away"]["games"],
                             "Avg Scored": stats["away"]["avg_scored"],
                             "Avg Conceded": stats["away"]["avg_conceded"],
                             "Win %": f"{stats['away']['win_pct']}%"},
                        ])
                        st.dataframe(ha_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No data available.")

            st.markdown("---")
            st.markdown("#### Full Game Log")
            st.dataframe(h2h_df, use_container_width=True, hide_index=True)
            _, center, _ = st.columns([1, 1, 1])
            avg_total = round((h2h_df[a_col] + h2h_df[b_col]).mean(), 1)
            center.metric(f"Avg Game Total {'Runs' if IS_MLB else 'Points'}", avg_total)

    # ── Win Probability ───────────────────────────────────────────────────────
    if not games_df.empty and h2h_team_a != h2h_team_b:
        st.markdown("---")
        st.markdown("#### Win Probability")
        col1, col2, col3 = st.columns(3)
        home_options = ["Neutral", h2h_team_a, h2h_team_b]
        pred_home = col3.selectbox("Home team", home_options, key="pred_home")
        home_team_val = None if pred_home == "Neutral" else pred_home
        _logit_scale = 3.5 if IS_MLB else 6.0
        prob_a, prob_b, margin = win_probability(h2h_team_a, h2h_team_b, games_df, home_team=home_team_val, pts_per_logit=_logit_scale)

        pc1, pc2 = st.columns(2)
        fav_color_a = "#2ea44f" if prob_a >= prob_b else "#cf222e"
        fav_color_b = "#2ea44f" if prob_b > prob_a else "#cf222e"
        pc1.markdown(
            f'<div style="background:{fav_color_a};padding:16px;border-radius:8px;text-align:center;">'
            f'<div style="font-size:2rem;font-weight:bold;color:white;">{prob_a}%</div>'
            f'<div style="color:white;">{h2h_team_a}</div></div>', unsafe_allow_html=True
        )
        pc2.markdown(
            f'<div style="background:{fav_color_b};padding:16px;border-radius:8px;text-align:center;">'
            f'<div style="font-size:2rem;font-weight:bold;color:white;">{prob_b}%</div>'
            f'<div style="color:white;">{h2h_team_b}</div></div>', unsafe_allow_html=True
        )

        spread_label = "Predicted Run Line" if IS_MLB else "Predicted Spread"
        spread_unit = "runs" if IS_MLB else "pts"
        st.markdown("---")
        st.markdown(f"#### {spread_label}")
        if margin > 0:
            st.info(f"**{h2h_team_a}** favored by **{abs(margin)} {spread_unit}**")
        elif margin < 0:
            st.info(f"**{h2h_team_b}** favored by **{abs(margin)} {spread_unit}**")
        else:
            st.info("Pick 'em — no advantage detected.")

    # ── Referee Assignment ────────────────────────────────────────────────────
    if not IS_MLB and not ref_assign_df.empty and h2h_team_a != h2h_team_b:
        team_a_parts = [w for w in h2h_team_a.lower().split() if len(w) > 3]
        team_b_parts = [w for w in h2h_team_b.lower().split() if len(w) > 3]
        matched = ref_assign_df[
            ref_assign_df["game_matchup"].str.lower().apply(
                lambda m: any(w in m for w in team_a_parts) and any(w in m for w in team_b_parts)
            )
        ]
        if not matched.empty:
            st.markdown("---")
            st.markdown("#### Tonight's Referee Crew")
            crew = matched[["referee_name", "role"]].values.tolist()
            role_order = {"Crew Chief": 0, "Referee": 1, "Umpire": 2}
            crew.sort(key=lambda x: role_order.get(x[1], 9))
            cols = st.columns(len(crew))
            for col, (name, role) in zip(cols, crew):
                # Look up this ref's stats
                if not ref_stats_df.empty:
                    rs = ref_stats_df[ref_stats_df["name"].str.strip().str.lower() == name.strip().lower()]
                    if rs.empty:
                        last = name.strip().split()[-1].lower()
                        rs = ref_stats_df[ref_stats_df["name"].str.strip().str.split().str[-1].str.lower() == last]
                    if not rs.empty:
                        r = rs.iloc[0]
                        ppg = f"{r['total_ppg']:.1f} PPG" if pd.notna(r.get("total_ppg")) else ""
                        fpg = f"{r['fouls_per_game']:.1f} FPG" if pd.notna(r.get("fouls_per_game")) else ""
                        col.metric(label=f"{role}", value=name, delta=f"{ppg}  {fpg}".strip())
                    else:
                        col.metric(label=f"{role}", value=name)
                else:
                    col.metric(label=f"{role}", value=name)

    # ── Projected Over/Under Total (NBA only) ────────────────────────────────
    if not IS_MLB and not games_df.empty and h2h_team_a != h2h_team_b:
        players_df_full = load_players(conn)
        if not players_df_full.empty:
            st.markdown("---")
            st.markdown("#### Projected Total (Over/Under)")
            proj = projected_total(
                h2h_team_a, h2h_team_b, games_df, players_df_full,
                home_team=home_team_val if 'home_team_val' in dir() else None, n=10,
                injuries_df=injuries_df,
                referee_stats_df=ref_stats_df,
                referee_assignments_df=ref_assign_df,
            )
            if "error" in proj:
                st.warning(proj["error"])
            else:
                # ── AI Formula: (avg_pts_a + avg_pts_b + avg_allowed_a + avg_allowed_b) / 2 + home bump ──
                try:
                    _avg_a = last_n_avg(h2h_team_a, 10, games_df).iloc[0]
                    _avg_b = last_n_avg(h2h_team_b, 10, games_df).iloc[0]
                    _ai_raw = (
                        _avg_a["avg_scored"] + _avg_b["avg_scored"]
                        + _avg_a["avg_conceded"] + _avg_b["avg_conceded"]
                    ) / 2
                    _home_bump = 2.5 if home_team_val else 0.0
                    _ai_total = round(_ai_raw + _home_bump, 1)
                except Exception:
                    _ai_total = None

                # Side-by-side display
                col_scout, col_ai = st.columns(2)
                with col_scout:
                    st.markdown(
                        f'<div style="background:#1a1a2e;padding:20px;border-radius:10px;text-align:center;'
                        f'border:2px solid #6c5ce7;margin-bottom:16px;">'
                        f'<div style="font-size:2.5rem;font-weight:bold;color:#6c5ce7;">{proj["projected_total"]}</div>'
                        f'<div style="color:#a0a0a0;font-size:0.85rem;">Scout Model</div></div>',
                        unsafe_allow_html=True,
                    )
                with col_ai:
                    _ai_display = str(_ai_total) if _ai_total is not None else "N/A"
                    st.markdown(
                        f'<div style="background:#1a1a2e;padding:20px;border-radius:10px;text-align:center;'
                        f'border:2px solid #00b894;margin-bottom:16px;">'
                        f'<div style="font-size:2.5rem;font-weight:bold;color:#00b894;">{_ai_display}</div>'
                        f'<div style="color:#a0a0a0;font-size:0.85rem;">AI Formula</div></div>',
                        unsafe_allow_html=True,
                    )

                # Step-by-step breakdown
                steps = proj["steps"]
                with st.expander("Step-by-step breakdown", expanded=True):
                    # Step 1 — Base Total
                    s1 = steps["step_1_base"]
                    st.markdown(
                        f"**Step 1 — Base Total**<br>"
                        f"Pace: {h2h_team_a} **{s1['pace_a']}** | {h2h_team_b} **{s1['pace_b']}** "
                        f"→ Poss: **{s1['expected_possessions']}**<br>"
                        f"ORtg/DRtg: {h2h_team_a} **{s1['ortg_a']}/{s1['drtg_a']}** | "
                        f"{h2h_team_b} **{s1['ortg_b']}/{s1['drtg_b']}** → "
                        f"Exp ORtg: **{s1['exp_ortg_a']}** / **{s1['exp_ortg_b']}**<br>"
                        f"Base total = {s1['expected_possessions']} x "
                        f"({s1['exp_ortg_a']} + {s1['exp_ortg_b']}) / 100 = **{s1['base_total']}**",
                        unsafe_allow_html=True,
                    )

                    # Step 2 — Shooting
                    s2 = steps["step_2_shooting"]
                    if s2.get("skipped"):
                        st.markdown(f"**Step 2 — Shooting** — _Skipped: {s2.get('reason', 'missing data')}_")
                    else:
                        st.markdown(
                            f"**Step 2 — Shooting** — "
                            f"eFG%: **{s2['efg_a']}%** / **{s2['efg_b']}%** (lg avg {s2['league_avg_efg']}%) · "
                            f"Opp eFG%: **{s2['opp_efg_a']}%** / **{s2['opp_efg_b']}%** · "
                            f"Matchup: **{s2['matchup_efg_a']}%** / **{s2['matchup_efg_b']}%** → "
                            f"**{s2['adjustment']:+.1f}** pts"
                        )

                    # Step 3 — Turnovers
                    s3 = steps["step_3_turnovers"]
                    if s3.get("skipped"):
                        st.markdown("**Step 3 — Turnovers** — _Skipped_")
                    else:
                        st.markdown(
                            f"**Step 3 — Turnovers** — "
                            f"TOV%: **{s3['tov_rate_a']}%** / **{s3['tov_rate_b']}%** (lg avg {s3['league_avg_tov']}%) → "
                            f"**{s3['adjustment']:+.1f}** pts"
                        )

                    # Step 4 — Free Throws
                    s4 = steps["step_4_free_throws"]
                    if s4.get("skipped"):
                        st.markdown("**Step 4 — Free Throws** — _Skipped_")
                    else:
                        st.markdown(
                            f"**Step 4 — Free Throws** — "
                            f"FT Rate: **{s4['ft_rate_a']}%** / **{s4['ft_rate_b']}%** (lg avg {s4['league_avg_ft_rate']}%) → "
                            f"**{s4['adjustment']:+.1f}** pts"
                        )

                    # Step 5 — Rest & Travel
                    s5 = steps["step_5_rest"]
                    rest_a_str = f"{s5['rest_days_a']}d" if s5['rest_days_a'] is not None else "?"
                    rest_b_str = f"{s5['rest_days_b']}d" if s5['rest_days_b'] is not None else "?"
                    note_a = f" ({s5['rest_note_a']})" if s5.get("rest_note_a") else ""
                    note_b = f" ({s5['rest_note_b']})" if s5.get("rest_note_b") else ""
                    st.markdown(
                        f"**Step 5 — Rest & Travel** — "
                        f"{h2h_team_a} **{rest_a_str}**{note_a} | "
                        f"{h2h_team_b} **{rest_b_str}**{note_b} → "
                        f"**{s5['adjustment']:+.1f}** pts"
                    )

                    # Step 6 — Home Court & Altitude
                    s6 = steps["step_6_home_court"]
                    alt_str = f" (altitude +{s6['altitude_adj']})" if s6.get("altitude_adj") else ""
                    st.markdown(
                        f"**Step 6 — Home Court** — "
                        f"**{s6['home_team']}**{alt_str} → **{s6['adjustment']:+.1f}** pts"
                    )

                    # Step 7 — Recent Form
                    s7 = steps["step_7_form"]
                    if s7.get("skipped"):
                        st.markdown("**Step 7 — Recent Form** — _Skipped: not enough season data_")
                    else:
                        st.markdown(
                            f"**Step 7 — Recent Form** — "
                            f"{h2h_team_a}: ORtg **{s7['recent_ortg_a']}** vs season **{s7['season_ortg_a']}** "
                            f"(Δ **{s7['form_delta_a']:+.1f}**) | "
                            f"{h2h_team_b}: **{s7['recent_ortg_b']}** vs **{s7['season_ortg_b']}** "
                            f"(Δ **{s7['form_delta_b']:+.1f}**) → "
                            f"**{s7['adjustment']:+.1f}** pts"
                        )

                    # Step 8 — Injuries
                    s8 = steps["step_8_injuries"]
                    if s8.get("skipped"):
                        st.markdown(f"**Step 8 — Injuries** — _No injury data — click Refresh Injuries in sidebar_")
                    else:
                        st.markdown(f"**Step 8 — Injuries** → **{s8['adjustment']:+.1f}** pts")
                        _tier_colors = {"Star": "#e74c3c", "Starter": "#e67e22", "Bench": "#95a5a6", "Unknown": "#7f8c8d"}
                        for side_label, side_key in [
                            (h2h_team_a, "injured_out_a"),
                            (h2h_team_b, "injured_out_b"),
                        ]:
                            injured_list = s8.get(side_key, [])
                            if not injured_list:
                                continue
                            impactful = [p for p in injured_list if p.get("impact_pts", 0) > 0]
                            if not impactful:
                                continue
                            lines = [f"**{side_label}** ({len(impactful)} with impact):"]
                            for ip in sorted(impactful, key=lambda x: x.get("impact_pts", 0), reverse=True):
                                tier = ip.get("tier", "?")
                                tc = _tier_colors.get(tier, "#95a5a6")
                                miss = ip.get("miss_prob", 1.0)
                                miss_str = f" · {int(miss*100)}% miss" if miss < 1.0 else ""
                                lines.append(
                                    f'<span style="color:{tc};font-weight:700;">[{tier}]</span> '
                                    f"**{ip['name']}** ({ip['status']}) — "
                                    f"**{ip['avg_ppg']} PPG** / {ip.get('avg_apg',0)} APG / {ip.get('minutes',0)} min → "
                                    f"**-{ip['impact_pts']:.1f} pts**{miss_str}"
                                )
                            st.markdown("<br>".join(lines), unsafe_allow_html=True)

                    # Step 9 — Referees
                    s9 = steps["step_9_referees"]
                    if s9.get("skipped"):
                        st.markdown(f"**Step 9 — Referees** — _{s9.get('reason', 'No data')}_")
                    else:
                        ref_lines = [
                            f"**Step 9 — Referees** (lg avg {s9['league_avg_ppg']} PPG) → **{s9['adjustment']:+.1f}** pts"
                        ]
                        for r in s9.get("refs", []):
                            fpg = f" · {r['fouls_pg']} FPG" if r.get("fouls_pg") else ""
                            games = f" · {r['games']}G" if r.get("games") else ""
                            ref_lines.append(
                                f"**{r['name']}** — **{r['total_ppg']} PPG** "
                                f"(Δ **{r['delta']:+.1f}**){fpg}{games}"
                            )
                        st.markdown("<br>".join(ref_lines), unsafe_allow_html=True)

                    # Step 10 — Rebounds
                    s10 = steps["step_10_rebounds"]
                    if s10.get("skipped"):
                        st.markdown("**Step 10 — Rebounds** — _Skipped_")
                    else:
                        st.markdown(
                            f"**Step 10 — Rebounds** — "
                            f"OREB%: **{s10['oreb_pct_a']}%** / **{s10['oreb_pct_b']}%** "
                            f"(lg avg {s10['league_avg_oreb']}%) → "
                            f"**{s10['adjustment']:+.1f}** pts"
                        )

                    # Step 11 — Motivation
                    s11 = steps["step_11_motivation"]
                    rivalry_str = " · 🔥 Rivalry game (+1.0)" if s11.get("is_rivalry") else ""
                    st.markdown(
                        f"**Step 11 — Motivation** — "
                        f"{h2h_team_a}: _{s11['team_a_context']}_ | "
                        f"{h2h_team_b}: _{s11['team_b_context']}_"
                        f"{rivalry_str} → "
                        f"**{s11['adjustment']:+.1f}** pts"
                    )

                    # Final summary
                    f = steps["final"]
                    st.markdown(
                        f"**Final** — "
                        f"**{f['base_total']}** (base) "
                        f"**{f['shooting_adj']:+.1f}** (shoot) "
                        f"**{f['tov_adj']:+.1f}** (TOV) "
                        f"**{f['ft_adj']:+.1f}** (FT) "
                        f"**{f['rest_adj']:+.1f}** (rest) "
                        f"**{f['home_adj']:+.1f}** (home) "
                        f"**{f['form_adj']:+.1f}** (form) "
                        f"**{f['injury_adj']:+.1f}** (inj) "
                        f"**{f['ref_adj']:+.1f}** (ref) "
                        f"**{f['oreb_adj']:+.1f}** (reb) "
                        f"**{f['motivation_adj']:+.1f}** (mot) "
                        f"= **{f['projected_total']}**"
                    )

# ═════════════════════════════════════════════════════════════════════════════
# Tab 5: Top Performers
# ═════════════════════════════════════════════════════════════════════════════
with tab_top:
    st.subheader("Top Performers")
    top_team = st.selectbox("Select team", ALL_TEAMS, key="top_team")

    if players_df.empty:
        st.info("No player data yet. Use the sidebar to scrape some teams first.")
    elif IS_MLB:
        bat_col, pitch_col = st.columns(2)

        with bat_col:
            st.markdown("#### Top Batters")
            top_bat = mlb_top_batters(top_team, num_games, players_df, games_df)
            if top_bat.empty:
                st.info(f"No batter data for {top_team}.")
            else:
                chart_data = top_bat.head(10).set_index("player")
                st.bar_chart(chart_data["HR"])
                st.dataframe(top_bat, use_container_width=True, hide_index=True)

        with pitch_col:
            st.markdown("#### Top Pitchers")
            top_pitch = mlb_top_pitchers(top_team, num_games, players_df, games_df)
            if top_pitch.empty:
                st.info(f"No pitcher data for {top_team}.")
            else:
                st.dataframe(top_pitch, use_container_width=True, hide_index=True)
    else:
        top_df = top_performers(top_team, num_games, players_df, games_df)
        if top_df.empty:
            st.info(f"No player data for {top_team}. Try scraping this team first.")
        else:
            chart_df = top_df.head(10).set_index("player")
            st.bar_chart(chart_df["avg_points"])
            st.dataframe(top_df, use_container_width=True, hide_index=True)

# ═════════════════════════════════════════════════════════════════════════════
# Tab 6: Standings
# ═════════════════════════════════════════════════════════════════════════════
with tab_standings:
    st.subheader("Standings")
    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    else:
        standings_df = season_standings(games_df)
        net_col = "Net Rtg" if not IS_MLB else "Net Rtg"  # "Run Diff" is same column

        def color_net(val):
            color = "#2ea44f" if val > 0 else ("#cf222e" if val < 0 else "")
            return f"color: {color}; font-weight: bold" if color else ""

        styled = standings_df.style.applymap(color_net, subset=["Net Rtg"])
        table_height = (len(standings_df) + 1) * 35 + 3
        st.dataframe(styled, use_container_width=True, hide_index=True, height=table_height)

# ═════════════════════════════════════════════════════════════════════════════
# Tab 7: AI Scout
# ═════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.subheader("AI Scout")
    sport_label = "MLB" if IS_MLB else "NBA"
    st.caption(f"Ask anything about the {sport_label} teams and players in your database.")

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        st.warning("Set your `ANTHROPIC_API_KEY` environment variable to use AI Scout.")
        st.code("export ANTHROPIC_API_KEY='sk-ant-...'", language="bash")
    else:
        ai_key = f"{'mlb' if IS_MLB else 'nba'}_ai_messages"
        if ai_key not in st.session_state:
            st.session_state[ai_key] = []

        for msg in st.session_state[ai_key]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if prompt := st.chat_input(f"Ask about {sport_label} teams, players, or matchups..."):
            st.session_state[ai_key].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

            context_parts = []

            if not games_df.empty:
                recent = games_df.sort_values("date", ascending=False).head(30)
                context_parts.append(
                    "Recent games:\n" +
                    recent[["date", "home_team", "away_team", "home_score", "away_score"]].to_string(index=False)
                )
                standings = season_standings(games_df)
                context_parts.append("Standings:\n" + standings.to_string(index=False))

            if not players_df.empty:
                if IS_MLB:
                    batters = players_df[players_df["role"] == "batter"]
                    top_bat = (
                        batters.groupby("name")
                        .agg(HR=("home_runs", "sum"), RBI=("rbi", "sum"),
                             H=("hits", "sum"), AB=("at_bats", "sum"))
                        .reset_index()
                    )
                    top_bat["AVG"] = top_bat.apply(
                        lambda r: round(r["H"] / r["AB"], 3) if r["AB"] > 0 else 0.0, axis=1
                    )
                    top_bat = top_bat.sort_values("HR", ascending=False).head(20).round(3)
                    context_parts.append("Top batters (by HR):\n" + top_bat.to_string(index=False))

                    pitchers = players_df[players_df["role"] == "pitcher"]
                    top_pitch = (
                        pitchers.groupby("name")
                        .agg(IP=("innings_pitched", "sum"), ER=("earned_runs", "sum"),
                             SO=("strikeouts_pitched", "sum"), BB=("walks_allowed", "sum"))
                        .reset_index()
                    )
                    top_pitch["ERA"] = top_pitch.apply(
                        lambda r: round(r["ER"] / r["IP"] * 9, 2) if r["IP"] > 0 else 0.0, axis=1
                    )
                    top_pitch = top_pitch[top_pitch["IP"] >= 5].sort_values("ERA").head(20)
                    context_parts.append("Top pitchers (by ERA):\n" + top_pitch.to_string(index=False))
                else:
                    top_scorers = (
                        players_df.groupby("name")
                        .agg(avg_pts=("points", "mean"), avg_reb=("rebounds", "mean"),
                             avg_ast=("assists", "mean"), games=("game_id", "count"))
                        .sort_values("avg_pts", ascending=False)
                        .head(30)
                        .round(1)
                    )
                    context_parts.append("Top scorers:\n" + top_scorers.to_string())

            context = "\n\n".join(context_parts) if context_parts else "No data in the database yet."
            full_prompt = f"Database stats:\n{context}\n\nQuestion: {prompt}"

            system_prompt = (
                f"You are AI Scout, an expert {sport_label} analyst. Answer questions using only the stats "
                f"data provided. Be concise and insightful. If something isn't in the data, say so."
            )

            with st.chat_message("assistant"):
                client = anthropic.Anthropic(api_key=api_key)
                with client.messages.stream(
                    model="claude-opus-4-6",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{"role": "user", "content": full_prompt}],
                ) as stream:
                    response_text = st.write_stream(stream.text_stream)

            st.session_state[ai_key].append({"role": "assistant", "content": response_text})

# ── Close DB ──────────────────────────────────────────────────────────────────
conn.close()

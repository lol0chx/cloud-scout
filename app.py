"""
app.py — Streamlit dashboard for CloudScout.

Provides a web-based UI for browsing NBA game results, player stats,
head-to-head matchups, and team performance analytics.

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from nba_api.stats.static import teams as nba_teams

from database import init_db, load_games, load_players
from scraper import scrape_team, _resolve_team
from analytics import (
    last_n_avg,
    head_to_head,
    rolling_form,
    player_avg,
    player_vs_team,
    top_performers,
)

# Page config
st.set_page_config(page_title="CloudScout", page_icon="🏀", layout="wide")
st.title("🏀 CloudScout")
st.caption("NBA Stats Scraper & Analytics Dashboard")

# Build team list from nba_api static data
ALL_TEAMS = sorted([t["full_name"] for t in nba_teams.get_teams()])

# Initialize database connection
conn = init_db()

# --- Sidebar ---
st.sidebar.header("Settings")
num_games = st.sidebar.slider("Number of games", 1, 100, 10)

st.sidebar.divider()
st.sidebar.header("Scrape Data")
scrape_team_name = st.sidebar.selectbox("Team to scrape", ALL_TEAMS, key="scrape_team")
scrape_count = st.sidebar.slider("Games to scrape", 5, 50, 15, key="scrape_count")

if st.sidebar.button("Scrape Team"):
    with st.sidebar.status(f"Scraping {scrape_team_name}...", expanded=True):
        try:
            games_df, players_df = scrape_team(scrape_team_name, last=scrape_count)
            st.sidebar.success(f"Saved {len(games_df)} games, {len(players_df)} player lines.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
    # Refresh connection to pick up new data
    conn.close()
    conn = init_db()

if st.sidebar.button("Scrape All Teams"):
    with st.sidebar.status("Scraping all 30 teams...", expanded=True):
        for i, team in enumerate(ALL_TEAMS):
            st.write(f"[{i+1}/30] {team}")
            try:
                scrape_team(team, last=scrape_count)
            except Exception as e:
                st.write(f"  Error: {e}")
        st.sidebar.success("All teams scraped!")
    conn.close()
    conn = init_db()

st.sidebar.divider()
if st.sidebar.button("Update All Teams", type="primary"):
    with st.sidebar.status("Checking for new games...", expanded=True):
        total_new_games = 0
        for i, team in enumerate(ALL_TEAMS):
            st.write(f"[{i+1}/30] {team}")
            try:
                games_new, _ = scrape_team(team, last=5)
                if not games_new.empty:
                    total_new_games += len(games_new)
                    st.write(f"  +{len(games_new)} new game(s)")
            except Exception as e:
                st.write(f"  Error: {e}")
        st.sidebar.success(f"Done! {total_new_games} new game(s) added.")
    conn.close()
    conn = init_db()

# --- Load data ---
games_df = load_games(conn)
players_df = load_players(conn)

# --- Main tabs ---
tab_games, tab_team, tab_player, tab_h2h, tab_top = st.tabs(
    ["Game Results", "Team Form", "Player Stats", "Head-to-Head", "Top Performers"]
)

# --- Tab 1: Game Results ---
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
            # Add W/L, score, and location columns
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
                    "Score": f"{team_score}-{opp_score}",
                    "Location": "Home" if is_home else "Away",
                })
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        else:
            st.dataframe(
                filtered[["date", "home_team", "away_team", "home_score", "away_score"]],
                use_container_width=True, hide_index=True,
            )

# --- Tab 2: Team Form ---
with tab_team:
    st.subheader("Team Form")
    team_sel = st.selectbox("Select team", ALL_TEAMS, key="form_team")

    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    else:
        try:
            # Averages
            avg_df = last_n_avg(team_sel, num_games, games_df)
            col1, col2, col3 = st.columns(3)
            col1.metric("Games", int(avg_df["games"].iloc[0]))
            col2.metric("Avg Scored", avg_df["avg_scored"].iloc[0])
            col3.metric("Avg Conceded", avg_df["avg_conceded"].iloc[0])

            # Rolling form chart
            st.subheader("Rolling Form")
            form_df = rolling_form(team_sel, num_games, games_df)
            st.line_chart(form_df.set_index("date")["rolling_avg"])

            # Rolling form table
            st.dataframe(form_df, use_container_width=True, hide_index=True)
        except ValueError as e:
            st.warning(str(e))

# --- Tab 3: Player Stats ---
with tab_player:
    st.subheader("Player Stats")

    if players_df.empty:
        st.info("No player data yet. Use the sidebar to scrape some teams first.")
    else:
        # Get unique player names for the dropdown
        player_names = sorted(players_df["name"].unique().tolist())
        player_sel = st.selectbox("Select player", player_names, key="player_sel")

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
            opponent_sel = st.selectbox("Opponent", ALL_TEAMS, key="pvt_opponent")
            try:
                pvt_df = player_vs_team(player_sel, opponent_sel, num_games, players_df, games_df)
                if pvt_df.empty:
                    st.info(f"No matchup data for {player_sel} vs {opponent_sel}.")
                else:
                    st.dataframe(pvt_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(str(e))

        # Game log — join with games data to show the opponent
        st.markdown("**Game Log**")
        player_log = players_df[players_df["name"] == player_sel].sort_values("date", ascending=False).head(num_games)
        player_log = player_log.merge(
            games_df[["id", "home_team", "away_team"]],
            left_on="game_id", right_on="id", how="left",
        )
        player_log["opponent"] = player_log.apply(
            lambda row: row["away_team"] if row["team"] == row["home_team"] else row["home_team"],
            axis=1,
        )
        st.dataframe(
            player_log[["date", "opponent", "points", "assists", "rebounds", "steals", "blocks", "turnovers", "minutes"]],
            use_container_width=True, hide_index=True,
        )

# --- Tab 4: Head-to-Head ---
with tab_h2h:
    st.subheader("Head-to-Head")
    col1, col2 = st.columns(2)
    h2h_team_a = col1.selectbox("Team A", ALL_TEAMS, index=0, key="h2h_a")
    h2h_team_b = col2.selectbox("Team B", ALL_TEAMS, index=1, key="h2h_b")

    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    elif h2h_team_a == h2h_team_b:
        st.warning("Please select two different teams.")
    else:
        h2h_df = head_to_head(h2h_team_a, h2h_team_b, num_games, games_df)
        if h2h_df.empty:
            st.info(f"No head-to-head data between {h2h_team_a} and {h2h_team_b} in the database. Try scraping more games.")
        else:
            st.dataframe(h2h_df, use_container_width=True, hide_index=True)

            # Summary stats below the table
            a_col = f"{h2h_team_a}_score"
            b_col = f"{h2h_team_b}_score"
            a_wins = (h2h_df["winner"] == h2h_team_a).sum()
            b_wins = (h2h_df["winner"] == h2h_team_b).sum()

            st.metric("Total Games", len(h2h_df))

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(f"{h2h_team_a} Wins", int(a_wins))
            col2.metric(f"{h2h_team_a} Avg Points", round(h2h_df[a_col].mean(), 1))
            col3.metric(f"{h2h_team_b} Wins", int(b_wins))
            col4.metric(f"{h2h_team_b} Avg Points", round(h2h_df[b_col].mean(), 1))

            # Average combined game total — centered
            avg_total = round((h2h_df[a_col] + h2h_df[b_col]).mean(), 1)
            st.markdown("---")
            _, center, _ = st.columns([1, 1, 1])
            center.metric("Avg Game Total Points", avg_total)

# --- Tab 5: Top Performers ---
with tab_top:
    st.subheader("Top Performers")
    top_team = st.selectbox("Select team", ALL_TEAMS, key="top_team")

    if players_df.empty:
        st.info("No player data yet. Use the sidebar to scrape some teams first.")
    else:
        top_df = top_performers(top_team, num_games, players_df, games_df)
        if top_df.empty:
            st.info(f"No player data for {top_team}. Try scraping this team first.")
        else:
            # Bar chart of top scorers
            chart_df = top_df.head(10).set_index("player")
            st.bar_chart(chart_df["avg_points"])

            # Full table
            st.dataframe(top_df, use_container_width=True, hide_index=True)

# Close connection
conn.close()

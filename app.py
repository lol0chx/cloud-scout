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
    home_away_stats,
    win_streak,           # current W/L streak for a team
    season_standings,     # ranks all teams in DB by win%
    win_probability,      # estimates win chance using win%, H2H, home/away
    possible_injured_players,  # flags players missing from the most recent game
)

# Page config
st.set_page_config(page_title="CloudScout", page_icon="🏀", layout="wide")
st.title("🏀 CloudScout")
st.caption("NBA Stats Scraper & Analytics Dashboard")

# Build team list from nba_api static data
ALL_TEAMS = sorted([t["full_name"] for t in nba_teams.get_teams()])

# Initialize database connection and load data up front
# (loaded early so the sidebar watchlist can reference game results)
conn = init_db()
games_df = load_games(conn)
players_df = load_players(conn)

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

# --- Watchlist ---
# Lets you pin teams and see their latest result + streak at a glance
st.sidebar.header("Watchlist")
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

wl_add = st.sidebar.selectbox("Add team to watchlist", [""] + ALL_TEAMS, key="wl_add")
if st.sidebar.button("Add") and wl_add and wl_add not in st.session_state.watchlist:
    st.session_state.watchlist.append(wl_add)

for wl_team in list(st.session_state.watchlist):
    wl_col1, wl_col2 = st.sidebar.columns([3, 1])
    # Show latest game result and streak for each watched team
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
    if wl_col2.button("✕", key=f"rm_{wl_team}"):
        st.session_state.watchlist.remove(wl_team)
        st.rerun()

st.sidebar.divider()
if st.sidebar.button("Update All Teams", type="primary"):
    with st.sidebar.status("Checking for new games...", expanded=True):
        total_new_games = 0
        for i, team in enumerate(ALL_TEAMS):
            st.write(f"[{i+1}/30] {team}")
            try:
                games_new, _ = scrape_team(team, last=10)
                if not games_new.empty:
                    total_new_games += len(games_new)
                    st.write(f"  +{len(games_new)} new game(s)")
            except Exception as e:
                st.write(f"  Error: {e}")
        st.sidebar.success(f"Done! {total_new_games} new game(s) added.")
    conn.close()
    conn = init_db()

# --- Main tabs ---
tab_games, tab_team, tab_player, tab_h2h, tab_top, tab_standings, tab_pred = st.tabs(
    ["Game Results", "Team Form", "Player Stats", "Head-to-Head", "Top Performers", "Standings", "Predictions"]
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
            # Averages + streak + net rating
            avg_df = last_n_avg(team_sel, num_games, games_df)
            streak_count, streak_type = win_streak(team_sel, games_df)  # current W/L streak
            avg_scored = avg_df["avg_scored"].iloc[0]
            avg_conceded = avg_df["avg_conceded"].iloc[0]
            avg_total = round(avg_scored + avg_conceded, 1)
            net_rating = round(avg_scored - avg_conceded, 1)  # positive = better offense than defense

            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("Games", int(avg_df["games"].iloc[0]))
            # Streak shown in green for wins, red for losses
            streak_label = f"{streak_type}{streak_count}"
            streak_color = "normal" if streak_type == "W" else "inverse"
            col2.metric("Streak", streak_label, delta=f"{streak_count} in a row", delta_color=streak_color)
            col3.metric("Avg Scored", avg_scored)
            col4.metric("Avg Total", avg_total)
            col5.metric("Avg Conceded", avg_conceded)
            # Net Rating = avg pts scored minus avg pts allowed — positive is good
            col6.metric("Net Rating", f"{'+' if net_rating >= 0 else ''}{net_rating}")

            # Rolling form chart
            st.subheader("Rolling Form")
            form_df = rolling_form(team_sel, num_games, games_df)
            st.line_chart(form_df.set_index("date")["rolling_avg"])

            # Game log table — rename columns for display and add margin sign
            display_df = form_df.copy()
            display_df["margin"] = display_df["margin"].apply(
                lambda x: f"+{int(x)}" if x > 0 else str(int(x))
            )
            display_df.columns = ["Date", "Location", "Opponent", "W/L", "Pts", "Opp Pts", "Margin", "Rolling Avg"]
            st.dataframe(display_df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
        except ValueError as e:
            st.warning(str(e))

# --- Tab 3: Player Stats ---
with tab_player:
    st.subheader("Player Stats")

    if players_df.empty:
        st.info("No player data yet. Use the sidebar to scrape some teams first.")
    else:
        # Search bar — filters the player list as you type
        search_query = st.text_input("Search player", placeholder="e.g. LeBron", key="player_search")
        player_names = sorted(players_df["name"].unique().tolist())
        if search_query:
            player_names = [n for n in player_names if search_query.lower() in n.lower()]
        if not player_names:
            st.warning("No players match your search.")
            st.stop()
        player_sel = st.selectbox("Select player", player_names, key="player_sel")

        # Injury Watch — highlight players who missed the most recent team game
        # We find their team from the player data, then check if they were missing
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
            a_col = f"{h2h_team_a}_score"
            b_col = f"{h2h_team_b}_score"
            a_wins = (h2h_df["winner"] == h2h_team_a).sum()
            b_wins = (h2h_df["winner"] == h2h_team_b).sum()

            # --- W/L Game Strip (last 5 games each team overall) ---
            st.markdown("#### Last 5 Games")

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

            # --- H2H Summary Stats ---
            st.markdown("#### H2H Summary")
            avg_diff_a = round((h2h_df[a_col] - h2h_df[b_col]).mean(), 1)
            avg_diff_b = round((h2h_df[b_col] - h2h_df[a_col]).mean(), 1)

            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            col1.metric(f"{h2h_team_a} Wins", int(a_wins))
            col2.metric("Avg Points", round(h2h_df[a_col].mean(), 1))
            col3.metric("Avg Margin", f"{'+' if avg_diff_a >= 0 else ''}{avg_diff_a}")
            col4.metric("Avg Total", round((h2h_df[a_col] + h2h_df[b_col]).mean(), 1))
            col5.metric(f"{h2h_team_b} Wins", int(b_wins))
            col6.metric("Avg Points", round(h2h_df[b_col].mean(), 1))
            col7.metric("Avg Margin", f"{'+' if avg_diff_b >= 0 else ''}{avg_diff_b}")

            st.markdown("---")

            # --- Season Averages Comparison ---
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
                stats_config = [
                    ("Avg Points Scored", "avg_scored", True),
                    ("Avg Points Conceded", "avg_conceded", False),
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

            # --- Home / Away Breakdown ---
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

            # --- Full Game Log ---
            st.markdown("#### Full Game Log")
            st.dataframe(h2h_df, use_container_width=True, hide_index=True)

            _, center, _ = st.columns([1, 1, 1])
            avg_total = round((h2h_df[a_col] + h2h_df[b_col]).mean(), 1)
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

# --- Tab 6: Standings ---
# Ranks every team in the database by win percentage
with tab_standings:
    st.subheader("Standings")
    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    else:
        standings_df = season_standings(games_df)
        # Highlight the Net Rating column — green if positive, red if negative
        def color_net(val):
            color = "#2ea44f" if val > 0 else ("#cf222e" if val < 0 else "")
            return f"color: {color}; font-weight: bold" if color else ""

        styled = standings_df.style.applymap(color_net, subset=["Net Rtg"])
        # Height scales with the number of teams so no scrolling is needed
        table_height = (len(standings_df) + 1) * 35 + 3
        st.dataframe(styled, use_container_width=True, hide_index=True, height=table_height)

# --- Tab 7: Predictions ---
# Estimates who wins a matchup using win%, H2H record, and home/away splits
with tab_pred:
    st.subheader("Predictions")
    col1, col2, col3 = st.columns(3)
    pred_team_a = col1.selectbox("Team A", ALL_TEAMS, index=0, key="pred_a")
    pred_team_b = col2.selectbox("Team B", ALL_TEAMS, index=1, key="pred_b")
    home_options = ["Neutral", pred_team_a, pred_team_b]
    pred_home = col3.selectbox("Home team", home_options, key="pred_home")

    if games_df.empty:
        st.info("No game data yet. Use the sidebar to scrape some teams first.")
    elif pred_team_a == pred_team_b:
        st.warning("Please select two different teams.")
    else:
        home_team_val = None if pred_home == "Neutral" else pred_home
        prob_a, prob_b, margin = win_probability(pred_team_a, pred_team_b, games_df, home_team=home_team_val)

        st.markdown("---")
        st.markdown("#### Win Probability")
        pc1, pc2 = st.columns(2)

        # Color the favored team green, underdog red
        fav_color_a = "#2ea44f" if prob_a >= prob_b else "#cf222e"
        fav_color_b = "#2ea44f" if prob_b > prob_a else "#cf222e"
        pc1.markdown(
            f'<div style="background:{fav_color_a};padding:16px;border-radius:8px;text-align:center;">'
            f'<div style="font-size:2rem;font-weight:bold;color:white;">{prob_a}%</div>'
            f'<div style="color:white;">{pred_team_a}</div></div>', unsafe_allow_html=True
        )
        pc2.markdown(
            f'<div style="background:{fav_color_b};padding:16px;border-radius:8px;text-align:center;">'
            f'<div style="font-size:2rem;font-weight:bold;color:white;">{prob_b}%</div>'
            f'<div style="color:white;">{pred_team_b}</div></div>', unsafe_allow_html=True
        )

        st.markdown("---")
        st.markdown("#### Predicted Spread")
        # Spread = the average point margin advantage for the favored team
        # Positive margin = Team A favored, negative = Team B favored
        if margin > 0:
            st.info(f"**{pred_team_a}** favored by **{abs(margin)} pts**")
        elif margin < 0:
            st.info(f"**{pred_team_b}** favored by **{abs(margin)} pts**")
        else:
            st.info("Pick 'em — no spread advantage detected.")

        st.markdown("---")
        st.markdown("#### Team Context")
        ctx_col1, ctx_col2 = st.columns(2)
        for ctx_col, team in [(ctx_col1, pred_team_a), (ctx_col2, pred_team_b)]:
            sc, st_type = win_streak(team, games_df)
            tg = games_df[(games_df["home_team"] == team) | (games_df["away_team"] == team)]
            if not tg.empty:
                s = tg.apply(lambda r: r["home_score"] if r["home_team"] == team else r["away_score"], axis=1)
                c = tg.apply(lambda r: r["away_score"] if r["home_team"] == team else r["home_score"], axis=1)
                wins = int((s.values > c.values).sum())
                wp = round(wins / len(tg) * 100, 1)
                ctx_col.markdown(f"**{team}**")
                ctx_col.markdown(f"Season: **{wins}W–{len(tg)-wins}L** ({wp}%)")
                ctx_col.markdown(f"Streak: **{st_type}{sc}**")

# Close connection
conn.close()

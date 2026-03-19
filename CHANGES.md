# CloudScout — What Was Added

## analytics.py — New Functions

### `win_streak(team, df)`
Counts how many games in a row a team has won or lost.
Returns a tuple like `(5, 'W')` meaning "5-game win streak" or `(3, 'L')` meaning "3-game losing streak".

### `season_standings(df)`
Looks at all teams in the database and ranks them by win percentage.
Returns a table with: W, L, GP, Win%, Avg Pts scored, Avg Pts allowed, Net Rating (scored - allowed), and current Streak.

### `win_probability(team_a, team_b, df, home_team=None)`
Estimates the chance each team wins a matchup using a weighted formula:
- 35% → Overall win percentage
- 30% → Head-to-head record between the two teams
- 35% → Home/away split (home team gets a boost)
Also returns a predicted point margin (positive = team A favored).

### `possible_injured_players(team, players_df, games_df)`
Compares who played in the most recent game vs. who played in the 3 games before it.
Players who were active before but missing from the latest game are flagged as possibly injured or resting.

---

## app.py — UI Changes

### Sidebar
- **Watchlist** — Add any team to a watchlist. Shows their latest game result (W/L + score) and current streak in real time.

### Team Form Tab
- **Streak** — Shows the current win/loss streak (e.g. "W5" in green, "L3" in red).
- **Net Rating** — Points scored minus points allowed per game. Positive = better offense than defense.
- **Offensive/Defensive Rating** — Displayed alongside existing Avg Scored / Avg Conceded.

### Player Stats Tab
- **Search bar** — Type to filter the player list instead of scrolling through the full dropdown.
- **Injury Watch** — Red warning if a player was active in previous games but missed the most recent game.

### New: Standings Tab
- Ranks all teams in the database by win percentage.
- Color-highlights the best Net Rating.
- Shows streak for every team.

### New: Predictions Tab
- Pick any two teams and an optional home team.
- Displays win probability for each team as a percentage.
- Shows a predicted spread (e.g. "Team A favored by 4.2 pts").
- Shows each team's current streak and season win% for context.

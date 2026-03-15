"""
main.py — Command line interface for CloudScout.

Provides a CLI to scrape NBA game data and run analytics queries.
Results are printed as clean formatted tables in the terminal.

Usage examples:
    python main.py --team "LA Lakers" --last 5
    python main.py --player "LeBron James" --last 10
    python main.py --h2h "LA Lakers" "Boston Celtics" --last 5
    python main.py --top "LA Lakers" --last 5
    python main.py --team "LA Lakers" --last 5 --scrape
"""

import argparse
import sys
import io

from database import init_db, load_games, load_players
from scraper import scrape_team, _resolve_team
from nba_api.stats.static import teams as nba_teams
import pandas as pd
from analytics import (
    last_n_avg,
    head_to_head,
    rolling_form,
    player_avg,
    player_vs_team,
    top_performers,
)


def build_parser():
    """
    Build and return the argument parser for the CLI.
    Supports four main actions (team, player, h2h, top) plus
    options for game count, scraping, and league selection.
    """
    parser = argparse.ArgumentParser(
        description="CloudScout — NBA Stats Scraper & Analytics Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python main.py --team "LA Lakers" --last 5\n'
            '  python main.py --player "LeBron James" --last 10\n'
            '  python main.py --h2h "LA Lakers" "Boston Celtics" --last 5\n'
            '  python main.py --top "LA Lakers" --last 5\n'
            '  python main.py --team "LA Lakers" --last 5 --scrape'
        ),
    )

    # Main action arguments — pick one per invocation
    parser.add_argument(
        "--team", type=str, help="Show recent form stats for a team"
    )
    parser.add_argument(
        "--player", type=str, help="Show average stats for a player"
    )
    parser.add_argument(
        "--h2h", nargs=2, metavar=("TEAM_A", "TEAM_B"),
        help="Head-to-head comparison between two teams"
    )
    parser.add_argument(
        "--top", type=str, help="Show top performers on a team"
    )
    parser.add_argument(
        "--pvt", nargs=2, metavar=("PLAYER", "TEAM"),
        help="Player's average stats against a specific team"
    )
    parser.add_argument(
        "--games", type=str, help="Show raw game results for a team"
    )

    parser.add_argument(
        "--scrape-all", action="store_true",
        help="Scrape last N games for all 30 NBA teams"
    )

    # Options
    parser.add_argument(
        "--last", type=int, default=5,
        help="Number of games to analyze (default: 5)"
    )
    parser.add_argument(
        "--scrape", action="store_true",
        help="Fetch fresh data from NBA.com before running analysis"
    )
    parser.add_argument(
        "--league", type=str, default="NBA",
        help="League to query (default: NBA, for future multi-sport support)"
    )

    return parser


def main():
    """
    Entry point: parse CLI args, optionally scrape fresh data,
    load data from the database, and dispatch to the appropriate
    analytics function. Prints results as formatted tables.
    """
    # Fix Unicode output on Windows terminals
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args()

    # Show help if no action is specified
    if not any([args.team, args.player, args.h2h, args.top, args.pvt, args.games, args.scrape_all]):
        parser.print_help()
        sys.exit(0)

    # Resolve team name aliases to canonical NBA.com names
    # (e.g., "LA Lakers" -> "Los Angeles Lakers") so analytics queries
    # match what's stored in the database
    if args.team:
        args.team = _resolve_team(args.team)["full_name"]
    if args.h2h:
        args.h2h = [_resolve_team(t)["full_name"] for t in args.h2h]
    if args.top:
        args.top = _resolve_team(args.top)["full_name"]
    if args.pvt:
        args.pvt[1] = _resolve_team(args.pvt[1])["full_name"]
    if args.games:
        args.games = _resolve_team(args.games)["full_name"]

    # Initialize the database (creates tables if needed)
    conn = init_db()

    try:
        # If --scrape is set, fetch fresh data from NBA.com first
        if args.scrape:
            # Determine which team(s) to scrape based on the action
            teams_to_scrape = []
            if args.team:
                teams_to_scrape.append(args.team)
            elif args.h2h:
                teams_to_scrape.extend(args.h2h)
            elif args.top:
                teams_to_scrape.append(args.top)
            elif args.pvt:
                teams_to_scrape.append(args.pvt[1])
            elif args.games:
                teams_to_scrape.append(args.games)

            for team in teams_to_scrape:
                scrape_team(team, last=args.last)

        # If --scrape-all is set, scrape every NBA team
        if args.scrape_all:
            all_teams = nba_teams.get_teams()
            total = len(all_teams)
            print(f"\nScraping last {args.last} games for all {total} NBA teams...\n")
            for i, t in enumerate(sorted(all_teams, key=lambda x: x["full_name"]), 1):
                print(f"[{i}/{total}] {t['full_name']}")
                try:
                    scrape_team(t["full_name"], last=args.last)
                except Exception as e:
                    print(f"  Error: {e}")
            print(f"\nDone! All {total} teams scraped.")
            conn.close()
            sys.exit(0)

        # Load data from the database for analysis
        games_df = load_games(conn, league=args.league)
        players_df = load_players(conn)

        if games_df.empty and not args.player:
            print("\nNo game data found in the database.")
            print("Try running with --scrape to fetch data from the API first.")
            sys.exit(0)

        # Dispatch to the appropriate analytics function
        if args.team:
            _handle_team(args.team, args.last, games_df)

        elif args.player:
            _handle_player(args.player, args.last, players_df, games_df)

        elif args.h2h:
            _handle_h2h(args.h2h[0], args.h2h[1], args.last, games_df)

        elif args.top:
            _handle_top(args.top, args.last, players_df, games_df)

        elif args.pvt:
            _handle_pvt(args.pvt[0], args.pvt[1], args.last, players_df, games_df)

        elif args.games:
            _handle_games(args.games, args.last, games_df)

    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
    finally:
        conn.close()


def _handle_team(team, n, games_df):
    """
    Handle the --team action: show average points scored/conceded
    and rolling form for the specified team.
    """
    # Show average scored and conceded
    print(f"\n{'='*50}")
    print(f"  {team} — Last {n} Games Summary")
    print(f"{'='*50}")

    avg_df = last_n_avg(team, n, games_df)
    print("\nAverages:")
    print(avg_df.to_string(index=False))

    # Show rolling form
    print(f"\nRolling Form (window={n}):")
    form_df = rolling_form(team, n, games_df)
    print(form_df.to_string(index=False))


def _handle_player(player, n, players_df, games_df):
    """
    Handle the --player action: show a player's average stats
    over their last N games.
    """
    if players_df.empty:
        print("\nNo player data found in the database.")
        print("Try running with --scrape and --team to fetch player data first.")
        return

    print(f"\n{'='*50}")
    print(f"  {player} — Last {n} Games Averages")
    print(f"{'='*50}")

    avg_df = player_avg(player, n, players_df)
    print("\n" + avg_df.to_string(index=False))


def _handle_h2h(team_a, team_b, n, games_df):
    """
    Handle the --h2h action: show head-to-head results between
    two teams over their last N meetings.
    """
    print(f"\n{'='*50}")
    print(f"  {team_a} vs {team_b} — Last {n} Meetings")
    print(f"{'='*50}")

    h2h_df = head_to_head(team_a, team_b, n, games_df)
    if not h2h_df.empty:
        print("\n" + h2h_df.to_string(index=False))


def _handle_top(team, n, players_df, games_df):
    """
    Handle the --top action: rank players on a team by average
    points over the last N team games.
    """
    if players_df.empty:
        print("\nNo player data found in the database.")
        print("Try running with --scrape and --team to fetch player data first.")
        return

    print(f"\n{'='*50}")
    print(f"  {team} — Top Performers (Last {n} Games)")
    print(f"{'='*50}")

    top_df = top_performers(team, n, players_df, games_df)
    if not top_df.empty:
        print("\n" + top_df.to_string(index=False))


def _handle_pvt(player, opponent, n, players_df, games_df):
    """
    Handle the --pvt action: show a player's average stats
    against a specific team over their last N matchups.
    """
    if players_df.empty:
        print("\nNo player data found in the database.")
        print("Try running with --scrape and --team to fetch player data first.")
        return

    print(f"\n{'='*50}")
    print(f"  {player} vs {opponent} — Last {n} Games")
    print(f"{'='*50}")

    pvt_df = player_vs_team(player, opponent, n, players_df, games_df)
    if not pvt_df.empty:
        print("\n" + pvt_df.to_string(index=False))


def _handle_games(team, n, games_df):
    """
    Handle the --games action: show the raw game results
    for a team's last N games.
    """
    team_games = games_df[
        (games_df["home_team"] == team) | (games_df["away_team"] == team)
    ].sort_values("date", ascending=False).head(n)

    if team_games.empty:
        print(f"\nNo game data found for {team}.")
        return

    print(f"\n{'='*50}")
    print(f"  {team} — Last {n} Game Results")
    print(f"{'='*50}")

    # Build a clean results table
    results = []
    for _, row in team_games.iterrows():
        is_home = row["home_team"] == team
        opponent = row["away_team"] if is_home else row["home_team"]
        team_score = row["home_score"] if is_home else row["away_score"]
        opp_score = row["away_score"] if is_home else row["home_score"]
        location = "Home" if is_home else "Away"
        result = "W" if team_score > opp_score else "L"
        results.append({
            "date": row["date"],
            "opponent": opponent,
            "result": result,
            "score": f"{team_score}-{opp_score}",
            "location": location,
        })

    results_df = pd.DataFrame(results)
    print("\n" + results_df.to_string(index=False))


if __name__ == "__main__":
    main()

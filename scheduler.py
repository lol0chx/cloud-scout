"""
scheduler.py — Automated nightly scraper for CloudScout.

Runs the scraper on a configurable schedule (default: every night at midnight)
for a watchlist of NBA teams. Logs each run with timestamps.

Uses the `schedule` library for simple, readable scheduling.

Usage:
    python scheduler.py

Note: stats.nba.com may throttle requests if hit too frequently.
Each team costs 1 request for the game log + 1 request per new game
for player box scores. A delay is enforced between requests.
"""

import time
from datetime import datetime

import schedule

from scraper import scrape_team


# Teams to scrape automatically each night.
# Each team uses 1 request for the game log + 1 per new game for box scores.
WATCHLIST = [
    "LA Lakers",
    "Boston Celtics",
]


def job():
    """
    The scheduled scraping task. Loops through the WATCHLIST and scrapes
    the last 15 games for each team. Logs start and end times, and catches
    errors per team so one failure doesn't halt the entire batch.
    """
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{start_time}] Starting scheduled scrape...")

    for team in WATCHLIST:
        try:
            scrape_team(team, last=15)
        except Exception as e:
            # Log the error but continue with the next team
            print(f"  Error scraping {team}: {e}")

    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{end_time}] Scheduled scrape complete.")


def run_scheduler():
    """
    Set up the schedule and run forever. The scraper runs every day
    at midnight. Checks for pending jobs every 60 seconds.
    """
    # Schedule the job to run every night at midnight
    schedule.every().day.at("00:00").do(job)

    next_run = schedule.next_run()
    print(f"CloudScout scheduler started.")
    print(f"Watchlist: {', '.join(WATCHLIST)}")
    print(f"Next scheduled run: {next_run}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


if __name__ == "__main__":
    run_scheduler()

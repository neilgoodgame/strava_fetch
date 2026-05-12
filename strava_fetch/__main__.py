"""Entry point: python -m strava_fetch  (or `strava-fetch` via poetry script)."""

import argparse
import logging
import os
from datetime import datetime

from strava_fetch.auth   import get_access_token, run_auth_flow
from strava_fetch.client import fetch_all_activities, to_dataframe
from strava_fetch.report import build_weekly_summary, print_summary, save

TOKEN_FILE = os.path.expanduser("~/.strava_tokens.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="strava-fetch",
        description="Fetch your Strava activity history.",
    )
    parser.add_argument(
        "--auth", action="store_true",
        help="Run the one-time OAuth authorisation flow.",
    )
    parser.add_argument(
        "--type", default=None, metavar="ACTIVITY_TYPE",
        help="Filter by activity type, e.g. Run, Ride, Swim, Walk.",
    )
    parser.add_argument(
        "--after", default=None, metavar="YYYY-MM-DD",
        help="Only fetch activities on or after this date.",
    )
    parser.add_argument(
        "--before", default=None, metavar="YYYY-MM-DD",
        help="Only fetch activities before this date.",
    )
    parser.add_argument(
        "--format", choices=["csv", "parquet"], default="csv",
        help="Output format (default: csv).",
    )
    parser.add_argument(
        "--out", default=None, metavar="FILE",
        help="Output file path for activity export (auto-generated if omitted).",
    )
    parser.add_argument(
        "--no-weekly", action="store_true",
        help="Skip the weekly run summary export.",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    client_id     = os.environ.get("STRAVA_CLIENT_ID",     "YOUR_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

    print(f"client id {client_id}")

    if args.auth:
        run_auth_flow(client_id, client_secret, TOKEN_FILE)
        return

    after  = datetime.strptime(args.after,  "%Y-%m-%d") if args.after  else None
    before = datetime.strptime(args.before, "%Y-%m-%d") if args.before else None

    print("Fetching activities from Strava...")
    token      = get_access_token(client_id, client_secret, TOKEN_FILE)
    activities = fetch_all_activities(token, after=after, before=before)
    print(f"Total fetched: {len(activities)}")

    df = to_dataframe(activities)

    if args.type:
        df = df[df["type"].str.lower() == args.type.lower()].reset_index(drop=True)
        print(f"After filtering for '{args.type}': {len(df)} activities")

    print_summary(df, args.type)

    # --- Activity export ---
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "parquet" if args.format == "parquet" else "csv"
    tag = f"_{args.type.lower()}" if args.type else ""

    out_path = args.out or f"strava_activities{tag}_{ts}.{ext}"
    save(df, out_path, args.format)

    # --- Weekly run summary export ---
    if not args.no_weekly:
        weekly_df = build_weekly_summary(df)
        if not weekly_df.empty:
            weekly_path = f"strava_weekly_runs_{ts}.{ext}"
            save(weekly_df, weekly_path, args.format)
        else:
            print("No Run activities in dataset — skipping weekly summary.")


if __name__ == "__main__":
    main()

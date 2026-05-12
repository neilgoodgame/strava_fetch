"""Strava API client — fetches and transforms activity data."""

from datetime import datetime

import pandas as pd
import requests

STRAVA_API_BASE = "https://www.strava.com/api/v3"


def fetch_all_activities(
    access_token: str,
    after: datetime | None = None,
    before: datetime | None = None,
) -> list[dict]:
    """Page through /athlete/activities and return all results."""
    headers = {"Authorization": f"Bearer {access_token}"}
    activities: list[dict] = []
    page = 1

    params: dict = {"per_page": 100}
    if after:
        params["after"] = int(after.timestamp())
    if before:
        params["before"] = int(before.timestamp())

    while True:
        params["page"] = page
        resp = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        batch: list[dict] = resp.json()
        if not batch:
            break
        activities.extend(batch)
        print(f"  Fetched page {page} ({len(batch)} activities)...")
        page += 1

    return activities


def to_dataframe(activities: list[dict]) -> pd.DataFrame:
    """Flatten key activity fields into a tidy DataFrame."""
    rows = [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "type": a.get("type"),
            "sport_type": a.get("sport_type"),
            "start_date_local": a.get("start_date_local"),
            "distance_km": round(a.get("distance", 0) / 1000, 3),
            "duration_s": a.get("elapsed_time"),
            "moving_time_s": a.get("moving_time"),
            "elevation_m": a.get("total_elevation_gain"),
            "avg_hr": a.get("average_heartrate"),
            "max_hr": a.get("max_heartrate"),
            "avg_watts": a.get("average_watts"),
            "avg_speed_kph": round(a.get("average_speed", 0) * 3.6, 3),
            "max_speed_kph": round(a.get("max_speed", 0) * 3.6, 3),
            "kudos": a.get("kudos_count"),
            "suffer_score": a.get("suffer_score"),
            "trainer": a.get("trainer"),
            "commute": a.get("commute"),
            "gear_id": a.get("gear_id"),
            "strava_url": f"https://www.strava.com/activities/{a.get('id')}",
        }
        for a in activities
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["start_date_local"] = pd.to_datetime(df["start_date_local"])
        df.sort_values("start_date_local", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df

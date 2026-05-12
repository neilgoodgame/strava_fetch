"""Console summary and file export helpers."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Activity types Strava uses for cycling
_RIDE_TYPES = {"ride", "virtualride", "ebikeride", "mountainbikeride", "gravelride"}


def print_summary(df: pd.DataFrame, activity_type: str | None = None) -> None:
    type_label = activity_type or "All"
    print(f"\n{'─' * 60}")
    print(f"  Strava Activity Summary  |  Filter: {type_label}")
    print(f"{'─' * 60}")
    print(f"  Total activities : {len(df)}")
    if df.empty:
        return

    by_type = df.groupby("type").size().sort_values(ascending=False)
    print("\n  By activity type:")
    for t, n in by_type.items():
        print(f"    {t:<20} {n:>4}")

    print(
        f"\n  Date range    : {df['start_date_local'].min().date()} → "
        f"{df['start_date_local'].max().date()}"
    )
    print(f"  Total distance : {df['distance_km'].sum():,.1f} km")
    total_s = int(df["moving_time_s"].sum())
    print(f"  Total moving   : {total_s // 3600}h {(total_s % 3600) // 60}m")

    if df["avg_hr"].notna().any():
        print(f"  Avg heart rate : {df['avg_hr'].mean():.1f} bpm")

    print(f"{'─' * 60}\n")


def _fmt_time(total_seconds: float) -> str:
    s = int(total_seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _fmt_pace(total_seconds: float, total_km: float) -> str:
    if total_km == 0:
        return "N/A"
    secs_per_km = total_seconds / total_km
    return f"{int(secs_per_km // 60):02d}:{int(secs_per_km % 60):02d}"


def _week_start(series: pd.Series) -> pd.Series:
    """Map a datetime series to the Monday date of its ISO week."""
    return series.dt.to_period("W-SUN").apply(lambda p: p.start_time.date())


def _build_spine(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of every Monday covering the full date range of df."""
    earliest = df["start_date_local"].min()
    latest = df["start_date_local"].max()
    mondays = pd.date_range(  # pylint: disable=no-member
        start=earliest.to_period("W-SUN").start_time,
        end=latest.to_period("W-SUN").start_time,
        freq="W-MON",
    ).date
    logger.debug("Week spine: %d weeks (%s → %s)", len(mondays), mondays[0], mondays[-1])
    return pd.DataFrame({"week_start": mondays})


def _agg_runs(runs: pd.DataFrame) -> pd.DataFrame:
    runs = runs.copy()
    runs["week_start"] = _week_start(runs["start_date_local"])
    return (
        runs.groupby("week_start")
        .agg(
            num_run_activities=("distance_km", "count"),
            total_run_distance_km=("distance_km", "sum"),
            run_moving_s=("moving_time_s", "sum"),
            avg_run_hr_bpm=("avg_hr", "mean"),
            longest_run_km=("distance_km", "max"),
        )
        .reset_index()
    )


def _agg_rides(rides: pd.DataFrame) -> pd.DataFrame:
    rides = rides.copy()
    rides["week_start"] = _week_start(rides["start_date_local"])
    return (
        rides.groupby("week_start")
        .agg(
            num_cycling_activities=("distance_km", "count"),
            total_cycling_distance_km=("distance_km", "sum"),
            cycling_moving_s=("moving_time_s", "sum"),
            avg_cycling_power_w=("avg_watts", "mean"),
            avg_cycling_hr_bpm=("avg_hr", "mean"),
        )
        .reset_index()
    )


def build_weekly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate Run and cycling activities into a combined weekly summary,
    including empty weeks.

    Weeks run Monday–Sunday. The date spine covers the full range of the
    input DataFrame so weeks with no activity appear as zero rows.

    Running columns:
        num_run_activities       — number of runs (0 for empty weeks)
        total_run_distance_km    — total run distance
        total_run_time           — total run moving time as HH:MM:SS
        avg_run_pace_min_per_km  — average pace as MM:SS/km (N/A if no runs)
        avg_run_hr_bpm           — mean HR across runs (NaN if unavailable)
        longest_run_km           — longest single run

    Cycling columns:
        num_cycling_activities     — number of rides (0 for empty weeks)
        total_cycling_distance_km  — total ride distance
        total_cycling_time         — total ride moving time as HH:MM:SS
        avg_cycling_power_w        — mean average power in watts (NaN if unavailable)
        avg_cycling_hr_bpm         — mean HR across rides (NaN if unavailable)
    """
    if df.empty:
        logger.warning("Input DataFrame is empty — weekly summary will be empty")
        return pd.DataFrame(
            columns=[
                "week_start",
                "week_end",
                "num_run_activities",
                "total_run_distance_km",
                "total_run_time",
                "avg_run_pace_min_per_km",
                "avg_run_hr_bpm",
                "longest_run_km",
                "num_cycling_activities",
                "total_cycling_distance_km",
                "total_cycling_time",
                "avg_cycling_power_w",
                "avg_cycling_hr_bpm",
            ]
        )

    spine = _build_spine(df)

    runs = df[df["type"].str.lower() == "run"]
    rides = df[df["type"].str.lower().isin(_RIDE_TYPES)]
    logger.debug("Found %d runs and %d rides", len(runs), len(rides))

    # Merge run aggregation
    if not runs.empty:
        spine = spine.merge(_agg_runs(runs), on="week_start", how="left")
    else:
        logger.warning("No Run activities found")
        for col in (
            "num_run_activities",
            "total_run_distance_km",
            "run_moving_s",
            "avg_run_hr_bpm",
            "longest_run_km",
        ):
            spine[col] = float("nan")

    # Merge ride aggregation
    if not rides.empty:
        spine = spine.merge(_agg_rides(rides), on="week_start", how="left")
    else:
        logger.warning("No cycling activities found")
        for col in (
            "num_cycling_activities",
            "total_cycling_distance_km",
            "cycling_moving_s",
            "avg_cycling_power_w",
            "avg_cycling_hr_bpm",
        ):
            spine[col] = float("nan")

    # Fill integer/distance zeros for empty weeks
    for col in ("num_run_activities", "total_run_distance_km", "run_moving_s", "longest_run_km"):
        spine[col] = spine[col].fillna(0)
    for col in ("num_cycling_activities", "total_cycling_distance_km", "cycling_moving_s"):
        spine[col] = spine[col].fillna(0)

    spine["num_run_activities"] = spine["num_run_activities"].astype(int)
    spine["num_cycling_activities"] = spine["num_cycling_activities"].astype(int)

    # Derived columns
    spine["week_end"] = spine["week_start"].apply(lambda d: d + pd.Timedelta(days=6))
    spine["total_run_time"] = spine["run_moving_s"].apply(_fmt_time)
    spine["total_cycling_time"] = spine["cycling_moving_s"].apply(_fmt_time)
    spine["avg_run_pace_min_per_km"] = spine.apply(
        lambda r: _fmt_pace(r["run_moving_s"], r["total_run_distance_km"]), axis=1
    )

    # Round numeric columns
    spine["total_run_distance_km"] = spine["total_run_distance_km"].round(2)
    spine["longest_run_km"] = spine["longest_run_km"].round(2)
    spine["avg_run_hr_bpm"] = spine["avg_run_hr_bpm"].round(1)
    spine["total_cycling_distance_km"] = spine["total_cycling_distance_km"].round(2)
    spine["avg_cycling_power_w"] = spine["avg_cycling_power_w"].round(1)
    spine["avg_cycling_hr_bpm"] = spine["avg_cycling_hr_bpm"].round(1)

    result = (
        spine[
            [
                "week_start",
                "week_end",
                "num_run_activities",
                "total_run_distance_km",
                "total_run_time",
                "avg_run_pace_min_per_km",
                "avg_run_hr_bpm",
                "longest_run_km",
                "num_cycling_activities",
                "total_cycling_distance_km",
                "total_cycling_time",
                "avg_cycling_power_w",
                "avg_cycling_hr_bpm",
            ]
        ]
        .sort_values("week_start", ascending=False)
        .reset_index(drop=True)
    )

    logger.debug(
        "Weekly summary: %d weeks, %d with runs, %d with rides",
        len(result),
        (result["num_run_activities"] > 0).sum(),
        (result["num_cycling_activities"] > 0).sum(),
    )
    return result


def save(df: pd.DataFrame, path: str, fmt: str) -> None:
    if fmt == "parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
    print(f"Saved {len(df)} rows → {path}")

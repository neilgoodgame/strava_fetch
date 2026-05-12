"""Tests for strava_fetch.report"""

import pandas as pd
import pytest

from strava_fetch.report import _fmt_pace, _fmt_time, build_weekly_summary, save


class TestFmtTime:
    def test_zero(self):
        assert _fmt_time(0) == "00:00:00"

    def test_one_hour(self):
        assert _fmt_time(3600) == "01:00:00"

    def test_mixed(self):
        assert _fmt_time(3661) == "01:01:01"

    def test_sub_minute(self):
        assert _fmt_time(45) == "00:00:45"

    def test_multi_hour(self):
        assert _fmt_time(7322) == "02:02:02"


class TestFmtPace:
    def test_zero_km_returns_na(self):
        assert _fmt_pace(300, 0) == "N/A"

    def test_five_min_per_km(self):
        assert _fmt_pace(25 * 60, 5.0) == "05:00"

    def test_four_min_per_km(self):
        assert _fmt_pace(4 * 60, 1.0) == "04:00"

    def test_sub_minute_pace(self):
        assert _fmt_pace(90, 3.0) == "00:30"


def _make_df(activities: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(activities)
    df["start_date_local"] = pd.to_datetime(df["start_date_local"])
    return df


_RUN = {
    "type": "Run",
    "start_date_local": "2025-01-08",
    "distance_km": 10.0,
    "moving_time_s": 3000,
    "avg_hr": 150.0,
    "avg_watts": None,
}

_RIDE = {
    "type": "Ride",
    "start_date_local": "2025-01-08",
    "distance_km": 40.0,
    "moving_time_s": 5400,
    "avg_hr": 140.0,
    "avg_watts": 220.0,
}


class TestBuildWeeklySummary:
    def test_empty_df_returns_empty_with_correct_columns(self):
        result = build_weekly_summary(pd.DataFrame())
        assert result.empty
        assert set(result.columns) == {
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
        }

    def test_single_run_week(self):
        result = build_weekly_summary(_make_df([_RUN]))
        assert len(result) == 1
        assert result["num_run_activities"].iloc[0] == 1
        assert result["total_run_distance_km"].iloc[0] == 10.0
        assert result["num_cycling_activities"].iloc[0] == 0

    def test_single_ride_week(self):
        result = build_weekly_summary(_make_df([_RIDE]))
        assert len(result) == 1
        assert result["num_cycling_activities"].iloc[0] == 1
        assert result["total_cycling_distance_km"].iloc[0] == 40.0
        assert result["num_run_activities"].iloc[0] == 0

    def test_virtual_ride_counts_as_cycling(self):
        ride = {**_RIDE, "type": "VirtualRide"}
        result = build_weekly_summary(_make_df([ride]))
        assert result["num_cycling_activities"].iloc[0] == 1

    def test_empty_week_filled_with_zeros(self):
        # Jan 6 (week 1) and Jan 20 (week 3) — week 2 should be zero-filled
        w1 = {**_RUN, "start_date_local": "2025-01-06"}
        w3 = {**_RUN, "start_date_local": "2025-01-20"}
        result = build_weekly_summary(_make_df([w1, w3]))

        assert len(result) == 3
        by_week = result.sort_values("week_start").reset_index(drop=True)
        empty = by_week.iloc[1]
        assert empty["num_run_activities"] == 0
        assert empty["total_run_distance_km"] == 0.0
        assert empty["total_run_time"] == "00:00:00"

    def test_sorted_descending_by_week(self):
        w1 = {**_RUN, "start_date_local": "2025-01-06"}
        w2 = {**_RUN, "start_date_local": "2025-01-13"}
        result = build_weekly_summary(_make_df([w1, w2]))
        assert result["week_start"].iloc[0] > result["week_start"].iloc[1]

    def test_week_end_is_six_days_after_start(self):
        result = build_weekly_summary(_make_df([_RUN]))
        row = result.iloc[0]
        delta = pd.Timestamp(row["week_end"]) - pd.Timestamp(row["week_start"])
        assert delta.days == 6

    def test_multiple_runs_aggregated(self):
        r1 = {**_RUN, "start_date_local": "2025-01-06", "distance_km": 5.0, "moving_time_s": 1500}
        r2 = {**_RUN, "start_date_local": "2025-01-08", "distance_km": 8.0, "moving_time_s": 2400}
        result = build_weekly_summary(_make_df([r1, r2]))
        assert result["num_run_activities"].iloc[0] == 2
        assert result["total_run_distance_km"].iloc[0] == pytest.approx(13.0)
        assert result["longest_run_km"].iloc[0] == pytest.approx(8.0)

    def test_avg_hr_is_nan_when_not_available(self):
        run = {**_RUN, "avg_hr": None}
        result = build_weekly_summary(_make_df([run]))
        assert pd.isna(result["avg_run_hr_bpm"].iloc[0])

    def test_run_and_ride_same_week(self):
        result = build_weekly_summary(_make_df([_RUN, _RIDE]))
        assert result["num_run_activities"].iloc[0] == 1
        assert result["num_cycling_activities"].iloc[0] == 1


class TestSave:
    def test_saves_csv(self, tmp_path):
        path = str(tmp_path / "out.csv")
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        save(df, path, "csv")
        loaded = pd.read_csv(path)
        assert len(loaded) == 2
        assert list(loaded.columns) == ["a", "b"]

    def test_saves_parquet(self, tmp_path):
        path = str(tmp_path / "out.parquet")
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        save(df, path, "parquet")
        loaded = pd.read_parquet(path)
        assert len(loaded) == 2

"""Tests for strava_fetch.client"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from strava_fetch.client import fetch_all_activities, to_dataframe

SAMPLE_ACTIVITY = {
    "id": 1,
    "name": "Morning Run",
    "type": "Run",
    "sport_type": "Run",
    "start_date_local": "2025-01-06T08:00:00Z",
    "distance": 10000,
    "elapsed_time": 3600,
    "moving_time": 3500,
    "total_elevation_gain": 100.0,
    "average_heartrate": 150.0,
    "max_heartrate": 175.0,
    "average_watts": None,
    "average_speed": 2.778,
    "max_speed": 4.0,
    "kudos_count": 3,
    "suffer_score": 50,
    "trainer": False,
    "commute": False,
    "gear_id": "g1",
}


class TestToDataframe:
    def test_empty_list_returns_empty_dataframe(self):
        df = to_dataframe([])
        assert df.empty
        assert isinstance(df, pd.DataFrame)

    def test_single_activity_returns_one_row(self):
        df = to_dataframe([SAMPLE_ACTIVITY])
        assert len(df) == 1

    def test_distance_conversion(self):
        df = to_dataframe([SAMPLE_ACTIVITY])
        assert df["distance_km"].iloc[0] == round(10000 / 1000, 3)

    def test_speed_conversion_kph(self):
        df = to_dataframe([SAMPLE_ACTIVITY])
        assert df["avg_speed_kph"].iloc[0] == round(2.778 * 3.6, 3)
        assert df["max_speed_kph"].iloc[0] == round(4.0 * 3.6, 3)

    def test_strava_url(self):
        df = to_dataframe([SAMPLE_ACTIVITY])
        assert df["strava_url"].iloc[0] == "https://www.strava.com/activities/1"

    def test_sorted_descending_by_date(self):
        a1 = {**SAMPLE_ACTIVITY, "id": 1, "start_date_local": "2025-01-01T08:00:00Z"}
        a2 = {**SAMPLE_ACTIVITY, "id": 2, "start_date_local": "2025-01-10T08:00:00Z"}
        df = to_dataframe([a1, a2])
        assert df["id"].iloc[0] == 2

    def test_missing_optional_fields_are_null(self):
        minimal = {"id": 99, "start_date_local": "2025-01-01T08:00:00Z"}
        df = to_dataframe([minimal])
        assert pd.isna(df["avg_hr"].iloc[0])
        assert pd.isna(df["avg_watts"].iloc[0])

    def test_start_date_is_datetime(self):
        df = to_dataframe([SAMPLE_ACTIVITY])
        assert pd.api.types.is_datetime64_any_dtype(df["start_date_local"])


class TestFetchAllActivities:
    def _mock_response(self, payload):
        m = MagicMock()
        m.json.return_value = payload
        m.raise_for_status.return_value = None
        return m

    def test_paginates_until_empty_batch(self):
        responses = [
            self._mock_response([{"id": 1}, {"id": 2}]),
            self._mock_response([{"id": 3}]),
            self._mock_response([]),
        ]
        with patch("strava_fetch.client.requests.get", side_effect=responses) as mock_get:
            result = fetch_all_activities("token123")

        assert len(result) == 3
        assert mock_get.call_count == 3

    def test_sends_auth_header(self):
        with patch("strava_fetch.client.requests.get", return_value=self._mock_response([])) as mock_get:
            fetch_all_activities("mytoken")

        assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer mytoken"}

    def test_after_before_params(self):
        after = datetime(2025, 1, 1)
        before = datetime(2025, 12, 31)

        with patch("strava_fetch.client.requests.get", return_value=self._mock_response([])) as mock_get:
            fetch_all_activities("token", after=after, before=before)

        params = mock_get.call_args.kwargs["params"]
        assert params["after"] == int(after.timestamp())
        assert params["before"] == int(before.timestamp())

    def test_no_after_before_omits_params(self):
        with patch("strava_fetch.client.requests.get", return_value=self._mock_response([])) as mock_get:
            fetch_all_activities("token")

        params = mock_get.call_args.kwargs["params"]
        assert "after" not in params
        assert "before" not in params

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")

        with patch("strava_fetch.client.requests.get", return_value=mock_resp):
            with pytest.raises(Exception, match="403"):
                fetch_all_activities("bad_token")

"""Tests for strava_fetch.auth"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from strava_fetch.auth import _load_tokens, _refresh_if_needed, _save_tokens, get_access_token


class TestLoadTokens:
    def test_loads_valid_token_file(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        data = {"access_token": "abc", "expires_at": 9999999999}
        token_file.write_text(json.dumps(data))
        assert _load_tokens(str(token_file)) == data

    def test_raises_file_not_found_with_hint(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="--auth"):
            _load_tokens(str(tmp_path / "missing.json"))


class TestSaveTokens:
    def test_writes_valid_json(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        data = {"access_token": "xyz", "expires_at": 9999999999}
        _save_tokens(data, str(token_file))
        assert json.loads(token_file.read_text()) == data

    def test_overwrites_existing_file(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({"access_token": "old"}))
        new_data = {"access_token": "new", "expires_at": 9999999999}
        _save_tokens(new_data, str(token_file))
        assert json.loads(token_file.read_text())["access_token"] == "new"


class TestRefreshIfNeeded:
    def test_returns_tokens_unchanged_when_not_expired(self):
        tokens = {"access_token": "valid", "expires_at": time.time() + 3600}
        result = _refresh_if_needed(tokens, "cid", "csecret", "/tmp/tok.json")
        assert result is tokens

    def test_refreshes_when_expired(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        old = {"access_token": "old", "expires_at": time.time() - 100, "refresh_token": "ref"}
        new = {"access_token": "new", "expires_at": time.time() + 3600, "refresh_token": "ref2"}

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = new

        with patch("strava_fetch.auth.requests.post", return_value=mock_resp):
            result = _refresh_if_needed(old, "12345", "csecret", str(token_file))

        assert result["access_token"] == "new"

    def test_posts_refresh_token_grant(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        old = {"access_token": "old", "expires_at": time.time() - 100, "refresh_token": "myref"}
        new = {"access_token": "new", "expires_at": time.time() + 3600, "refresh_token": "myref"}

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = new

        with patch("strava_fetch.auth.requests.post", return_value=mock_resp) as mock_post:
            _refresh_if_needed(old, "12345", "csecret", str(token_file))

        payload = mock_post.call_args.kwargs.get("data") or mock_post.call_args.args[1]
        assert payload["grant_type"] == "refresh_token"
        assert payload["refresh_token"] == "myref"

    def test_raises_on_failed_refresh(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        old = {"access_token": "old", "expires_at": time.time() - 100, "refresh_token": "ref"}

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")

        with patch("strava_fetch.auth.requests.post", return_value=mock_resp):
            with pytest.raises(Exception, match="401"):
                _refresh_if_needed(old, "12345", "csecret", str(token_file))


class TestGetAccessToken:
    def test_returns_access_token(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        tokens = {"access_token": "the_token", "expires_at": time.time() + 3600, "refresh_token": "ref"}
        token_file.write_text(json.dumps(tokens))
        assert get_access_token("cid", "csecret", str(token_file)) == "the_token"

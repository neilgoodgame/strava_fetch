"""OAuth2 token management for the Strava API."""

import json
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
import webbrowser

import requests

logger = logging.getLogger(__name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


def _capture_auth_code() -> str:
    """Spin up a local server and block until Strava redirects with a code."""
    captured: dict[str, str] = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # pylint: disable=invalid-name
            logger.debug("Incoming request path: %s", self.path)
            params = parse_qs(urlparse(self.path).query)
            logger.debug("Parsed params: %s", params)
            code = params.get("code", [None])[0]
            error = params.get("error", [None])[0]
            if error:
                logger.error("Strava returned an error: %s", error)
                captured["code"] = ""
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f"<h2>Error: {error}</h2>".encode())
            elif code:
                logger.debug("Auth code captured: %s...", code[:8])
                captured["code"] = code
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<h2>Authorised! You can close this tab.</h2>")
            else:
                logger.debug("No code in request, ignoring")
                self.send_response(204)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", 8765), _Handler)
    print("Waiting for redirect on http://localhost:8765 ...")
    while "code" not in captured:
        server.handle_request()
    server.server_close()

    if not captured["code"]:
        raise RuntimeError("Auth flow failed — Strava returned an error.")
    return captured["code"]


def run_auth_flow(client_id: str, client_secret: str, token_file: str) -> None:
    """Open browser for Strava OAuth, capture the code, exchange for tokens."""
    params = urlencode(
        {
            "client_id": int(client_id),
            "redirect_uri": "http://localhost:8765",
            "response_type": "code",
            "approval_prompt": "force",
            "scope": "activity:read_all",
        }
    )
    url = f"{STRAVA_AUTH_URL}?{params}"
    logger.debug("Auth URL: %s", url)
    print(f"Opening browser for Strava authorisation...\n{url}\n")
    webbrowser.open(url)

    code = _capture_auth_code()
    print("Auth code received, exchanging for tokens...")
    logger.debug(
        "POST payload: client_id=%s secret=%s... code=%s...",
        client_id,
        client_secret[:8],
        code[:8],
    )

    resp = requests.post(
        STRAVA_TOKEN_URL,
        timeout=30,
        data={
            "client_id": int(client_id),
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    logger.debug("Token exchange response (%s): %s", resp.status_code, resp.text)
    if not resp.ok:
        print(f"Token exchange failed ({resp.status_code}): {resp.text}")
        resp.raise_for_status()
    tokens = resp.json()
    _save_tokens(tokens, token_file)
    print(f"Authorised as: {tokens['athlete']['firstname']} {tokens['athlete']['lastname']}")


def get_access_token(client_id: str, client_secret: str, token_file: str) -> str:
    """Load tokens, refresh if expired, return a valid access token."""
    tokens = _load_tokens(token_file)
    tokens = _refresh_if_needed(tokens, client_id, client_secret, token_file)
    return tokens["access_token"]


def _save_tokens(tokens: dict, token_file: str) -> None:
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)
    logger.debug("Tokens saved to %s", token_file)
    print(f"Tokens saved to {token_file}")


def _load_tokens(token_file: str) -> dict:
    try:
        with open(token_file, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"No token file found at {token_file}. " "Run with --auth first to authorise."
        ) from exc


def _refresh_if_needed(tokens: dict, client_id: str, client_secret: str, token_file: str) -> dict:
    if tokens.get("expires_at", 0) > time.time() + 60:
        return tokens
    print("Access token expired — refreshing...")
    resp = requests.post(
        STRAVA_TOKEN_URL,
        timeout=30,
        data={
            "client_id": int(client_id),
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
    )
    logger.debug("Token refresh response (%s): %s", resp.status_code, resp.text)
    if not resp.ok:
        print(f"Token refresh failed ({resp.status_code}): {resp.text}")
        resp.raise_for_status()
    new_tokens = resp.json()
    _save_tokens(new_tokens, token_file)
    return new_tokens

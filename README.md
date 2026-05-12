# strava-fetch

[![Tests](https://github.com/neilgoodgame/strava_fetch/actions/workflows/tests.yml/badge.svg)](https://github.com/neilgoodgame/strava_fetch/actions/workflows/tests.yml)
[![Pylint](https://github.com/neilgoodgame/strava_fetch/actions/workflows/pylint.yml/badge.svg)](https://github.com/neilgoodgame/strava_fetch/actions/workflows/pylint.yml)

Fetch your Strava activity history and export to CSV or Parquet.

## Setup

### 1. Install dependencies

```bash
poetry install
```

### 2. Configure credentials

Set your Strava API credentials as environment variables (get them from https://www.strava.com/settings/api):

```bash
export STRAVA_CLIENT_ID=your_client_id
export STRAVA_CLIENT_SECRET=your_client_secret
```

Or add them to a `.env` file and use `python-dotenv` (optional).

### 3. Authorise (one-time)

```bash
poetry run strava-fetch --auth
```

This opens your browser, completes the OAuth flow, and saves a token to `~/.strava_tokens.json`. Tokens are refreshed automatically on subsequent runs.

## Usage

```bash
# All activities → CSV
poetry run strava-fetch

# Runs only → Parquet
poetry run strava-fetch --type Run --format parquet

# Rides in a date range
poetry run strava-fetch --type Ride --after 2025-01-01 --before 2026-01-01

# Custom output path
poetry run strava-fetch --out my_activities.csv
```

## Options

| Flag | Description |
|------|-------------|
| `--auth` | Run the one-time OAuth authorisation flow |
| `--type` | Filter by activity type: `Run`, `Ride`, `Swim`, `Walk`, etc. |
| `--after YYYY-MM-DD` | Only fetch activities on or after this date |
| `--before YYYY-MM-DD` | Only fetch activities before this date |
| `--format csv\|parquet` | Output format (default: `csv`) |
| `--out FILE` | Output file path (auto-generated if omitted) |
| `--no-weekly` | Skip the weekly run summary export |
| `--debug` | Enable debug logging |

## Development

### Install dev dependencies

```bash
poetry install --with dev
```

### Install git hooks

The pre-commit hook runs black (auto-format) and pylint before every commit.

```bash
sh scripts/install-hooks.sh
```

### Run tests

```bash
poetry run pytest
```

Tests also run automatically on every push via GitHub Actions.

### Lint and format manually

```bash
poetry run pylint $(git ls-files '*.py')
poetry run black strava_fetch/ tests/
```

## Project structure

```
strava_fetch/
├── __init__.py      # Package metadata
├── __main__.py      # CLI entry point
├── auth.py          # OAuth2 token management
├── client.py        # Strava API client + DataFrame builder
└── report.py        # Console summary + file export
```

## PyCharm setup

1. Open the `strava_fetch` folder as a project in PyCharm.
2. Go to **Settings → Python Interpreter → Add Interpreter → Poetry Environment**.
3. PyCharm will detect the `pyproject.toml` and create the virtual environment automatically.
4. Use the built-in terminal to run `poetry install` if dependencies aren't installed yet.

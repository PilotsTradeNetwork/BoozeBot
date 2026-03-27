# BoozeBot — Agent Onboarding

Trust these instructions. Only search the codebase if something here is incomplete or appears incorrect.

---

## What this repository does

BoozeBot is a Python Discord bot for the **Pilots Trade Network (PTN)** community that manages "Booze Cruise" events — coordinated in-game fleet carrier wine-delivery operations in Elite Dangerous. It tracks carriers, coordinates unloading, manages roles, posts announcements, and integrates with a REST API (BoozeSheets) for cruise state. The bot is deployed as a Docker container.

---

## Repository at a glance

| Item | Detail |
|---|---|
| Language | Python 3.13 (pinned via `requires-python = "~=3.13.0"`) |
| Package manager | `uv` (lock file: `uv.lock`) |
| Framework | `discord.py` 2.7 (slash commands via `app_commands`) |
| Key external dependency | `ptn-utils` — sourced from a **private Git repo**: `https://github.com/PilotsTradeNetwork/PTN-Library.git` at tag `1.1.0` |
| Entry point | `ptn/boozebot/application.py` → `run()`, registered as the `booze` console script |
| Database | SQLite (`booze.db`) managed via a custom `Database` class |
| Linter | `ruff` 0.15.4 (configured in `pyproject.toml`) |
| Type checkers | `basedpyright` 1.38.2 **and** `ty` 0.0.14 |
| Pre-commit | `prek` 0.3.1 — a uv tool, drop-in replacement for `pre-commit` (config: `.pre-commit-config.yaml`) |
| Tests | `unittest` — two tests in `tests/test_ph_check.py` |
| CI | GitHub Actions (`.github/workflows/container.yml`) — builds and pushes Docker image on `v*` tags only |

---

## Dev/prod environment split

`ptn_utils` reads the environment variable `PTN_SERVICE` at import time:

- `PTN_SERVICE=False` (default, unset) → **dev mode**: uses the PANTS test Discord server, reads `DISCORD_TOKEN_TESTING` from `.env`
- `PTN_SERVICE=True` → **production mode**: uses the live PTN server, reads `DISCORD_TOKEN` from `.env`

`DATA_DIR` defaults to `ptn/data/` (relative to cwd) in dev mode. In production it is set via an environment variable pointing to `/root/boozedatabase`.

---

## Secrets and credentials

**Never hardcode secrets.** The project reads secrets from `.env` files (via `python-dotenv`):

- In dev, `.env` is expected at `ptn/data/.env` (i.e. `$DATA_DIR/.env`)
- In production, the Docker container mounts `/root/boozedatabase` and symlinks `/root/boozedatabase/.env` → `/root/.env`

Required `.env` keys:
- `DISCORD_TOKEN_TESTING` — bot token for dev/testing
- `DISCORD_TOKEN` — bot token for production
- `BOOZESHEETS_API_BASE_URL` — base URL of the BoozeSheets REST API (startup will `exit(1)` if missing)
- `BOOZESHEETS_API_KEY` — API key for BoozeSheets (startup will `exit(1)` if missing)

The `.env` file and `data/` directory are gitignored. Do not commit credentials.

---

## Environment setup

```
# 1. Install uv if not already installed
# See: https://github.com/astral-sh/uv#installation

# 2. (Optional) install the correct Python version
uv python install

# 3. Sync all dependencies including dev group
uv sync

# 4. Activate the venv (required to use `python` directly; not needed for `uv run`)
source .venv/bin/activate

# 5. Install uv tools (prek and ty are NOT project dev dependencies — they are uv tools)
uv tool install prek
uv tool install ty

# 6. Install the prek git hook so it runs automatically on commit
prek install
```

Always run `uv sync` first after any change to `pyproject.toml` or `uv.lock`, and before running lint, type-check, or tests.

`ptn-utils` is fetched from a private GitHub repository — `uv sync` will clone it automatically using the pinned git SHA. If the clone fails, check network access to GitHub.

---

## Running validations

All commands below should be run from the repo root (`/path/to/BoozeBot`).

### Lint (ruff)

```
uv run ruff check ptn/
```

Expected output on a clean tree: `All checks passed!`

The ruff config is in `pyproject.toml` under `[tool.ruff]`. Line length is 120. Only `FIX001`, `FIX002`, `FIX003` rules are selected (flags FIXME/HACK/TODO/XXX comments). Ruff will not block on stylistic issues.

### Type-check (basedpyright)

```
uv run basedpyright ptn/
```

The baseline on the current codebase is **5 errors, 18 warnings** — these are pre-existing and are not introduced by new changes. The config is in `pyproject.toml` under `[tool.basedpyright]` with many checks intentionally disabled. Do not introduce new errors beyond the baseline.

### Type-check (ty)

`ty` is installed as a **uv tool** (not a project dev dependency). Install it with `uv tool install ty` if not already present. Run it as:

```
ty check ptn/
```

or, if `ty` is not on `PATH`:

```
uv tool run ty check ptn/
```

The baseline on the current codebase is **280 diagnostics (112 errors, 168 warnings)**. These are all pre-existing. Do not introduce new errors beyond the baseline count.

### Tests

```
uv run python -m unittest discover
```

Expected output: `Ran 2 tests` with `OK`. The two tests in `tests/test_ph_check.py` exercise `api_ph_check()` with mocked HTTP responses. They emit `RuntimeWarning: coroutine ... was never awaited` and `DeprecationWarning` — these are known pre-existing issues with the test suite and can be ignored as long as the result is still `OK`.

---

## CI pipeline

`.github/workflows/container.yml` runs **only on `v*` tag pushes**. It does **not** run on pull requests or branch pushes. The workflow only builds and pushes a Docker image to Docker Hub — it does **not** run lint, type-check, or tests in CI.

Lint and formatting are enforced locally via **`prek`** (a Rust-reimplementation of `pre-commit`, installed as a uv tool). The config is in `.pre-commit-config.yaml`. Once installed with `prek install`, it runs automatically on `git commit`. Hooks configured:

- `check-added-large-files` (max 750 KB), `check-merge-conflict`, `detect-private-key`, `check-case-conflict`, `mixed-line-ending`, `check-toml`, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace` — all from `pre-commit-hooks` v6.0.0
- `ruff check --fix --exit-non-zero-on-fix` — lint with auto-fix; exits non-zero if any fix was applied (requiring a re-stage)
- `ruff format --exit-non-zero-on-format` — format; exits non-zero if any file was reformatted

**Important**: `prek run --all-files` may modify files on first run (fixing trailing whitespace, missing final newlines, etc.) and exit non-zero. Run it a second time to confirm all hooks pass cleanly.

**Summary of what to run before submitting:**
1. `uv sync`
2. `prek run --all-files` — run twice if first run exits non-zero due to auto-fixes
3. `uv run basedpyright ptn/` — must not exceed 5 errors / 18 warnings
4. `ty check ptn/` — must not exceed 280 diagnostics
5. `uv run python -m unittest discover` — must pass with `OK`

---

## Project layout

```
BoozeBot/
├── agents.md                  # this file
├── pyproject.toml             # build system, dependencies, ruff + basedpyright config
├── uv.lock                    # locked dependency versions
├── requirements.txt           # auto-generated by uv for Docker builds; do not edit manually
├── .pre-commit-config.yaml    # prek/pre-commit hook config (ruff check + format, file hygiene)
├── Dockerfile                 # multi-stage build; entrypoint is `booze` console script
├── Docker_readme.txt          # Docker run instructions
├── CHANGELOG.md
├── CODEOWNERS
├── ptn/
│   ├── __init__.py            # pkgutil namespace init — required for PTN namespace packages
│   ├── data/                  # empty dir; in dev mode DATA_DIR defaults here
│   └── boozebot/
│       ├── __init__.py        # exports __version__
│       ├── _metadata.py       # version via importlib.metadata
│       ├── application.py     # entry point: registers cogs, error handlers, starts bot
│       ├── constants.py       # bot object, DB paths, role/channel IDs, GIF lists, regex
│       ├── botcommands/       # discord.py Cogs (one per feature area)
│       │   ├── AutoResponses.py
│       │   ├── BackgroundTaskCommands.py
│       │   ├── Cleaner.py         # channel open/close, roles cleanup
│       │   ├── Corked.py          # corked user management
│       │   ├── Departures.py      # carrier departure announcements
│       │   ├── DiscordBotCommands.py  # admin text commands (ping, version, exit, update)
│       │   ├── MakeWineCarrier.py
│       │   ├── MimicSteve.py      # steve_says, context menu
│       │   ├── PublicHoliday.py   # holiday detection loop, channel management
│       │   ├── Statistics.py      # tally, carrier lookup, pinned stat messages
│       │   └── Unloading.py       # wine carrier unload flow
│       ├── classes/           # data model classes
│       │   ├── AutoResponse.py
│       │   ├── BoozeCarrier.py
│       │   ├── CorkedUser.py
│       │   └── Cruise.py
│       ├── database/
│       │   └── database.py    # Database class: SQLite via aiosqlite-like sync API, all bot state
│       ├── modules/
│       │   ├── ErrorHandler.py    # global on_app_command_error, on_text_command_error, custom exceptions
│       │   ├── PHcheck.py         # public holiday check via EDSM API
│       │   ├── Settings.py        # JSON settings file (departure status, timed unloads)
│       │   ├── Views.py           # DynamicButton for persistent Discord UI components
│       │   ├── boozeSheetsApi.py  # BoozeSheetsApi client (REST + WebSocket to BoozeSheets backend)
│       │   └── helpers.py         # check_roles/check_command_channel decorators, is_staff, etc.
│       └── data/              # empty; runtime data written here in dev
├── tests/
│   ├── test_ph_check.py
│   └── test_data/
│       ├── test_data.py
│       ├── peak_faction_holiday_response.json
│       └── peak_faction_no_holiday_response.json
└── .github/
    ├── dependabot.yml         # monthly uv dependency group updates
    └── workflows/
        └── container.yml      # Docker build+push on v* tags
```

---

## Architecture and dependency order

Import dependencies flow in this direction (no circular imports):

```
ptn_utils (external)
    ↓
constants.py          ← imports ptn_utils, discord, dotenv; creates the `bot` object
    ↓
modules/ErrorHandler.py   ← imports constants
modules/helpers.py        ← imports constants, ErrorHandler
modules/Settings.py       ← imports constants
modules/PHcheck.py        ← imports constants, boozeSheetsApi
modules/boozeSheetsApi.py ← imports constants, helpers
modules/Views.py          ← imports ptn_utils (no local module deps)
    ↓
classes/*                 ← import helpers, constants
    ↓
database/database.py      ← imports constants, classes
    ↓
botcommands/*             ← import all of the above
    ↓
application.py            ← imports all botcommands cogs, constants, ErrorHandler, Views
```

Key rules:
- `constants.py` must not import from `botcommands/`, `classes/`, `database/`, or `modules/`
- `modules/helpers.py` imports from `constants` and `ErrorHandler` only
- `database/database.py` is a leaf that everything else may use
- `botcommands/` cogs may freely import across the codebase but must not import from other cogs (except `PublicHoliday.py` which imports `Cleaner`)

---

## Key constants and patterns

- **Bot object**: `ptn.boozebot.constants.bot` — a `GetFetchBot` instance. Always import the singleton from `constants`, never create a new one.
- **Carrier ID format**: `XXX-XXX` matched by `CARRIER_ID_RE` in `constants.py`. Characters `O` and `I` are excluded from valid IDs.
- **Role/channel IDs**: All come from `ptn_utils.global_constants` (dev vs prod values selected automatically based on `PTN_SERVICE` env var). Never hardcode Discord IDs.
- **Logging**: Always use `get_logger("boozebot.<module_name>")` from `ptn_utils.logger.logger`. Never use `print()` or the stdlib `logging` module directly.
- **Error handling**: Raise `CustomError`, `GenericError`, `CommandRoleError`, or `CommandChannelError` from `modules/ErrorHandler.py`. The global handler in `application.py` sends appropriate Discord embeds.
- **Settings persistence**: Use the `settings` singleton from `modules/Settings.py` for runtime-configurable bot settings.
- **BoozeSheets API**: Use the `booze_sheets_api` singleton from `modules/boozeSheetsApi.py` for all cruise/carrier data operations. Do not query the database for carrier data — use this API.

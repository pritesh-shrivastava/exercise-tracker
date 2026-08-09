# exercise-tracker

Personal workout tracker. Primary interface is the private mobile web form over Tailscale. Reporting, backups, DB inspection, and advisory coaching run through local scripts and SQLite. Python + SQLite. No external runtime dependencies.

## Quick commands

```bash
uv run python scripts/summary.py                           # recent activity
uv run python scripts/summary.py --prs                     # personal records (compact, one line per exercise)
# (use --prs for any weekly PR summary automation; no separate weekly_pr_summary script)
uv run python scripts/summary.py --coach                   # DB-backed advisory coaching prompts
uv run python scripts/web_form.py --host 127.0.0.1 --port 8765  # local form; production uses systemd + Tailscale Serve
uv run pytest                                         # run tests
uv run ruff check .                                   # lint
uv run mypy tracker/ scripts/summary.py scripts/web_form.py  # type check
uv run vulture tracker/ tests/ scripts/summary.py scripts/web_form.py  # dead code check
sqlite3 data/workouts.sqlite                          # inspect/edit DB directly
```

## Project structure

```
tracker/          — core library (models, normalizer, core DB helpers, PR/progression reports)
scripts/          — entry points and utilities (summary.py, web_form.py, backfill_structured.py, backup_db.py, restore_db.sh)
tests/            — pytest suite (test_normalizer.py, test_reports.py, test_web_form.py)
query_db.py       — does not exist; use `sqlite3 data/workouts.sqlite` directly
design.md         — data model, variation rules, logging behaviour
```

## Key conventions

- **Weight stored as total** (not per-hand), with `per_hand` boolean flag
- **DB path**: `data/workouts.sqlite` in repo root
- **15 columns**: id, logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source, sets, reps, weight_kg, equipment, per_hand, body_part
- **Auto-migration**: `ensure_db()` in `tracker/core.py` adds missing columns on startup
- **Columns to hide**: `details`, `raw_text`, `id` when displaying
- **Valid variations**: `default`, `flat`, `incline`, `decline`, `short grip`, `wide grip`, `reverse grip`
- **Form defaults**: every predefined exercise in `scripts/web_form.py` should have nonblank default equipment and body-part metadata; selecting an exercise pre-fills those fields
- **PR/progression filters**: `/prs?part=...` and `/progression?part=...` use the same `BODY_PART_ORDER` body-part dropdown
- **Progression charts**: web-only `/progression`, grouped by exercise + variation, minimum 3 weighted entries, ordered by `BODY_PART_ORDER`; chart uses full history, table shows latest 3 entries
- **Network access**: serve `scripts/web_form.py` on localhost; production exposes it tailnet-only with Tailscale Serve. Do not expose it publicly without auth
- **Web form port**: always use/restart the canonical `127.0.0.1:8765` service. If the port is busy, restart the existing service/process on `8765`; do not start a second form server on a different port.

## Workflow routing

Workout data entry is form-only. Do not parse pasted workouts into DB rows and do not mutate `data/workouts.sqlite` from chat unless the user explicitly asks for a direct DB maintenance operation.

- User pastes workout lines → do not log them; direct them to the private form URL.
- User asks for summary, PRs, stats, coaching, or what to train next → use `uv run python scripts/summary.py` with the appropriate flag.
- User asks for progression charts in the app → inspect or update `/progression` in `scripts/web_form.py`; the CLI has no chart flag.
- User asks to see the table, DB, rows, browse data, top N, last N → use `sqlite3 data/workouts.sqlite` directly.
- User asks for DB anomalies/cleanup candidates → check blank equipment, missing non-bodyweight weights, invalid body parts/variations, duplicate-looking rows, and mixed equipment/body-part values per exercise.
- Backups → use `uv run python scripts/backup_db.py` from cron/systemd or an explicit shell session.

Do not use sub-agents for workout updates or DB queries. Sub-agents may only be used for code fixes or audits, never for mutating `data/workouts.sqlite`.

## Health Stack

- typecheck: uv run mypy tracker/ scripts/summary.py scripts/web_form.py
- lint: uv run ruff check .
- test: uv run pytest
- deadcode: uv run vulture tracker/ tests/ scripts/summary.py scripts/web_form.py

## Canonical exercise names (normalizer)

Key mappings in `tracker/normalizer.py` — use these exact names in the DB:
- `shoulder press` / `should press` → `Dumbbell Shoulder Press`
- `bicep curl` → `Dumbbell Bicep Curl`
- `leg curl` → `Hamstring Curl`
- `leg press` → `45 Degree Leg Press`
- `seated row` / `horizontal row` → `Chest Supported Rows`
- `seated row machine` → `Seated Cable Row`
- `abs crunch` → `Seated Abs Crunch Machine`
- `lat pull down` (any grip) → `Lat Pull Down` + variation column (`short grip` / `wide grip`)
- reverse-grip cable curls and tricep pushdowns → variation column `reverse grip`
- `tricep pushdown` → equipment is `cable` (not machine)

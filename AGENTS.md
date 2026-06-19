# exercise-tracker

Personal workout tracker. Primary interface is the private mobile web form over Tailscale. Hermes Agent is for summaries, PRs, backups, and DB inspection only. Python + SQLite. No external runtime dependencies.

## Quick commands

```bash
uv run python scripts/summary.py                           # recent activity
uv run python scripts/summary.py --prs                     # personal records (compact, one line per exercise)
uv run python scripts/web_form.py --host 127.0.0.1  # local form; production uses systemd + Tailscale Serve
uv run pytest                                         # run tests
uv run ruff check .                                   # lint
uv run mypy tracker/ scripts/summary.py scripts/web_form.py  # type check
uv run vulture tracker/ tests/ scripts/summary.py scripts/web_form.py  # dead code check
uv run python scripts/backfill_structured.py           # backfill structured columns after schema change
sqlite3 data/workouts.sqlite                          # inspect/edit DB directly
```

## Project structure

```
tracker/          — core library (models, normalizer, core DB helpers, PR reports)
scripts/          — entry points and utilities (summary.py, web_form.py, backfill_structured.py, backup_db.py, restore_db.sh)
tests/            — pytest suite (test_normalizer.py, test_reports.py, test_web_form.py)
skills/           — Hermes agent SKILL.md definitions (workout-summary, backup-db, query-db)
query_db.py       — does not exist; use `sqlite3 data/workouts.sqlite` directly
design.md         — data model, variation rules, logging behaviour
```

## Key conventions

- **Weight stored as total** (not per-hand), with `per_hand` boolean flag
- **DB path**: `data/workouts.sqlite` in repo root
- **14 columns**: id, logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source, sets, reps, weight_kg, equipment, per_hand
- **Auto-migration**: `ensure_db()` in `tracker/core.py` adds missing columns on startup
- **Columns to hide**: `details`, `raw_text`, `id` when displaying
- **Network access**: serve `scripts/web_form.py` on localhost; production exposes it tailnet-only with Tailscale Serve. Do not expose it publicly without auth

## Skill routing

When the user's request matches an available exercise-tracker skill, invoke it via the skill tool. Workout data entry is form-only; use Hermes for summaries, PRs, backups, and raw DB inspection:

- User pastes workout lines → do not log them; direct them to the private form URL
- User asks for summary, PRs, stats → load `workout-summary` skill
- User asks for backup or database save → load `backup-db` skill
- User asks to see the table, DB, rows, browse data, top N, last N → load `query-db` skill

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
- `seated row machine` → `Seated Row Machine`
- `abs crunch` → `Seated Abs Crunch Machine`
- `lat pull down` (any grip) → `Lat Pull Down` + variation column (`short grip` / `wide grip`)
- `tricep pushdown` → equipment is `cable` (not machine)

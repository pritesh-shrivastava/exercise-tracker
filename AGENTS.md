# exercise-tracker

Personal workout tracker. Hermes Agent is the Telegram interface. Python + SQLite. No external runtime dependencies.

## Quick commands

```bash
uv run python log_workout.py "squats 3x5 @ 100kg"   # log a workout
uv run python summary.py                              # recent activity
uv run python summary.py --prs                        # personal records (compact, one line per exercise)
uv run pytest                                         # run tests (98 tests)
uv run ruff check .                                   # lint
uv run mypy tracker/ summary.py log_workout.py        # type check
uv run vulture tracker/ tests/ *.py                   # dead code check
uv run python scripts/backfill_structured.py           # backfill structured columns after schema change
sqlite3 data/workouts.sqlite                          # inspect/edit DB directly
```

## Project structure

```
tracker/          — core library (parser, normalizer, core DB helpers, PR reports)
scripts/          — utilities (backfill_structured.py, restore_db.sh, weekly_pr_summary.py)
tests/            — pytest suite (test_parser.py, test_normalizer.py, test_reports.py)
skills/           — Hermes agent SKILL.md definitions (log-workout, workout-summary, backup-db, query-db)
log_workout.py    — CLI entry point for logging
summary.py        — CLI entry point for summaries and PRs
query_db.py       — does not exist; use `sqlite3 data/workouts.sqlite` directly
design.md         — data model, variation rules, logging behaviour
```

## Key conventions

- **Weight stored as total** (not per-hand), with `per_hand` boolean flag
- **DB path**: `data/workouts.sqlite` in repo root
- **14 columns**: id, logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source, sets, reps, weight_kg, equipment, per_hand
- **Auto-migration**: `ensure_db()` in `tracker/core.py` adds missing columns on startup
- **Columns to hide**: `details`, `raw_text`, `id` when displaying

## Skill routing

When the user's request matches an available exercise-tracker skill, invoke it via the skill tool:

- User pastes workout lines → load `log-workout` skill
- User asks for summary, PRs, stats → load `workout-summary` skill
- User asks for backup or database save → load `backup-db` skill
- User asks to see the table, DB, rows, browse data, top N, last N → load `query-db` skill

Do not use sub-agents for workout logging, workout updates, or DB queries. Logging is
stateful and must stay in the active Health conversation buffer. Sub-agents may only
be used for code fixes or audits, never for mutating `data/workouts.sqlite`.

## Health Stack

- typecheck: uv run mypy tracker/ summary.py log_workout.py
- lint: uv run ruff check .
- test: uv run pytest
- deadcode: uv run vulture tracker/ tests/ *.py

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

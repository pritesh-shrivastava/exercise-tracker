# Exercise Tracker Design

## Purpose

This is a small, private workout tracker backed by SQLite. The database is the source of truth. The daily logging interface is the mobile web form over Tailscale. Reports, raw inspection, backups, and advisory coaching prompts are local scripts over SQLite.

## Data Model

The database uses two tables:

- `workouts` (per-set/session rows)
- `exercise_meta` (canonical per-exercise metadata)

The `workouts` table has 12 columns:

| Column | Meaning |
|--------|---------|
| `id` | SQLite primary key |
| `logged_at` | IST timestamp when the row was written |
| `workout_date` | IST training date |
| `workout_type` | usually `strength`; legacy rows may use `cardio` or `note` |
| `exercise` | canonical exercise name |
| `variation` | `default`, `flat`, `incline`, `decline`, `short grip`, `wide grip`, or `reverse grip` |
| `details` | compact display string derived from structured fields |
| `raw_text` | trace field; form rows store the selected exercise |
| `source` | origin, usually `form` |
| `sets` | set count |
| `reps` | reps per set |
| `weight_kg` | total load in kg, not per-hand |

The `exercise_meta` table has 5 columns:

| Column | Meaning |
|--------|---------|
| `exercise` | canonical exercise name (primary key) |
| `movement_type` | `compound` or `isolation` |
| `body_part` | canonical body-part tag used for grouping/filtering |
| `equipment` | equipment category: `bodyweight`, `dumbbells`, `barbell`, `machine`, `cable`, `kettlebell`, `smith machine`, `band`, `other`, or blank only for custom/edge cases |
| `per_hand` | boolean flag for dumbbell per-hand display |

Important invariants:
- Store total load in `weight_kg`. For dumbbells, `exercise_meta.per_hand=1` means display each-hand weight as `weight_kg / 2`.
- `details` is derived display text; reports use structured fields.
- `exercise_meta` is canonical for `body_part`/`equipment`/`per_hand`; reports fall back to name-based classification when body_part is blank.
- Defaults are seeded from `tracker/exercises.py` into `exercise_meta` for new DBs.
- `ensure_db()` in `tracker/core.py` creates and auto-migrates missing columns.

## Entry Rules

Workout logging happens only through `scripts/web_form.py`.

Form pages:
- `Log` writes one structured strength row per submitted row.
- `Today` supports exact same-day corrections and deletes.
- `Recent` shows recent saved rows while hiding internal/trace columns.
- `PRs` renders the same PR report path as `scripts/summary.py --prs`, with an optional `?part=BodyPart` filter.
- `Progression` renders SVG weight-history charts from structured weighted rows, with an optional `?part=BodyPart` filter.

The `Log` page's predefined exercise dropdown and defaults use `exercise_meta` as the canonical source. `tracker/exercises.py` is used only to seed `exercise_meta` for new databases.

The form runs on `127.0.0.1:8765` and is exposed privately with Tailscale Serve. It has no public-internet authentication layer, so do not bind it to a public interface without an auth proxy. HTML responses are gzip-compressed for clients that advertise support.

## Normalization

`tracker/normalizer.py` owns canonical exercise names and typo recovery. Keep normalizer changes in code/tests, not in ad hoc database edits.

Variation rules:
- Non-bench strength entries use `default` unless grip is meaningful.
- Bench uses `flat`, `incline`, or `decline`.
- Lat Pull Down grip is stored in `variation` as `short grip` or `wide grip`.
- Reverse-grip cable curls and tricep pushdowns are stored in `variation` as `reverse grip`.

## Reports

`scripts/summary.py` is the reporting entry point:

| Command | Use |
|---------|-----|
| `uv run python scripts/summary.py` | recent activity |
| `uv run python scripts/summary.py --prs` | compact personal records |
| `uv run python scripts/summary.py --coach` | advisory coaching prompts |

Report rules:
- Hide `default` variation in display output.
- PR scoring is highest weight, then reps, then sets, then earliest date.
- Body-part display uses saved `body_part` tags first, then classifier fallback in `tracker/reports.py`.
- Coaching is advisory only: body-part recency, recent coverage, and stale weighted PRs that may be ready for a small weight increase.

Progressive overload (rep targets for "add weight"):
- **Isolation exercises:** 15 reps
- **Compound exercises:** 12 reps

These targets are driven by `exercise_meta.movement_type` (seeded from `tracker/exercises.py`).
- Progression charts group by canonical exercise plus variation, ignore rows without `weight_kg`, require at least 3 weighted entries, and order charts by `BODY_PART_ORDER`.
- Progression SVGs plot full weighted history; the compact table under each chart shows only the latest 3 entries.
- The PR and progression pages both use `part` query-parameter filtering with values from `BODY_PART_ORDER`.

## Local Operations

All workout writes use the private web form. Local scripts may read the database for summaries, PRs, coaching prompts, backups, and raw inspection.

- Use `uv run python scripts/summary.py` for recent activity.
- Use `uv run python scripts/summary.py --prs` for personal records.
- For "what should I train next?", run `uv run python scripts/summary.py --coach`.
- Use `sqlite3 data/workouts.sqlite` for direct DB inspection.
- Send new logs, corrections, and deletes through the private form.
- Avoid medical or injury diagnosis.

Useful anomaly checks before/after direct maintenance:
- Blank equipment: `SELECT exercise FROM exercise_meta WHERE equipment IS NULL OR equipment = '';`
- Missing non-bodyweight load: `SELECT id, workout_date, exercise FROM workouts WHERE weight_kg IS NULL;` (interpret using `exercise_meta.equipment`)
- Mixed exercise equipment: `SELECT exercise, GROUP_CONCAT(DISTINCT equipment), COUNT(*) FROM workouts GROUP BY exercise HAVING COUNT(DISTINCT equipment) > 1;` (should be empty if equipment is fully normalized)
- Invalid body parts or variations should be treated as data cleanup, not as reporting display problems.

## Maintenance

Recommended jobs and checks:
- Nightly backup: `uv run python scripts/backup_db.py`.
- After schema changes: `uv run python scripts/backfill_structured.py`.
- Tests: `uv run pytest`.
- Lint/type/dead-code checks are listed in `AGENTS.md`.

The repo plus `data/workouts.sqlite` and required backup env vars should be enough to restore the tracker.

# Exercise Tracker Design

## Purpose

This is a small, private workout tracker backed by SQLite. The database is the source of truth. The daily logging interface is the mobile web form over Tailscale; Hermes/Telegram is read-only for summaries, PRs, raw inspection, and advisory coaching from past data.

## Data Model

The `workouts` table has 14 columns:

| Column | Meaning |
|--------|---------|
| `id` | SQLite primary key |
| `logged_at` | IST timestamp when the row was written |
| `workout_date` | IST training date |
| `workout_type` | usually `strength`; legacy rows may use `cardio` or `note` |
| `exercise` | canonical exercise name |
| `variation` | `default`, `flat`, `incline`, `decline`, `short grip`, or `wide grip` |
| `details` | compact display string derived from structured fields |
| `raw_text` | trace field; form rows store the selected exercise |
| `source` | origin, usually `form` |
| `sets` | set count |
| `reps` | reps per set |
| `weight_kg` | total load in kg, not per-hand |
| `equipment` | equipment category |
| `per_hand` | boolean flag for dumbbell per-hand display |

Important invariants:
- Store total load in `weight_kg`. For dumbbells, `per_hand=1` means display each-hand weight as `weight_kg / 2`.
- `per_hand=1` is valid only with `equipment='dumbbells'`.
- `details` is derived display text; reports use structured fields.
- `ensure_db()` in `tracker/core.py` creates and auto-migrates missing columns.

## Entry Rules

Workout logging happens only through `scripts/web_form.py`.

Form pages:
- `Log` writes one structured strength row per submitted row.
- `Today` supports exact same-day corrections and deletes.
- `PRs` renders the same PR report path as `scripts/summary.py --prs`.

The form runs on `127.0.0.1:8765` and is exposed privately with Tailscale Serve. It has no public-internet authentication layer, so do not bind it to a public interface without an auth proxy.

## Normalization

`tracker/normalizer.py` owns canonical exercise names and typo recovery. Keep normalizer changes in code/tests, not in ad hoc database edits.

Variation rules:
- Non-bench strength entries use `default` unless grip is meaningful.
- Bench uses `flat`, `incline`, or `decline`.
- Lat Pull Down grip is stored in `variation` as `short grip` or `wide grip`.

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
- Body-part classification lives in `tracker/reports.py`.
- Coaching is advisory only: body-part recency, recent coverage, and stale high-rep weighted PRs that may be ready for a small weight increase.

## Hermes And Telegram

Hermes is a read-only assistant for workout data in Telegram. It may query SQLite-backed reports and inspect rows, but it must not log, edit, or delete workouts.

Repo skills:
- `workout-summary`: summaries, PRs, progress questions, and coaching.
- `query-db`: raw row inspection, excluding hidden columns.

No backup skill exists. Backups run outside Hermes skill routing via `scripts/backup_db.py` from cron/systemd or an explicit shell session.

Health topic binding should preload only the interactive read-only skills:

```yaml
extra:
  dm_topics:
  - chat_id: 5727496535
    topics:
    - name: Health
      thread_id: 7218
      skill:
      - query-db
      - workout-summary
```

Telegram coaching rules:
- Use SQLite-backed output only; never use Hermes memory as truth.
- For "what should I train next?", run `uv run python scripts/summary.py --coach`.
- Keep interpretation short and grounded in the report.
- Send new logs, corrections, and deletes back to the private form.
- Avoid medical or injury diagnosis.

## Maintenance

Recommended jobs and checks:
- Nightly backup: `uv run python scripts/backup_db.py`.
- After schema changes: `uv run python scripts/backfill_structured.py`.
- Tests: `uv run pytest`.
- Lint/type/dead-code checks are listed in `AGENTS.md`.

Runtime Hermes memory is not part of backup or restore. The repo plus `data/workouts.sqlite` and required env vars should be enough to restore the tracker.

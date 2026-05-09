# Exercise Tracker Design

## Purpose

This tracker keeps workout logs portable and easy to move between VPS instances.
The database is the source of truth. Hermes Agent is the sole interface — via Telegram for logging and queries, and via cron for scheduled reports. The Python scripts are tools that Hermes calls; they are not run directly by the user.

## Data model

Each workout row stores:

- `logged_at` — ISO timestamp in IST
- `workout_date` — IST date
- `workout_type` — `strength`, `cardio`, or `note`
- `exercise` — canonical exercise name
- `variation` — exercise variation label
- `details` — compact set/reps/weight summary
- `raw_text` — original pasted input
- `source` — where the row came from

## Variation rules

- Non-bench strength entries use `default`
- Bench press entries use `flat` for the base variation
- Bench press incline and decline are tracked as separate rows
- Legacy summary output may still encounter old combined rows, but new logs should not create them

## Logging behavior

When a pasted line contains both incline and decline bench wording:

- the parser creates two strength rows
- one row gets `incline`
- one row gets `decline`
- both keep the same raw text for traceability

## Summary behavior

- `default` variations stay hidden in Telegram summary output
- `flat`, `incline`, and `decline` are shown for bench press
- the summary is grouped by body part first, then exercise

Summary responses are tiered — Hermes picks the right one based on natural language:

| Level | Example trigger | Script |
|---|---|---|
| Short | "show recent workouts" | `python summary.py` |
| Full PRs | "show my PRs", "best lifts" | `python summary.py --prs` |

## Hermes skills architecture

Skills live in `skills/<name>/SKILL.md` and teach Hermes the procedures for this tracker. The agent loads a skill's full content only when the task matches — descriptions are loaded at startup, full bodies on demand.

Three planned skills:
- `log-workout` — parse and insert lines, handle incline/decline split, confirm count
- `workout-summary` — pick the right summary tier and format for Telegram
- `backup-db` — dump SQLite, upload to Azure Blob, prune to last 3 copies

The data layer (`tracker/core.py`, `tracker/parser.py`) is intentionally separate from the agent layer. Skills call the Python scripts; they do not replicate logic.

## Hermes memory

Hermes memory stores facts that persist across sessions but are not derivable from the database:

- Current PRs — overwritten automatically after each weekly `python summary.py --prs` run
- Training preferences: Pull→Push→Legs priority rotation, kg not lbs, IST timezone
- Voice memos sent via Telegram are auto-transcribed by Hermes before being logged

## Maintenance notes

- Keep raw text intact
- Normalize exercise names in code, not by rewriting user input
- Backfill older rows when schema rules change
- Keep the repo copyable as-is, with SQLite and env vars being enough to restore it
- Skills and memory belong to the agent layer — they are not part of the database backup, but should be committed to the repo so they migrate with it

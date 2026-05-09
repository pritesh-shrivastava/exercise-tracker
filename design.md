# Exercise Tracker Design

## Purpose

This tracker keeps workout logs portable and easy to move between VPS instances.
The database is the source of truth; the Telegram bot and summary scripts are just interfaces.

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

## Maintenance notes

- Keep raw text intact
- Normalize exercise names in code, not by rewriting user input
- Backfill older rows when schema rules change
- Keep the repo copyable as-is, with SQLite and env vars being enough to restore it

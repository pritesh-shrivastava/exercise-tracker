---
name: workout-summary
description: Use when the user asks for a summary, stats, progress, recent workouts, personal records, PRs, this week's training, best lifts, or how their training is going.
version: 1.0.0
---

## When to use

- Default `/summary` or "show my stats" or "recent workouts" → short summary (last 5 entries)
- "This week", "weekly summary", "how did I do this week" → weekly volume by muscle group
- "PRs", "personal records", "full summary", "best lifts" → PR summary by body part

## Procedure

### Short summary (default)
```
python summary.py
```
Returns: total entries, date range, breakdown by type, last 5 entries.

### PR summary (full)
```
python summary.py --prs
```
Returns: best set per exercise + variation, grouped by body part (Chest, Back, Shoulders, Arms, Legs, Core, Other).

Use `--db <path>` if `WORKOUT_DB_PATH` points to a non-default location.

## Pitfalls

- `summary.py` shows the last 5 entries only — not a weekly breakdown. For weekly volume, query the DB directly or extend `fetch_summary()` in `tracker_core.py`.
- `pr_summary.py` ranks by weight first, then reps, then sets. High-rep low-weight entries may not surface as PRs even if they represent progress.
- `default` variations are hidden in summary output; `flat`, `incline`, `decline` are shown explicitly for bench press.

## After the weekly PR summary

After running `python summary.py --prs`, update Hermes memory with the latest PRs so they're available as fast-access context in future sessions without querying the DB:

1. Parse the PR output — best set per exercise + variation.
2. Write the results into memory under a `## Personal Records` section, replacing any previous entries.
3. Include the date so it's clear when the snapshot was taken.

This runs automatically as part of the weekly cron — no manual update needed.

## Verification

Both scripts print to stdout. Output should not be empty if workouts have been logged.

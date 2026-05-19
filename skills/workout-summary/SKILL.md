---
name: workout-summary
description: Use when the user asks for a summary, stats, progress, recent workouts, personal records, PRs, this week's training, best lifts, or how their training is going.
version: 1.0.0
---

## When to use

When the user says ANY of these in the context of the exercise tracker:
- "prs", "PRs", "PR", "personal records", "best lifts", "full summary", "show PRs"
- "summary", "stats", "progress", "recent workouts", "how am I doing"
- "this week", "weekly summary", "how did I do this week"
- Any short command that could mean exercise PRs (especially single-word: "prs", "PRs", "stats")

**Important routing note**: "prs" is the most common command. When the user says "prs" without qualification and the exercise tracker repo exists, this is ALWAYS the skill to load — not github-pr-workflow.

## Procedure

### Short summary (default)
```
python summary.py
```
Returns: total entries, date range, breakdown by type, then recent activity with body-part labels and exercise names only (no sets, reps, weight, equipment, or details).

### PR summary (full)
```
python summary.py --prs
```
Returns: best set per exercise + variation, grouped by body part (Chest, Back, Shoulders, Arms, Legs, Core, Other).


## Pitfalls

- `summary.py` shows the last 5 recent days only (body-part label + exercise names) — not a weekly breakdown. For weekly volume, query the DB directly or extend `fetch_recent_activity()` in `tracker/core.py`.
- `pr_summary.py` ranks by weight first, then reps, then sets. High-rep low-weight entries may not surface as PRs even if they represent progress.
- `default` variations are hidden in summary output; `flat`, `incline`, `decline` are shown explicitly for bench press.

## After the weekly PR summary

The weekly cron job now uses `scripts/weekly_pr_summary.py` as a `no_agent` script. It:
1. Runs `python summary.py --prs` to generate the PR output.
2. Parses the output into structured markdown.
3. Updates MEMORY.md with the `## Personal Records` section.

This happens automatically — no manual steps needed.

For manual ad-hoc runs, just use `python summary.py --prs` directly. The memory update is handled by the cron script.

## Verification

Both scripts print to stdout. Output should not be empty if workouts have been logged.

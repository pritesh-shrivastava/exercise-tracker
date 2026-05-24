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

### Output delivery rule

**Deliver raw command output verbatim.** When the user asks for PRs, summary, or stats, paste the raw `summary.py` output directly. Do NOT convert to markdown tables, bullet lists, or add commentary. The user wants to see the exact shell output. Use a code block (` ``` `). Only summarize or analyze if the user explicitly asks "what do you think?" or "analyze this."

This applies to ALL summary commands: `python summary.py`, `python summary.py --prs`, and any future summary variants.


## Pitfalls

- `summary.py` shows the last 5 recent days only (body-part label + exercise names) — not a weekly breakdown. For weekly volume, query the DB directly or extend `fetch_recent_activity()` in `tracker/core.py`.
- `pr_summary.py` ranks by weight first, then reps, then sets. High-rep low-weight entries may not surface as PRs even if they represent progress.
- `default` variations are hidden in summary output; `flat`, `incline`, `decline` are shown explicitly for bench press.

## Schedule

This skill is registered as a Hermes cron job that runs every Sunday at 10:00 IST. Install once on the VPS:

```
hermes cron create "0 10 * * 0" "Generate weekly PR summary and update Hermes memory with latest personal records" --skill workout-summary
```

Notes:
- The cron expression is evaluated in the Hermes process's local timezone. The VPS runs on IST (`Asia/Kolkata`), so `0 10 * * 0` fires at 10:00 IST on Sunday. On a UTC VPS, use `30 4 * * 0` (04:30 UTC = 10:00 IST).
- Verify the job was created: `hermes cron list`. Job definitions are persisted to `~/.hermes/cron/jobs.json`; execution outputs land in `~/.hermes/cron/output/{job_id}/`.
- To change the schedule, delete and recreate: `hermes cron delete <job_id>` then re-run the create command.

## After the weekly PR summary

The weekly cron job now uses `scripts/weekly_pr_summary.py` as a `no_agent` script. It:
1. Runs `python summary.py --prs` to generate the PR output.
2. Parses the output into structured markdown.
3. Updates MEMORY.md with the `## Personal Records` section.

This happens automatically — no manual steps needed.

For manual ad-hoc runs, just use `python summary.py --prs` directly. The memory update is handled by the cron script.

## Pitfalls

- **Emoji-heavy output may not render on Telegram.** `summary.py --prs` uses emoji body-part labels (🩻🧱🧢💪🦵⚡). If the user says they can't see the output or asks for it again, DO NOT resend the raw emoji output. Instead, reformat without emojis using plain section headers (`### Chest`, `### Back`, etc.) inside a code block. The user prefers to see the data, not the emoji. If the raw output rendered fine on your end but the user still says \"Cant see\", trust them — strip and reformat.

## Verification

Both scripts print to stdout. Output should not be empty if workouts have been logged.

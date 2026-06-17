---
name: workout-summary
description: Use when the user asks for a summary, stats, progress, recent workouts, personal records, PRs, this week's training, best lifts, or how their training is going.
version: 1.1.0
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
cd /home/azureuser/exercise-tracker && uv run python summary.py
```
Returns: total entries, date range, breakdown by type, then recent activity with body-part labels and exercise names only (no sets, reps, weight, equipment, or details).

### PR summary (full)
```
cd /home/azureuser/exercise-tracker && uv run python summary.py --prs
```
Returns: best set per exercise + variation, grouped by body part (Chest, Back, Shoulders, Biceps, Triceps, Legs, Core, Other).

### Output delivery rule

**Deliver raw command output verbatim.** When the user asks for PRs, summary, or stats, paste the raw `summary.py` output directly. Do NOT convert to markdown tables, bullet lists, or add commentary. The user wants to see the exact shell output. Use a code block (` ``` `). Only summarize or analyze if the user explicitly asks "what do you think?" or "analyze this."

This applies to ALL summary commands: `uv run python summary.py`, `uv run python summary.py --prs`, and any future summary variants.


## Pitfalls

- `summary.py` shows the last 5 recent days only (body-part label + exercise names) — not a weekly breakdown. For weekly volume, query the DB directly or extend `fetch_recent_activity()` in `tracker/core.py`.
- `pr_summary.py` ranks by weight first, then reps, then sets. High-rep low-weight entries may not surface as PRs even if they represent progress.
- **PR date shows earliest achievement, not most recent.** When weight and reps are tied across multiple sessions, the PR date is the FIRST time you hit that weight/reps combo — not the latest. If a PR date looks suspiciously recent when you know you've hit that weight before, the tiebreaker may be wrong; check `tracker/reports.py` `_best_sets()` for the `_neg_date` logic.
- `default` variations are hidden in summary output; `flat`, `incline`, `decline` are shown explicitly for bench press.
- **Variations split by weight.** `format_prs_compact()` shows one PR line per distinct PR *weight* within an exercise: variations with different weights (e.g. Lat Pull Down `default` @ 35kg vs `[short grip, wide grip]` @ 31kg) appear on **separate lines**; variations that share the same PR weight stay **clubbed** in one `[a, b]` bracket. So the same exercise can legitimately occupy multiple lines — that's intended, not a duplicate.

## Web form PRs

The private web form has a `PRs` page that renders the same DB-backed report path as `summary.py --prs`. Use that page for routine phone review. Use this skill when the user asks for PRs or summaries in Telegram.

Do not answer PR questions from Hermes memory. Runtime memory is not the source of truth and is no longer maintained by a weekly PR cron. Always use SQLite-backed output.

## Pitfalls

- **Emoji-heavy output may not render on Telegram.** `summary.py --prs` uses emoji body-part labels (🩻🧱🧢💪🔻🦵⚡). If the user says they can't see the output or asks for it again, DO NOT resend the raw emoji output. Instead, reformat without emojis using plain section headers (`### Chest`, `### Back`, etc.) inside a code block. The user prefers to see the data, not the emoji. If the raw output rendered fine on your end but the user still says \"Cant see\", trust them — strip and reformat.

- **When showing PRs, always deliver raw command output verbatim in code blocks without any summary, conversion to tables, or commentary unless explicitly requested by the user.**

- **For PRs on a specific date (e.g., today), query the database directly for exact filtering and present results in raw or JSON format as needed.**

## Verification

Both scripts print to stdout. Output should not be empty if workouts have been logged.

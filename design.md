# Exercise Tracker Design

## Purpose

This tracker keeps workout logs portable and easy to move between VPS instances.
The database is the source of truth. Hermes Agent is the sole interface — via Telegram for logging and queries, and via cron for scheduled reports. The Python scripts are tools that Hermes calls; they are not run directly by the user.

## Data model

### Schema (13 columns)

Each workout row stores:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | auto-increment |
| `logged_at` | TEXT | ISO timestamp in IST |
| `workout_date` | TEXT | IST date |
| `workout_type` | TEXT | `strength`, `cardio`, or `note` |
| `exercise` | TEXT | canonical exercise name (via normalizer) |
| `variation` | TEXT | `default`, `flat`, `incline`, `decline`, `short grip`, `wide grip` |
| `details` | TEXT | compact set/reps/weight summary string |
| `raw_text` | TEXT | original pasted input |
| `source` | TEXT | origin of row (`manual`, `telegram`, etc.) |
| `sets` | INTEGER | parsed number of sets |
| `reps` | INTEGER | parsed number of reps |
| `weight_kg` | REAL | total weight in kg (NOT per-hand) |
| `equipment` | TEXT | `dumbbells`, `barbell`, `machine`, `cable`, `bodyweight`, `kettlebell`, `smith machine`, `band`, `other` |
| `per_hand` | INTEGER | boolean: was weight entered as per-hand? |

### Weight convention

- **Total weight stored** (NOT per-hand), with `per_hand` boolean flag
- Example: Dumbbell Shoulder Press "15 kg each hand" → `weight_kg=30.0, per_hand=1`
- Display format: `3x15 @ 30 (15 ea.)`
- Goblet squats: single dumbbell held with both hands, `per_hand=0`

### Auto-migration

`ensure_db()` in `tracker/core.py` creates the table on first call and **auto-adds** missing columns on subsequent calls (no manual migration needed). Indexes on `workout_date` and `workout_type` are also created.

## Variation rules

- Non-bench strength entries use `default` unless a grip is specified
- Bench press entries use `flat` for the base variation; incline and decline are tracked as separate rows
- Lat Pull Down grip variations use `short grip` or `wide grip` in the variation column (not in the exercise name)
- Legacy rows that stored grip in the exercise name (e.g. `Lat Pull Down (Short Grip)`) have been migrated to the variation column

## Parsing behaviour

### Strength parsing

Handles these format variants (in priority order):

1. **Continuation lines**: bare `N x M [@ weight]` — inherits exercise from previous line
2. **Weight-first**: `Exercise - 20 kg 3 sets x 15 reps`
3. **Multi-set comma split**: `Exercise - 2 x 15 with 5 + 5 kg, 1 set of 15 rep with 7.5 kg`
4. **Standard**: `exercise N x M [@ weight]`
5. **Multi-set-of inside comma parsing**: `, N set(s) of M rep(s) [@ weight]`

Typo recovery: `woth` → `with`, `dumbell` → `dumbbell`, `biceo` → `bicep`, `calf rause` → `calf raise`, etc.

### Exercise name normalisation

`tracker/normalizer.py` normalizes exercise names to canonical forms:

- Bench press with "press" in text → `Barbell Bench Press` (if "barbell" in text) or `Dumbbell Bench Press` (default)
- Lat pull-down → always `Lat Pull Down`; grip goes into variation column via `detect_variations()`
- Rear delt → `Rear Delt Fly`
- Canonical names: `shoulder press` → `Dumbbell Shoulder Press`, `leg curl` → `Hamstring Curl`, `leg press` → `45 Degree Leg Press`, `seated row` / `horizontal row` → `Seated Row machine`, `abs crunch` → `Seated Abs Crunch Machine`
- Title-case fallback for unknown exercises

### Equipment inference

Keyword-based on exercise name + raw text (combined):

`dumbbells` | `barbell` | `cable` | `machine` | `bodyweight` | `kettlebell` | `smith machine` | `band` | `other`

Machine exercises are detected via a hardcoded set of exercise names (Chest Press, Pec Fly, Lat Pull Down, Seated Row machine, 45 Degree Leg Press, Horizontal Leg Press, etc.).

### Logging behaviour

When a pasted line contains both incline and decline bench wording:
- the parser creates two strength rows
- one row gets `incline` variation
- one row gets `decline` variation
- both keep the same raw text for traceability

### Cardio parsing

Matches: `[distance km/mi] [activity] duration [min/hr] [in HH:MM]`

Examples: `20 min zone 2 cardio`, `5 km run 28 min`, `cycling 45 min`

## Summary behaviour

- `default` variations stay hidden in display output
- `flat`, `incline`, and `decline` are shown for bench press
- Summary is grouped by body part first, then exercise
- PR scoring: highest weight → highest reps → highest sets → earliest date
- PR output is compact: one line per exercise, variations shown inline in brackets

Summary responses are tiered — Hermes picks the right one based on natural language:

| Level | Example trigger | Script |
|-------|----------------|--------|
| Short | "show recent workouts" | `python summary.py` |
| Full PRs | "show my PRs", "best lifts" | `python summary.py --prs` |

### Body part classification

Chest 💪 | Back 🧱 | Shoulders 🧢 | Arms 🏹 | Legs 🦵 | Core ⚡ | Other 📦

Keywords for each group are in `tracker/reports.py:body_part()`. Special rules: `Rear Delt Fly` → Shoulders (not Back), `Hamstring Curl` → Legs (not Arms).

## Hermes skills architecture

Skills live in `skills/<name>/SKILL.md` and teach Hermes the procedures for this tracker. The agent loads a skill's full content only when the task matches — descriptions are loaded at startup, full bodies on demand.

Four skills, all in `skills/`:
- `log-workout` — parse and insert lines, handle incline/decline split, confirm count
- `workout-summary` — pick the right summary tier and format for Telegram
- `backup-db` — dump SQLite + CSV, upload to Azure Blob (retention handled server-side by a 30-day lifecycle policy, not by the skill)
- `query-db` — browse raw table rows, excluding id/raw_text/details

The data layer (`tracker/core.py`, `tracker/parser.py`) is intentionally separate from the agent layer. Skills call the Python scripts; they do not replicate logic.

### Cron jobs

Scheduled via Hermes cron (`hermes cron create ...`, persisted to `~/.hermes/cron/jobs.json`):
1. **PR summary** (weekly): runs `python summary.py --prs` and updates Hermes memory with latest PRs
2. **DB backup** (nightly at 03:00 IST): runs `backup-db` skill to upload SQLite + CSV to Azure Blob. **Write-only** — old blobs are deleted by an Azure lifecycle policy (30-day retention) rather than by the skill itself, after a 2026-05-28 incident where Hermes-executed prune logic deleted the wrong container. Install command and policy JSON live in `skills/backup-db/SKILL.md`.

## Hermes memory

Hermes memory stores facts that persist across sessions but are not derivable from the database:

- Current PRs — overwritten automatically after each weekly `python summary.py --prs` run
- Training preferences: Pull→Push→Legs priority rotation, kg not lbs, IST timezone
- Voice memos sent via Telegram are auto-transcribed by Hermes before being logged

## Maintenance notes

- Keep raw text intact
- Normalize exercise names in code, not by rewriting user input
- Backfill older rows when schema rules change: `uv run python scripts/backfill_structured.py`
- Keep the repo copyable as-is, with SQLite and env vars being enough to restore it
- Skills and memory belong to the agent layer — they are not part of the database backup, but should be committed to the repo so they migrate with it
- After changing parser/normalizer, run `uv run pytest` — 99 tests should pass
- SQLite auto-ALTER in `ensure_db()` handles schema migration on startup; no manual DDL needed

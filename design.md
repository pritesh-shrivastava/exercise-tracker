# Exercise Tracker Design

## Purpose

This tracker keeps workout logs portable and easy to move between VPS instances.
The database is the source of truth. **Mercury** (Hermes Agent) is the sole interface — via Telegram for logging and queries, and via cron for scheduled reports. The Python scripts are tools that Mercury calls; they are not run directly by the user.

## Data model

### Schema (14 columns)

Each workout row stores:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | auto-increment |
| `logged_at` | TEXT | ISO timestamp in IST |
| `workout_date` | TEXT | IST date |
| `workout_type` | TEXT | `strength`, `cardio`, or `note` |
| `exercise` | TEXT | canonical exercise name (via normalizer) |
| `variation` | TEXT | `default`, `flat`, `incline`, `decline` |
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

- Non-bench strength entries use `default`
- Bench press entries use `flat` for the base variation
- Bench press incline and decline are tracked as separate rows
- Legacy summary output may still encounter old combined rows, but new logs should not create them

## Parsing behaviour

### Strength parsing

Handles these format variants (in priority order):

1. **Continuation lines**: bare `N x M [@ weight]` — inherits exercise from previous line
2. **Weight-first**: `Exercise - 20 kg 3 sets x 15 reps`
3. **Multi-set comma split**: `Exercise - 2 x 15 with 5 + 5 kg, 1 set of 15 rep with 7.5 kg`
4. **Standard**: `exercise N x M [@ weight]`
5. **Multi-set-of**: `N set(s) of M rep(s) [@ weight]`

Typo recovery: `woth` → `with`, `dumbell` → `dumbbell`, `biceo` → `bicep`, `calf rause` → `calf raise`, etc.

### Exercise name normalisation

`tracker/normalizer.py` normalizes exercise names to canonical forms:

- Bench press with "press" in text → `Barbell Bench Press` (if "barbell" in text) or `Dumbbell Bench Press` (default)
- Lat pull-down → detects `short grip` / `wide grip` variants
- Rear delt → `Rear Delt Fly`
- Canonical dictionary for known exercises (Shoulder Press, Bicep Curl, Leg Press, etc.)
- Title-case fallback for unknown exercises

### Equipment inference

Keyword-based on exercise name + raw text (combined):

`dumbbells` | `barbell` | `cable` | `machine` | `bodyweight` | `kettlebell` | `smith machine` | `band` | `other`

Machine exercises are detected via a hardcoded set of exercise names (Chest Press, Pec Fly, Lat Pull Down, Seated Row, Leg Press, etc.).

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
- PR scoring: highest weight → highest reps → highest sets → latest date

Summary responses are tiered — Mercury picks the right one based on natural language:

| Level | Example trigger | Script |
|-------|----------------|--------|
| Short | "show recent workouts" | `python summary.py` |
| Full PRs | "show my PRs", "best lifts" | `python summary.py --prs` |

### Body part classification

Chest 💪 | Back 🧱 | Shoulders 🧢 | Arms 🏹 | Legs 🦵 | Core ⚡ | Other 📦

Keywords for each group are in `tracker/reports.py:_body_part()`. Special rules: `Rear Delt Fly` → Shoulders (not Back), `Leg Curl` → Legs (not Arms).

## Hermes skills architecture

Skills live in `skills/<name>/SKILL.md` and teach Mercury the procedures for this tracker. The agent loads a skill's full content only when the task matches — descriptions are loaded at startup, full bodies on demand.

Three skills, all created in `skills/`:
- `log-workout` — parse and insert lines, handle incline/decline split, confirm count
- `workout-summary` — pick the right summary tier and format for Telegram
- `backup-db` — dump SQLite, upload to Azure Blob, prune to last 3 copies

The data layer (`tracker/core.py`, `tracker/parser.py`) is intentionally separate from the agent layer. Skills call the Python scripts; they do not replicate logic.

### Cron jobs

Weekly cron runs:
1. **PR summary**: runs `python summary.py --prs` and updates Hermes memory with latest PRs
2. **DB backup**: runs `backup-db` skill to upload to Azure Blob and prune to last 3 copies

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
- After changing parser/normalizer, run `uv run pytest` — 96+ tests should pass
- SQLite auto-ALTER in `ensure_db()` handles schema migration on startup; no manual DDL needed
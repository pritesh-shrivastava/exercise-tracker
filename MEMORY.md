# Hermes Memory — Exercise Tracker

Project-specific notes, conventions, and decisions for the exercise tracker.
This file lives in the repo root so it follows the project wherever it's cloned.

---

## Project Overview

Personal workout tracker. Hermes Agent is the Telegram interface. Python + SQLite. No external runtime dependencies.

- **Log a workout:** `uv run python log_workout.py "exercise 3x5 @ 100kg"`
- **Recent activity:** `uv run python summary.py`
- **PR summary (compact):** `uv run python summary.py --prs`
- **Tests:** `uv run pytest`
- **Backfill structured columns:** `uv run python scripts/backfill_structured.py`

## Database

- **Path:** `data/workouts.sqlite` (in repo root)
- **14 columns:** id, logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source, sets, reps, weight_kg, equipment, per_hand
- **Columns to hide when displaying data:** `details`, `raw_text`, `id`
- **Auto-migration:** `ensure_db()` in `tracker/core.py` adds missing columns + indexes on startup

### Weight Convention

- **Total weight stored** (NOT per-hand), with `per_hand` boolean flag
- Example: Dumbbell Shoulder Press "15 kg each hand" → `weight_kg=30.0, per_hand=1`
- Display format: `3x15 @ 30 (15 ea.)`
- Goblet squats: single dumbbell held with both hands, `per_hand=0`

### Equipment Tags

| Value | Description |
|-------|-------------|
| `machine` | Cable machines, plate-loaded, pin-loaded |
| `dumbbells` | Dumbbell exercises (with per_hand flag) |
| `cable` | Cable pulley exercises |
| `bodyweight` | No external weight |
| `barbell` | Barbell exercises |
| `kettlebell` | Kettlebell exercises |
| `smith machine` | Smith machine exercises |
| `band` | Resistance band exercises |
| `other` | Catch-all |

**Equipment classification logic:** keyword-based on the *combined* exercise name + raw text. Machine exercises detected via a hardcoded set of known machine exercise names.

### Parser Features

- Continuation line handling (bare `N x M` after a strength line inherits the exercise name)
- Weight-first format support (e.g., "30 kg squats 3x5")
- Multi-set comma splitting (e.g., "bench 3x5 with 70kg, 2x3 with 80kg")
- `set of` notation splitting (e.g., "3 sets of 10 with 50kg")
- `"woth"` → `"with"` typo auto-correction
- Compound bench-angle phrase detection: splits "bench incline and decline" into two rows

### Normalizer

- Bench press detection: `bench` + `press` in combined text → `[Barbell|Dumbbell] Bench Press`
- Canonical names: Face Pull, Cable Rope Upright Row, Bodyweight Abs Crunch, etc.
- `"dumbell"` → `"dumbbell"` auto-replacement in cleaned text
- Lat pull-down variants: short grip, wide grip
- Title-case fallback for unknown exercises

### PR Reports

- PR scoring uses `weight_kg`, `reps`, `sets` columns directly (not raw text parsing)
- Display: `3x15 @ 30 (15 ea.)` for dumbbells
- Compact PR format: body-part sections only (💪 Chest, 🧱 Back, etc.) — no header/summary lines
- Date freshness: 🟢 if ≤ 14 days ago, 🔴 if older

## User Preferences

- **Weight unit:** kg (never lbs)
- **Timezone:** IST (Asia/Kolkata) — all timestamps in IST
- **Training style:** free weights + machines, gym-based

## Training Split

Priority rotation — follow the next available slot:

1. Pull — back + biceps
2. Push — chest + triceps
3. Legs
4. Shoulders + abs
5. Functional / yoga / tai chi
6. Bonus — swimming / badminton / walk

If only 3 days: Pull, Push, Legs. Add Shoulders on day 4, Functional on day 5.

## Workflow Tips

- After changing parser/normalizer, run `uv run pytest` — tests should pass
- To backfill structured columns after a schema change: `uv run python scripts/backfill_structured.py`
- SQLite auto-ALTER in `ensure_db()` — `core.py` handles migration on startup
- Weekly backup + PR summary runs via Hermes cron

## Key Decisions (Historical)

- **Weight as total + per_hand flag** (not per-hand storage) — keeps PR comparisons and volume calculations consistent across equipment types
- **Equipment by combined text** (exercise name + raw text) — handles free-text input reliably
- **Backfill rule:** existing rows without `+` notation were stored per-hand → doubled to total; with `+` notation already total → kept; goblet squat is single-dumbbell exception
- **Compact PR summaries** skip header lines — start directly with body-part emoji sections
- **SQLite auto-migration** — no manual migration scripts for the deployed DB; `ensure_db()` adds columns incrementally

## Agent Name

The user refers to the agent as Mercury. Config files use "Mercury" for personality names.
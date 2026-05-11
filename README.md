# Exercise Tracker

A small, portable workout tracker that you can move to another VPS later.

Paste what you did in natural language, and the tracker stores it in a local SQLite database. **Mercury** (Hermes Agent) is the interface — chat with it on Telegram to log and query. The data stays separate and portable.

## Why this structure

- **Portable**: data lives in `data/workouts.sqlite`
- **Simple**: one script can log workouts from pasted text
- **Portable**: copy the folder to another VPS and keep going
- **Future-proof**: easy to add Notion, CSV export, or dashboards later

## Folder layout

```
data/                        — SQLite database
log_workout.py               — add workouts to the database
summary.py                   — quick stats (default) or PRs (--prs)
tracker/
  __init__.py                — empty package marker
  parser.py                  — classify lines: strength, cardio, note
  normalizer.py              — canonical exercise names + typo recovery
  core.py                    — DB helpers (insert, fetch, format, auto-migrate)
  reports.py                 — PR report by body part with scoring
tests/
  test_parser.py             — parser unit tests
  test_normalizer.py         — normalizer unit tests
  test_reports.py            — PR report + equipment classification tests
scripts/
  backfill_structured.py     — one-off backfill of structured columns (sets, reps, weight_kg, etc.)
  normalize_existing.py      — one-off normalisation pass for old rows
  restore_db.sh              — restore database from Azure Blob backup
skills/                      — Hermes agent skill definitions (loaded on demand)
  log-workout/SKILL.md
  workout-summary/SKILL.md
  backup-db/SKILL.md
pyproject.toml               — uv project config with ruff, mypy, pytest
design.md                    — data model, variation rules, logging behaviour
memory_template.md           — seed file for Hermes memory on setup/migration
```

## Quick start

```bash
cd /home/azureuser/exercise-tracker
uv run python log_workout.py "squats 3x5 @ 100kg"
uv run python log_workout.py "20 min zone 2 cardio"
uv run python summary.py
uv run python summary.py --prs   # personal records by body part
```

## Weekly training template

Your plan is aspirational, so the tracker should work even when you only train 3–4 days a week.

### Priority rotation

Follow the next available slot instead of forcing a rigid calendar:

1. Pull — back + biceps
2. Push — chest + triceps
3. Legs
4. Shoulders + abs
5. Functional / yoga / taichi
6. Swimming / badminton / walk

### If you train 3 days in a week

- Day 1: Back + Biceps
- Day 2: Chest + Triceps
- Day 3: Legs

### If you train 4 days in a week

- Day 1: Back + Biceps
- Day 2: Chest + Triceps
- Day 3: Legs
- Day 4: Shoulders + Abs

### If you train 5 days in a week

- Day 1: Back + Biceps
- Day 2: Chest + Triceps
- Day 3: Legs
- Day 4: Shoulders + Abs
- Day 5: Functional / yoga / taichi

### Bonus day

- Swimming / badminton / walk

## Telegram interface

**Mercury** (Hermes Agent) is the Telegram interface. There is no separate bot to run — just chat with Mercury directly:

- "squats 3x5 @ 100kg" → logged
- "20 min zone 2 cardio" → logged
- "show my PRs" → runs `python summary.py --prs`, sends results back
- "show recent workouts" → runs `python summary.py`
- Voice memos → auto-transcribed by Mercury, then logged

Run `/sethome` once in your Telegram chat so Mercury knows where to deliver scheduled outputs like the weekly PR report.

## Paste format examples

### Strength

- `bench 5x5 @ 70kg`
- `squats 3x5 @ 100kg`
- `deadlift 1x5 @ 140kg`
- `30 kg squats 3x5` (weight-first format)

#### Bench variation examples

- `bench incline 3x12 @ 15kg`
- `bench decline 3x12 @ 15kg`
- `bench incline and decline 3x15 @ 15kg` → stored as two rows, `incline` and `decline`

#### Multi-set in one line

- `Dumbbell Shoulder Press - 2 x 15 with 5 + 5 kg, 1 set of 15 rep with 7.5 kg` → splits into separate records

#### Continuation lines

- `bench 3x5 @ 70kg`
- `2x3 @ 80kg` (inherits "bench" from previous line)

### Cardio

- `20 min zone 2 cardio`
- `5 km run 28 min`
- `cycling 45 min`

### Mixed log

- `squats 3x5 @ 100kg`
- `bench 5x5 @ 70kg`
- `20 min incline walk`

## Hermes Agent skills

The `skills/` folder teaches Mercury the procedures for this tracker. Each skill is a folder named `<name>/` with a `SKILL.md` inside:

```
skills/
  log-workout/      — how to log workout lines from natural language
  workout-summary/  — tiered summary: recent entries, weekly volume, PRs
  backup-db/        — dump SQLite to Azure Blob and prune old copies
```

Skills are auto-discovered by Hermes on startup. The agent picks the right skill based on what you ask, then runs the procedure in `SKILL.md`. You can also trigger any skill manually.

Hermes memory stores facts that persist across sessions:
- Your current PRs (bench, squat, deadlift)
- Training preferences (Pull→Push→Legs rotation, kg, IST timezone)

## Migration to another VPS

You do **not** need the same Hermes Agent instance to keep this tracker running.
The important part is the data and the env vars, not the agent.

### What to move

- The whole repo folder
- `data/workouts.sqlite` or your latest backup copy
- Your Hermes config (if moving the agent too)
- Any `WORKOUT_DB_PATH` setting if you use a custom DB path

### Migration steps

1. **Clone or copy the repo** on the new VPS

```bash
git clone https://github.com/pritesh-shrivastava/exercise-tracker.git
cd exercise-tracker
```

2. **Restore the database**

If you have the old DB file, copy it into:

```bash
mkdir -p data
cp /path/to/old/workouts.sqlite data/workouts.sqlite
```

If you only have a backup file, restore that instead.

3. **Set up Python**

```bash
pip install uv   # or: brew install uv
uv sync
```

4. **Set the environment variable**

```bash
export WORKOUT_DB_PATH="data/workouts.sqlite"
```

Hermes Agent handles Telegram — point it at this repo from your Hermes config.

5. **Verify the data**

```bash
uv run python summary.py
```

6. **Seed Hermes memory**

```bash
cp memory_template.md ~/.hermes/memories/MEMORY.md
```

### Migration checklist

- [ ] repo cloned
- [ ] database copied
- [ ] `uv sync` runs clean
- [ ] `uv run python summary.py` shows data
- [ ] Hermes pointed at the repo folder
- [ ] `memory_template.md` copied to `~/.hermes/memories/MEMORY.md`

## Maintenance

```bash
uv run pytest            # 96+ tests
uv run ruff check .      # lint
uv run mypy tracker/ summary.py log_workout.py  # type check
```

After schema changes: `uv run python scripts/backfill_structured.py`
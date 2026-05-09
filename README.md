# Exercise Tracker

A small, portable workout tracker that you can move to another VPS later.

## Goal

Paste what you did in natural language, and the tracker stores it in a local SQLite database.
Hermes Agent is the interface — chat with it on Telegram to log and query. The data stays separate and portable.

## Why this structure

- **Portable**: data lives in `data/workouts.sqlite`
- **Simple**: one script can log workouts from pasted text
- **Moveable**: copy the folder to another VPS and keep going
- **Future-proof**: easy to add Notion, CSV export, or dashboards later

## Folder layout

- `data/` — SQLite database
- `log_workout.py` — add workouts to the database
- `summary.py` — show quick stats; `--prs` flag for personal records by body part
- `tracker/` — core library (parser, normalizer, DB helpers, PR report)
- `tests/` — pytest suite (test_parser.py, test_reports.py)
- `scripts/normalize_existing.py` — one-off cleanup for old rows
- `scripts/restore_db.sh` — restore database from Azure Blob backup
- `skills/` — Hermes agent skill definitions
- `pyproject.toml` — uv project config with ruff, mypy, pytest
- `design.md` — the current data and variation rules
- `memory_template.md` — seed file for Hermes memory on setup/migration

## Quick start

```bash
cd /home/azureuser/exercise-tracker
uv run python log_workout.py "squats 3x5 @ 100kg"
uv run python log_workout.py "20 min zone 2 cardio"
uv run python summary.py
uv run python summary.py --prs   # personal records
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

Hermes Agent is the Telegram interface. There is no separate bot to run — just chat with Hermes directly:

- "squats 3x5 @ 100kg" → logged
- "20 min zone 2 cardio" → logged
- "show my PRs" → runs `python summary.py --prs`, sends results back
- "show recent workouts" → runs `python summary.py`
- Voice memos → auto-transcribed by Hermes, then logged

Run `/sethome` once in your Telegram chat so Hermes knows where to deliver scheduled outputs like the weekly PR report.

## Paste format examples

Strength:
- `bench 5x5 @ 70kg`
- `squats 3x5 @ 100kg`
- `deadlift 1x5 @ 140kg`

Bench variation examples:
- `bench incline 3x12 @ 15kg`
- `bench decline 3x12 @ 15kg`
- `bench incline and decline 3x15 @ 15kg` → stored as two rows, `incline` and `decline`

Cardio:
- `20 min zone 2 cardio`
- `5 km run in 28:30`
- `cycling 45 min`

Mixed log:
- `squats 3x5 @ 100kg`
- `bench 5x5 @ 70kg`
- `20 min incline walk`

## Hermes Agent skills

The `skills/` folder teaches Hermes the procedures for this tracker. Each skill is a folder containing a `SKILL.md`:

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

Copy these pieces to the new VPS:

- the whole repo folder
- `data/workouts.sqlite` or your latest backup copy
- your Telegram bot token
- any `WORKOUT_DB_PATH` setting if you use a custom DB path

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

Hermes Agent handles Telegram — point it at this repo and set your `TELEGRAM_BOT_TOKEN` in Hermes config, not here.

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

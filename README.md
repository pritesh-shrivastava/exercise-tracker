# Exercise Tracker

A small, portable workout tracker that you can move to another VPS later.

## Goal

Paste what you did in natural language, and the tracker stores it in a local SQLite database.
Hermes can be the interface, but the data stays separate and portable.

## Why this structure

- **Portable**: data lives in `data/workouts.sqlite`
- **Simple**: one script can log workouts from pasted text
- **Moveable**: copy the folder to another VPS and keep going
- **Future-proof**: easy to add Telegram, Notion, CSV export, or dashboards later

## Folder layout

- `data/` — SQLite database and future data files
- `imports/` — optional raw imports
- `exports/` — CSV / JSON exports
- `logs/` — app logs
- `log_workout.py` — add workouts to the database
- `summary.py` — show quick stats
- `parse_workout.py` — turn pasted text into structured fields
- `exercise_normalizer.py` — canonical exercise names and aliases
- `normalize_existing.py` — one-off cleanup for old rows
- `telegram_bot.py` — listen to Telegram and log messages automatically
- `tracker_core.py` — shared DB/stats helpers
- `config.example.yaml` — sample settings

## Quick start

```bash
cd /home/azureuser/exercise-tracker
python log_workout.py "squats 3x5 @ 100kg"
python log_workout.py "20 min zone 2 cardio"
python summary.py
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

## Telegram logging

If you want the tracker to log workouts directly from Telegram:

1. Create a bot with BotFather
2. Set `TELEGRAM_BOT_TOKEN`
3. Optional: set `TELEGRAM_ALLOWED_CHAT_ID` to restrict it to your chat
4. Run:

```bash
python telegram_bot.py
```

Then send workout messages like:
- `squats 3x5 @ 100kg`
- `20 min zone 2 cardio`
- `5 km run in 28:30`

It also supports:
- `/summary`
- `/help`

## Paste format examples

Strength:
- `bench 5x5 @ 70kg`
- `squats 3x5 @ 100kg`
- `deadlift 1x5 @ 140kg`

Cardio:
- `20 min zone 2 cardio`
- `5 km run in 28:30`
- `cycling 45 min`

Mixed log:
- `squats 3x5 @ 100kg`
- `bench 5x5 @ 70kg`
- `20 min incline walk`

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
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

This project uses only the standard library, so there are no extra packages to install.

4. **Set the environment variables**

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_ALLOWED_CHAT_ID="optional-chat-id"
export WORKOUT_DB_PATH="data/workouts.sqlite"
```

5. **Verify the data**

```bash
python summary.py
```

6. **Start the Telegram bot**

```bash
python telegram_bot.py
```

### If you want it to run as a service

On the new VPS, you can run it with `systemd`, `supervisord`, or a simple `tmux` session.
A minimal `systemd` service would just need:

- the repo path
- the venv path
- `TELEGRAM_BOT_TOKEN`
- `WORKOUT_DB_PATH`

### Migration checklist

- [ ] repo copied or cloned
- [ ] database copied
- [ ] Telegram bot token set
- [ ] summary works
- [ ] bot starts and receives messages

If you later connect a different Hermes Agent, it only needs the path to this folder and the env vars above.

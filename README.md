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

## Migration later

To move this tracker to another VPS:

1. Copy the whole folder
2. Copy `data/workouts.sqlite`
3. Keep the same script files
4. Run the scripts on the new machine

If you later connect Hermes to it, Hermes only needs the path to this folder.

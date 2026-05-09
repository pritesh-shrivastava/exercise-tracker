# Hermes Memory — Exercise Tracker

Copy this file to `~/.hermes/memories/MEMORY.md` when setting up Hermes on a new machine or after a VPS migration.

---

## User Preferences

- Weight unit: kg (never lbs)
- Timezone: IST (Asia/Kolkata) — all workout timestamps are stored in IST
- Training style: free weights + machines, gym-based

## Training Split

Priority rotation — follow the next available slot rather than a fixed calendar day:

1. Pull — back + biceps
2. Push — chest + triceps
3. Legs
4. Shoulders + abs
5. Functional / yoga / tai chi
6. Bonus — swimming / badminton / walk

If only 3 days in a week: Pull, Push, Legs. Add Shoulders on day 4, Functional on day 5.

## Workout Logging

- Database: `data/workouts.sqlite` in the exercise-tracker repo
- Log with: `python log_workout.py "<text>"`
- Summary: `python summary.py` (recent) or `python pr_summary.py` (PRs by body part)
- Bench press variations are tracked separately: flat, incline, decline

## Personal Records

> This section is overwritten automatically after each weekly `pr_summary.py` run.
> Do not edit manually — it will be replaced on the next weekly cron.

(Not yet populated — will be filled after first weekly summary.)

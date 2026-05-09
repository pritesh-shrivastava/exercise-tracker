---
name: log-workout
description: Use when the user pastes workout lines, says what they trained, mentions exercise sets or reps, or wants to log a workout session. Handles strength (sets x reps @ weight), cardio (distance, duration), and mixed sessions.
version: 1.0.0
---

## When to use

When the user sends:
- Strength lines: "squats 3x5 @ 100kg", "bench 5x5 @ 70kg", "deadlift 1x5 @ 140kg"
- Cardio lines: "20 min zone 2 cardio", "5 km run in 28:30", "cycling 45 min"
- Mixed sessions with multiple lines
- Natural language like "today I did chest and triceps"

## Procedure

1. Pass the user's text to `log_workout.py`:
   ```
   python log_workout.py "<workout text>"
   ```
   For multi-line input:
   ```
   python log_workout.py "squats 3x5 @ 100kg
   bench 5x5 @ 70kg
   20 min zone 2 cardio"
   ```

2. Confirm the count returned: "Logged N workout line(s)."

3. If this looks like the last session of the week, offer to run `python summary.py` (recent) or `python summary.py --prs` (personal records).

## Pitfalls

- **Incline + decline bench in one line** (`bench incline and decline 3x15 @ 15kg`) — the parser splits this into two rows, one `incline` and one `decline`. Confirm both are logged by checking N=2.
- **IST timezone is assumed** — `logged_at` and `workout_date` are always stored in IST. Do not convert timestamps.
- **Raw text is preserved exactly** — exercise name normalization happens in `exercise_normalizer.py`, not by rewriting the user's input.
- **Lines that don't match strength or cardio patterns** are stored as `note` type — expected behavior, not an error.

## Verification

Output says `Logged N workout line(s) into data/workouts.sqlite` where N > 0.
Run `python summary.py` to confirm the entry appears in recent entries.

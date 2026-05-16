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

A workout session usually arrives across multiple chat messages. **Buffer lines in conversation memory and only write to the DB when the user signals the session is done.**

1. **Accumulate, don't log yet.** When the user sends one or more workout lines, append them to a running buffer for this session and reply with a short confirmation that includes the running list (e.g. "Got it. So far: squats 3x5 @ 100kg, bench 5x5 @ 70kg. Send more or say 'log it' when done."). Do **not** call `log_workout.py` yet.

2. **Flush on an explicit done signal.** When the user says any of: "log it", "log this", "save", "save it", "that's it", "done", "finished", "commit", "flush", "end session" — concatenate every buffered line with newlines and make a single call:
   ```
   uv run python log_workout.py "squats 3x5 @ 100kg
   bench 5x5 @ 70kg
   20 min zone 2 cardio"
   ```
   Then clear the buffer.

3. **Flush implicitly when the user moves on.** If the user changes topic (asks for a summary, PRs, backup, or starts an unrelated conversation) and the buffer is non-empty, flush it first, mention you did, then handle the new request.

4. **One-shot override.** If the user explicitly says "log this immediately" / "log now" with a single line, skip the buffer and call `log_workout.py` directly.

5. After flushing, confirm the count returned: "Logged N workout line(s)."

6. If this looks like the last session of the week, offer to run `uv run python summary.py` (recent) or `uv run python summary.py --prs` (personal records).

## Pitfalls

- **Incline + decline bench in one line** (`bench incline and decline 3x15 @ 15kg`) — the parser splits this into two rows, one `incline` and one `decline`. Confirm both are logged by checking N=2.
- **IST timezone is assumed** — `logged_at` and `workout_date` are always stored in IST. Do not convert timestamps.
- **Raw text is preserved exactly** — exercise name normalization happens in `exercise_normalizer.py`, not by rewriting the user's input.
- **Lines that don't match strength or cardio patterns** are stored as `note` type — expected behavior, not an error.
- **Don't log line-by-line.** Each call to `log_workout.py` is a separate DB write with its own `logged_at`. Always batch the whole session into one call so all rows share a timestamp.
- **Don't lose the buffer on correction.** If the user amends a previous line ("actually bench was 75kg not 70"), update the buffered line in place rather than appending a duplicate.

## Verification

Output says `Logged N workout line(s) into data/workouts.sqlite` where N > 0.
Run `python summary.py` to confirm the entry appears in recent entries.

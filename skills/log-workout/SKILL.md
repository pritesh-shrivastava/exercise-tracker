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

## Post-flush verification (MANDATORY)

After every log, run `python summary.py --prs` and verify:

1. **Weights are present** for every exercise that had them in the buffer. A missing weight means the parser dropped it — fix immediately with SQL.
2. **Exercise names are canonical.** No new variants (e.g. "Calf Raises" alongside existing "Calf Raise", "Hamstring Curls" vs "Hamstring Curl"). Fix with SQL: `UPDATE workouts SET exercise='<canonical>' WHERE id=<id>`.
3. **No bogus exercise rows.** The parser sometimes creates rows where the exercise name is a raw fragment like "1 x 15 - 43 kg" instead of merging it as a continuation of the previous exercise. Fix by updating `exercise`, `sets`, `reps`, `weight_kg`, and `variation` for that row via SQL.
4. If the `--prs` output looks clean, then confirm with the user.

## Parser bugs to watch for (post-flush SQL fixes)

The parser has known gaps. After every log, query the new rows (`WHERE id > <last_known_id>`) and fix these patterns:

- **Continuation lines treated as new exercises.** When the user sends a weight-only follow-up line (e.g. "1 x 15 - 43 kg" after "Leg extension - 2 x 15 - 36 kg"), the parser creates a row with `exercise='1 x 15 - 43 kg'` instead of merging it into the previous exercise. Fix: `UPDATE workouts SET exercise='<canonical>', sets=1, reps=15, weight_kg=43, variation='default' WHERE id=<bogus_id>`.
- **Comma-separated mixed weights dropped.** Lines like "Goblet Squats - 2 x 15 - 10 kg, 1 x 15 - 12.5 kg" only parse the first part; the second set is lost entirely. Currently fixed manually — split into two workouts rows with SQL.
- **Weight dropped when present in input.** If the --prs output shows no weight for an exercise that had one in the buffer, the parser ate it. Common with multi-set lines or lines with trailing qualifiers like "(machine)". Fix by setting `weight_kg` directly.
## Pitfalls

- **per_hand: user means total weight, not per-hand.** When the user says "7.5 kg" for dumbbell exercises, it's **total weight** (per_hand=0), never per-hand. "7.5 + 7.5 kg" means 15kg total with per_hand=1. "7.5 kg" without modifiers = total weight, per_hand=0. The parser's per_hand logic has caused corrections from the user — always leave per_hand=0 unless the input explicitly says "each" or "per hand".
- **The parser has known format gaps.** Test every new session's input with the parser BEFORE writing to the DB. See procedure below. The user consistently uses dash-separated weight (`3x12 - 30 kg`), which the regexes now support. But novel formats will still surface — always dry-run first.
- **Continuation lines** (bare `1 x 15 - 43 kg` without exercise name) inherit from the previous line's exercise. The parser handles this via `CONTINUATION_RE` + `classify_lines()` — always use `classify_lines()` not `classify_line()` for multi-line input.
- **Comma-separated mixed weights** (`2 x 15 - 10 kg, 1 x 15 - 12.5 kg`) split into separate rows if `MULTI_LINE_PATTERN` detects them. This requires the line to have `N x` or `N set` after the comma.
- **Verify PR output after every log.** Run `python summary.py --prs` and check that weights parsed correctly. If an exercise name has a weight suffix (e.g. "Standing Dumbbell Tricep Extension - 10 Kg"), the parser created a bogus variation — fix with SQL: `UPDATE workouts SET exercise='<canonical>', weight_kg=<value>, per_hand=0 WHERE id=<id>`.
- **Fix old entries when correcting current ones.** If the user corrects today's weight, they may also want previous entries for that exercise updated — ask.
- **Incline + decline bench in one line** (`bench incline and decline 3x15 @ 15kg`) — the parser splits this into two rows, one `incline` and one `decline`. Confirm both are logged by checking N=2.
- **IST timezone is assumed** — `logged_at` and `workout_date` are always stored in IST. Do not convert timestamps.
- **Raw text is preserved exactly** — exercise name normalization happens in `exercise_normalizer.py`, not by rewriting the user's input.
- **Lines that don't match strength or cardio patterns** are stored as `note` type — expected behavior, not an error.
- **Don't log line-by-line.** Each call to `log_workout.py` is a separate DB write with its own `logged_at`. Always batch the whole session into one call so all rows share a timestamp.
- **Don't lose the buffer on correction.** If the user amends a previous line ("actually bench was 75kg not 70"), update the buffered line in place rather than appending a duplicate.

## Verification

1. **Dry-run the parser first** (before DB write):
   ```bash
   python -c "
   from tracker.parser import classify_lines
   from dataclasses import asdict
   text = '''<buffered lines>'''
   for r in classify_lines(text):
       d = asdict(r)
       print(f'{d[\"workout_type\"]:8s} | {d[\"exercise\"]:30s} | {d[\"sets\"]}x{d[\"reps\"]} | {d[\"weight_kg\"]} | {d[\"equipment\"]}')
   "
   ```
   Verify: all exercises named correctly, weights present where expected, no bogus `note` rows for strength lines, mixed-weight lines split correctly.

2. **Then log to DB:** `python log_workout.py "<text>"`. Output says `Logged N workout line(s) into data/workouts.sqlite` where N matches expected.

3. **Verify PR output:** `python summary.py --prs`. Check weights, exercise names, and that newly logged entries appear with today's date and correct values.

4. **Fix any parsing errors immediately** using SQL before the user notices them. Common fixes:
   - Missing weight: `UPDATE workouts SET weight_kg=<value> WHERE id=<id>`
   - Wrong exercise name: `UPDATE workouts SET exercise='<canonical>' WHERE id=<id>`
   - Bogus variation suffix in exercise: `UPDATE workouts SET exercise='<canonical>', weight_kg=<value> WHERE id=<id>`

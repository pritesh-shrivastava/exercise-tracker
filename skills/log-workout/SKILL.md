---
name: log-workout
description: Use when the user pastes workout lines, says what they trained, mentions exercise sets or reps, or wants to log a workout session. Handles strength (sets x reps @ weight), cardio (distance, duration), and mixed sessions.
version: 1.1.0
---

## Working directory & ad-hoc reads (exercise-tracker)

Interactive Telegram sessions in the Health topic have **no working directory in this repo**.
Every command in these skills (`python summary.py`, `python log_workout.py`, the `python -c`
DB queries) is written **relative to the repo root**, so **prefix each command with a `cd`
into the repo** — otherwise a bare `python summary.py` runs from the home dir and fails with
`can't open file '/home/azureuser/summary.py'`:

```bash
cd /home/azureuser/exercise-tracker && python summary.py --prs
```

Common ad-hoc requests (not the logging flow):
- **"Show PRs" / "personal records"** → `cd /home/azureuser/exercise-tracker && python summary.py --prs`
- **"Show recent" / "summary"** → `cd /home/azureuser/exercise-tracker && python summary.py`
- **DB queries** (query-db skill) → run the `python -c` snippet with the same `cd` prefix.

(Cron jobs set `--workdir` so they're already in the repo; this note is for chat replies.)

## When to use

When the user sends:
- Strength lines: "squats 3x5 @ 100kg", "bench 5x5 @ 70kg", "deadlift 1x5 @ 140kg"
- Cardio lines: "20 min zone 2 cardio", "5 km run in 28:30", "cycling 45 min"
- Mixed sessions with multiple lines
- Natural language like "today I did chest and triceps"

## Procedure

A workout session usually arrives across multiple chat messages. **Buffer lines in conversation memory and only write to the DB when the user signals the session is done.**

**Never delegate workout logging to a sub-agent.** Do not call `delegate_task` for
logging, updating, deleting, or verifying workout rows. This skill is stateful:
the active Health conversation owns the workout buffer and all DB writes must be
performed directly in this session.

1. **Accumulate, don't log yet.** When the user sends one or more workout lines, append them to a running buffer for this session and reply with a short confirmation that includes the running list (e.g. "Got it. So far: squats 3x5 @ 100kg, bench 5x5 @ 70kg. Send more or say 'log it' when done."). Do **not** call `log_workout.py` yet.

2. **Flush on an explicit done signal.** When the user says any of: "log it", "log this", "save", "save it", "that's it", "done", "finished", "commit", "flush", "end session" — concatenate every buffered line with newlines and make a single call:
   ```
   python log_workout.py "squats 3x5 @ 100kg
   bench 5x5 @ 70kg
   20 min zone 2 cardio"
   ```
   Then clear the buffer.

3. **Flush implicitly when the user moves on.** If the user changes topic (asks for a summary, PRs, backup, or starts an unrelated conversation) and the buffer is non-empty, flush it first, mention you did, then handle the new request.

4. **One-shot override.** If the user explicitly says "log this immediately" / "log now" with a single line, skip the buffer and call `log_workout.py` directly.

5. **Clarify ambiguous weight BEFORE flushing, mid-buffer.** If the user types ambiguous lines like:
   - "empty bar" or "0 kg" for barbell exercises → the user's policy is barbell weight is NOT tracked. Don't ask. Log as weight_kg=NULL. If parser doesn't handle it, fix via Codex after flush.
   - "7.5 kg" for a dumbbell exercise → it's total weight (per_hand=0). Don't ask unless it's "7.5 + 7.5" which is per_hand=1.
   - "5 + 5 kg" → per_hand=True (10 total).
   Do NOT ask the user what these mean — the policy is established. Only ask if format is genuinely ambiguous.

6. After flushing, confirm the count returned: "Logged N workout line(s)."

7. If this looks like the last session of the week, offer to run `python summary.py` (recent) or `python summary.py --prs` (personal records).

## Post-flush verification (MANDATORY)

After every log, run `python summary.py --prs` and verify:

1. **Weights are present** for every exercise that had them in the buffer. A missing weight means the parser dropped it — fix immediately with SQL.
2. **Exercise names are canonical — no plural drift.** No new variants (e.g. "Calf Raises" alongside existing "Calf Raise", "Barbell Curls" vs "Barbell Curl", "Hamstring Curls" vs "Hamstring Curl"). If the same exercise appears twice in PR output under slightly different names, merge with SQL: `UPDATE workouts SET exercise='<canonical singular>' WHERE exercise='<variant>'`.
3. **No bogus exercise rows.** The parser sometimes creates rows where the exercise name is a raw fragment like "1 x 15 - 43 kg" instead of merging it as a continuation of the previous exercise. Fix by updating `exercise`, `sets`, `reps`, `weight_kg`, and `variation` for that row via SQL.
4. **Body part classification is correct in PR output.** Check that every new exercise shows under the right emoji section (🩻 Chest, 🧱 Back, 🧢 Shoulders, 💪 Biceps, 🔻 Triceps, 🦵 Legs, ⚡ Core, 📦 Other). If an exercise like "Barbell Incline Press" shows under 📦 Other, the keyword is missing from `tracker/reports.py:body_part()`. Fix by asking Codex to add the missing keyword. Common gaps: "incline press" for Chest, "dip" for Triceps.
5. If the `--prs` output looks clean, then confirm with the user.
6. **When showing PRs to the user, the emoji-heavy raw output may not render in Telegram.** If the user says they can't see it ("Cant see"), reformat without emojis using plain section headers and `code` blocks. Don't repeat the raw emoji output — go straight to a clean format.

## Post-flush fixes (do these BEFORE showing user the output)

This is the priority-ordered checklist of what to check after every log. Work through these before running `summary.py --prs` to show the user:

### 1. Barbell weight → NULL (Pritesh policy)
The user's policy: barbell weight (the bar itself) is not tracked. Any barbell row with weight_kg=0.0, weight_kg=20.0, or any value for "empty bar" should be set to NULL immediately:
```sql
UPDATE workouts SET weight_kg=NULL WHERE id IN (<ids>)
```
If the parser doesn't handle this (e.g. produces weight_kg=0 for "0 kg"), ask Codex to fix `tracker/parser.py:parse_weight_kg()` to return None for barbell + 0 kg / "empty bar".

### 2. Name normalization / DB merge
Check PR output for duplicate exercise entries that are the same exercise under slightly different names:
- "Vertical Chest Press" vs "Vertical Chest Press Machine" → merge to the canonical (the one with more history)
- "Standing Dumbbell Tricep Extension" vs "Dumbbell Overhead Tricep Extension" → merge to whichever name the user prefers
- Fix: (a) add canonical mapping in `tracker/normalizer.py`, (b) run `UPDATE workouts SET exercise='<canonical>' WHERE exercise='<variant>'`
- Delegate to Codex with a clear goal. Tell Codex the canonical name explicitly.

### 3. per_hand override
The parser may set per_hand=True for dumbbell exercises even when the weight is total (e.g. overhead tricep extension at 7.5 kg — total, not per-hand).
- per_hand=True is correct for: "5 + 5 kg" format
- per_hand=True is WRONG for: single number like "7.5 kg" or "10 kg" on dumbbell tricep extension, pec fly, etc.
- Fix: `UPDATE workouts SET per_hand=0 WHERE id=<id>`
- Check PR output: "(##ea.)" suffix means per_hand was set.

### 4. Body part classification
If a new exercise shows under the wrong emoji section:
- Add the missing keyword to the right list in `tracker/reports.py:body_part()`
- Do NOT add exercise-specific overrides — add a general keyword
- Known gaps already fixed: "incline press" → Chest, "dip" → Triceps
- Delegate to Codex with the exercise name and target body part

### 5. Merge spelling forks
"Dumbell" (one b) vs "Dumbbell" — the normalizer handles "dumbell" → "dumbbell" in `_clean()`, but the parser may output "Dumbell" (capitalized) from the raw exercise name before normalization. The title-case fallback path preserves "Dumbell". Fix: `UPDATE workouts SET exercise='Dumbbell ...' WHERE exercise='Dumbell ...'`

## Parser bugs to watch for (post-flush SQL fixes)

The parser has known gaps. After every log, query the new rows (`WHERE id > <last_known_id>`) and fix these patterns:

- **Continuation lines treated as new exercises.** When the user sends a weight-only follow-up line (e.g. "1 x 15 - 43 kg" after "Leg extension - 2 x 15 - 36 kg"), the parser creates a row with `exercise='1 x 15 - 43 kg'` instead of merging it into the previous exercise. Fix: `UPDATE workouts SET exercise='<canonical>', sets=1, reps=15, weight_kg=43, variation='default' WHERE id=<bogus_id>`.
- **Comma-separated mixed weights dropped.** Lines like "Goblet Squats - 2 x 15 - 10 kg, 1 x 15 - 12.5 kg" only parse the first part; the second set is lost entirely. Currently fixed manually — split into two workouts rows with SQL.
- **Weight dropped when present in input.** If the --prs output shows no weight for an exercise that had one in the buffer, the parser ate it. Common causes: multi-set lines, lines with trailing parenthetical qualifiers like "45 Degree T Bar Row (Machine) - 3 x 15 - 15 kg" where the `(Machine)` suffix interferes with the weight regex. Fix by setting `weight_kg` directly via SQL.
- **Plural name drift creates fork in DB.** Input like "Barbell Curl" vs "Barbell Curls" get stored as separate exercises, appearing twice in PR output. The normalizer only handles canonical form detection (e.g. "dumbell" → "dumbbell"), not pluralization. Fix: `UPDATE workouts SET exercise='<singular canonical>' WHERE exercise='<plural variant>'`. Common offenders: curl/curls, squat/squats, lunge/lunges, raise/raises, crunch/crunches.
- **"Dumbell incline chest press" truncated to "Dumbell".** When the parser sees "Dumbell incline chest press - 3 x 15 - 7.5 + 7.5 kg", it only captures "Dumbell" as the exercise name and drops "incline chest press" entirely. The per-hand detection on `7.5 + 7.5` is correct but the exercise name regex is too greedy in the wrong direction. Fix: `UPDATE workouts SET exercise='Dumbbell Incline Chest Press', variation='incline' WHERE id=<id>`.
- **Barbell "0 kg" / "empty bar" → weight_kg=None.** The parser may produce weight_kg=0.0 for "0 kg" input. If the equipment is barbell, this should be None. Ask Codex to fix `tracker/parser.py:parse_weight_kg()` to check `equipment == "barbell" and total == 0`.
- **Barbell "incline press" → exercise name drops "incline".** The `_clean_exercise_name()` function strips angle words ("incline", "decline", "flat") after the first word. For barbell exercises, the first word is "barbell" and "incline" gets stripped. Fix: ask Codex to exempt barbell from the angle-word strip in `_clean_exercise_name()`.

## Pitfalls

- **New exercise addition**: When you encounter a previously unseen exercise (e.g., "Hanstring curl"), add a canonical entry in `tracker/normalizer.py` under the appropriate body‑part mapping. After logging, verify the PR output includes the new exercise under the correct emoji section. If it appears under 📦 or with a wrong name, update the normalizer mapping accordingly.
- **Virtual‑env warning**: The `uv run` commands may emit a warning about `VIRTUAL_ENV` mismatching the project environment. To silence this, invoke the command with the `--active` flag (`uv run --active python …`) or ensure the active virtual environment matches the project’s `.venv`. This prevents spurious warnings in future logs.


- **per_hand: user means total weight, not per-hand.** When the user says "7.5 kg" for a dumbbell exercise, it's **total weight** (per_hand=0), never per-hand. The parser may still set per_hand=True purely on equipment=dumbbells, especially for overhead tricep extensions and pec flys — always verify and override. "7.5 + 7.5 kg" means 15kg total with per_hand=1. "7.5 kg" without modifiers = total weight, per_hand=0. The parser's per_hand logic has caused corrections from the user — always leave per_hand=0 unless the input explicitly says "each" or "per hand" OR uses explicit "## + ##" format. When in doubt after the dry run, check the --prs output — (##ea.) suffix means per_hand=True was set; override with SQL if incorrect.
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

3. **Run the post-flush fix checklist** (see "Post-flush fixes" section above) — barbell weight, name merge, per_hand, body part, spelling. Do these BEFORE showing the user.

4. **Verify PR output:** `python summary.py --prs`. Check weights, exercise names, and that newly logged entries appear with today's date and correct values.

### Codex delegation pattern for parser/normalizer/reports fixes

When the parser, normalizer, or body_part() classifier needs a fix:

```bash
cd /home/azureuser/exercise-tracker
# Tell Codex the goal, the file to fix, and the tests to run
/home/azureuser/.hermes/node/bin/codex exec "
... clear description of what to fix ...
Run UV_CACHE_DIR=/tmp/uv-cache uv run pytest to verify.
Do NOT touch tests/test_parser.py or tracker/parser.py (unless that's the fix target).
"
```

Use pty=true mode. Always ask Codex to run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` because the default UV cache is read-only in Codex's sandbox.

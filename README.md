# Exercise Tracker

A small, portable workout tracker for a private VPS.

The primary workflow is a small mobile web form/PWA-style interface served from the VPS and opened from your phone over Tailscale. The app writes directly to a local SQLite database and re-reads inserted rows before confirming saves. Telegram/Hermes is kept as a fallback and maintenance interface, not the main daily logger.

## Folder layout

```
data/                        — SQLite database
log_workout.py               — add workouts to the database
summary.py                   — quick stats (default) or PRs (--prs)
web_form.py                  — stdlib mobile web form: Log, Today, PRs
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
  backup_db.py               — Azure Blob backup implementation (SQLite + CSV upload only)
  azure_lifecycle_policy_30d.json — Azure policy deleting workout backup blobs after 30 days
  restore_db.sh              — restore database from Azure Blob backup
skills/                      — Hermes agent skill definitions (loaded on demand)
  log-workout/SKILL.md
  workout-summary/SKILL.md
  backup-db/SKILL.md
  query-db/SKILL.md
pyproject.toml               — uv project config with ruff, mypy, pytest
design.md                    — data model, variation rules, logging behaviour
```

## Quick start

```bash
cd /home/azureuser/exercise-tracker
uv run python log_workout.py "squats 3x5 @ 100kg"
uv run python log_workout.py "20 min zone 2 cardio"
uv run python summary.py
uv run python summary.py --prs   # personal records — compact, one line per exercise
uv run python web_form.py         # mobile web form at http://127.0.0.1:8765/log
```

## Mobile web workflow

Run the form on the VPS and keep it private to your tailnet:

```bash
cd /home/azureuser/exercise-tracker
TAILSCALE_IP=$(tailscale ip -4)
uv run python web_form.py --host "$TAILSCALE_IP" --port 8765
```

Open `http://<tailscale-ip>:8765/log` from your phone while connected to Tailscale.

Do not bind this app to a public VPS interface unless you add real authentication in front of it. The stdlib web form intentionally has no public-internet auth layer; Tailscale is the access control boundary.

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

## Telegram/Hermes fallback

Hermes Agent can still log or query workouts from Telegram when the form is inconvenient. There is no separate bot to run — chat with Hermes directly:

- "squats 3x5 @ 100kg" → logged
- "20 min zone 2 cardio" → logged
- "show my PRs" → runs `uv run python summary.py --prs`, sends compact one-line-per-exercise results back
- "show recent workouts" → runs `uv run python summary.py`
- Voice memos → auto-transcribed by Hermes, then logged

## Workout form

For daily logging, prefer the mobile form over free-text Telegram. The form is intentionally small: open it from your phone, enter one or more structured rows, save, and verify the exact inserted rows shown back from SQLite.

Pages:

- `Log` — date, exercise, variation, sets, reps, weight, equipment, and per-hand fields
- `Today` — today's saved rows, with exact row selection for updates/deletes
- `PRs` — DB-backed PR output using the same report code as `summary.py --prs`

The form should not show "saved" until the SQLite write succeeds and the inserted rows are re-read from `data/workouts.sqlite`.


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

The `skills/` folder teaches Hermes the procedures for this tracker. Each skill is a folder named `<name>/` with a `SKILL.md` inside:

```
skills/
  log-workout/      — how to log workout lines from natural language
  workout-summary/  — tiered summary: recent entries, weekly volume, PRs
  backup-db/        — SQLite + CSV upload to Azure Blob; 30-day retention via Azure lifecycle policy
  query-db/         — show raw table rows, excluding id/raw_text/details
```

Skills are auto-discovered by Hermes on startup. The agent picks the right skill based on what you ask, then runs the procedure in `SKILL.md`. You can also trigger any skill manually.

Hermes runtime memory lives outside this repo at `~/.hermes/memories/MEMORY.md` and is not part of the database backup.


## Maintenance

```bash
uv run pytest
uv run ruff check .      # lint
uv run mypy tracker/ summary.py log_workout.py  # type check
```

After schema changes: `uv run python scripts/backfill_structured.py`

## License

MIT — see [LICENSE](LICENSE).

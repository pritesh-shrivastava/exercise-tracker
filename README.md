# Exercise Tracker

A small, portable workout tracker for a private VPS.

The primary workflow is a small mobile web form served from the VPS and opened from your phone over Tailscale. The app writes directly to a local SQLite database and re-reads inserted rows before confirming saves. All workout logging and edits go through the form; reports, DB inspection, backups, and coaching prompts are local scripts over SQLite.

## Folder layout

```
data/                        — SQLite database
tracker/
  __init__.py                — empty package marker
  models.py                  — shared workout row model, validation, details formatting
  exercises.py               — predefined exercise groups, form choices, and selector defaults
  normalizer.py              — canonical exercise names + typo recovery
  core.py                    — DB helpers (fetch, format, auto-migrate)
  reports.py                 — PR reports, progression series, and coaching helpers
tests/
  test_normalizer.py         — normalizer unit tests
  test_reports.py            — report, progression, and coaching tests
  test_web_form.py           — structured form helper tests
scripts/
  summary.py                 — quick stats (default), PRs (--prs), or coaching prompts (--coach)
  web_form.py                — stdlib mobile web form: Log, Today, Recent, PRs, Progression
  exercise-web-form.service  — systemd unit for always-on localhost form server
  backfill_structured.py     — one-off backfill of structured columns (sets, reps, weight_kg, etc.)
  backup_db.py               — Azure Blob backup implementation (SQLite + CSV upload only)
  azure_lifecycle_policy_30d.json — Azure policy deleting workout backup blobs after 30 days
  restore_db.sh              — restore database from Azure Blob backup
pyproject.toml               — uv project config with ruff, mypy, pytest
design.md                    — data model, variation rules, logging behaviour
```

## Quick start

```bash
cd /home/azureuser/exercise-tracker
uv run python scripts/summary.py
uv run python scripts/summary.py --prs   # personal records — compact, one line per exercise
uv run python scripts/summary.py --coach # advisory prompts from past logged data
uv run python scripts/web_form.py         # mobile web form at http://127.0.0.1:8765/log
```

## Mobile web workflow

The preferred always-on setup runs the Python form on localhost under systemd, then exposes it privately inside the tailnet with Tailscale Serve:

```bash
cd /home/azureuser/exercise-tracker
sudo cp scripts/exercise-web-form.service /etc/systemd/system/exercise-web-form.service
sudo systemctl daemon-reload
sudo systemctl enable --now exercise-web-form.service
sudo tailscale serve --bg --http=8765 localhost:8765
```

Open the tailnet-only URL from a Tailscale-connected phone or laptop:

```text
http://azure-vps.tail5d90bf.ts.net:8765/log
```

Useful checks:

```bash
systemctl status exercise-web-form.service --no-pager
tailscale serve status
curl http://127.0.0.1:8765/log
```

If `tailscale` is not installed or not logged in, Tailscale Serve cannot expose the form. Install/configure Tailscale first, or run the form for local-only use:

```bash
uv run python scripts/web_form.py --host 127.0.0.1 --port 8765
```

Do not bind this app to a public VPS interface unless you add real authentication in front of it. The stdlib web form intentionally has no public-internet auth layer; Tailscale is the access control boundary.

## Weekly training template (canonical)

The tracker is designed to work even when you only train 3–4 days/week. The canonical plan is a simple 4-day Upper/Lower hypertrophy rotation (~60 minutes).

### Priority rotation (Upper/Lower)

Follow the next available slot instead of forcing a rigid calendar:

1. Upper A
2. Lower A (+ arms + abs)
3. Upper B
4. Lower B (+ arms + abs)

#### Upper A

- Barbell Bench Press — 4×6–10
- Chest Supported Rows — 4×8–12
- Lat Pull Down (wide grip) — 3×10–15
- Vertical Chest Press Machine — 2×10–15
- Lateral Raise — 2×12–20

#### Lower A (+ arms + abs)

- Horizontal Leg Press — 4×10–15
- Leg Extension — 3×12–20
- Hamstring Curl — 3×10–15
- Superset: Tricep Pushdown — 3×10–15 + Dumbbell Bicep Curl — 3×10–15
- Hanging Knee Raise — 3×8–15
- Optional: Calf Raise — 2×10–15

#### Upper B

- Lat Pull Down (short grip) *or* Assisted Pull Up — 4×8–12
- Seated Cable Row — 4×8–12
- Dumbbell Shoulder Press — 3×6–10
- Face Pull — 3×12–20
- Rear Delt Fly — 2×12–20

#### Lower B (+ arms + abs)

- Barbell Romanian Deadlift — 4×6–10
- Goblet Squat — 3×10–15
- Glute Kickback Machine — 3×10–15
- Superset: Cable Overhead Tricep Extension — 3×10–15 + Dumbbell Hammer Curl — 3×8–12
- Bodyweight Abs Crunch — 3×12–25
- Optional: Hamstring Curl — 2×10–15

### If you train 3 days in a week

Run the first 3 slots and pick up where you left off next time:

- Day 1: Upper A
- Day 2: Lower A
- Day 3: Upper B

### If you train 4 days in a week

- Day 1: Upper A
- Day 2: Lower A
- Day 3: Upper B
- Day 4: Lower B

### If you train 5 days in a week

- Day 1: Upper A
- Day 2: Lower A
- Day 3: Upper B
- Day 4: Lower B
- Day 5: Optional conditioning / mobility (easy)

## Workout form

All workout logging happens through the mobile form. The form is intentionally small: open it from your phone, enter one or more structured rows, save, and verify the exact inserted rows shown back from SQLite.

Pages:

- `Log` — date, exercise, variation, sets, reps, weight, equipment, body part, and per-hand fields
- `Today` — today's saved rows, with exact row selection for updates/deletes
- `Recent` — recent saved rows without internal IDs, raw text, or derived details
- `PRs` — DB-backed PR output using the same report code as `scripts/summary.py --prs`, with a body-part dropdown
- `Progression` — SVG weight charts for exercise/variation series with at least 3 weighted entries, with a body-part dropdown

The form should not show "saved" until the SQLite write succeeds and the inserted rows are re-read from `data/workouts.sqlite`.

The exercise selector uses metadata from `tracker/exercises.py` for every predefined exercise. Selecting a listed exercise pre-fills equipment and body part; bodyweight selections also clear the weight field. Custom exercises are allowed, but should include explicit equipment and body-part values because they do not have selector metadata.

HTML responses are gzip-compressed when the browser advertises support, which keeps the repeated mobile form controls and progression charts fast over Tailscale.

## Reporting and Inspection

Use local commands against the SQLite database:

```bash
uv run python scripts/summary.py          # recent activity
uv run python scripts/summary.py --prs    # personal records
uv run python scripts/summary.py --coach  # advisory training prompts
sqlite3 data/workouts.sqlite              # raw DB inspection
```

For raw display, hide `id`, `raw_text`, and `details` unless you are deliberately auditing internals. Hide `variation` when it is `default`.

Variation rules:

- Valid variations are `default`, `flat`, `incline`, `decline`, `short grip`, `wide grip`, and `reverse grip`.
- Bench movements use `flat`, `incline`, or `decline`.
- Lat Pull Down uses `short grip` or `wide grip`.
- Reverse-grip cable curls and tricep pushdowns use `reverse grip`.

Progression chart rules:

- Only rows with a non-empty `weight_kg` count toward progression history.
- Exercises are tracked separately by `exercise` plus `variation`.
- A chart appears once that exercise/variation has at least 3 weighted entries.
- Chart order follows saved body-part order from `tracker.reports.BODY_PART_ORDER`, then exercise and variation.
- The `/progression?part=...` filter uses the same body-part dropdown convention as `/prs?part=...`.
- The chart plots the full weighted history; the table under each chart shows only the latest 3 entries.
- Dumbbell rows store total load; `per_hand=1` only changes display, such as showing `20kg` as `10ea.`.

Useful DB cleanup checks:

```bash
sqlite3 data/workouts.sqlite "SELECT id, workout_date, exercise FROM workouts WHERE equipment IS NULL OR equipment = '';"
sqlite3 data/workouts.sqlite "SELECT id, workout_date, exercise FROM workouts WHERE equipment != 'bodyweight' AND weight_kg IS NULL;"
sqlite3 data/workouts.sqlite "SELECT exercise, GROUP_CONCAT(DISTINCT equipment), COUNT(*) FROM workouts GROUP BY exercise HAVING COUNT(DISTINCT equipment) > 1 ORDER BY exercise;"
```

Backups are intended to be run via cron/systemd (or manually) using the backup script:

```bash
uv run python scripts/backup_db.py
```

PR summaries do not require a separate “weekly_pr_summary” script. For a PR report (e.g. in a weekly cron email),
use the existing summary entry point:

```bash
uv run python scripts/summary.py --prs
```

## Maintenance

```bash
uv run pytest
uv run ruff check .      # lint
uv run mypy tracker/ scripts/summary.py scripts/web_form.py  # type check
uv run vulture tracker/ tests/ scripts/summary.py scripts/web_form.py  # dead code check
```

After schema changes: `uv run python scripts/backfill_structured.py`

## License

MIT — see [LICENSE](LICENSE).

# Exercise Tracker

A small, portable workout tracker for a private VPS.

The primary workflow is a small mobile web form served from the VPS and opened from your phone over Tailscale. The app writes directly to a local SQLite database and re-reads inserted rows before confirming saves. Telegram/Hermes is the read-only assistant layer for summaries, PRs, DB inspection, backups, and coaching from past data; workout data entry is form-only.

## Folder layout

```
data/                        — SQLite database
tracker/
  __init__.py                — empty package marker
  models.py                  — shared workout row model, validation, details formatting
  normalizer.py              — canonical exercise names + typo recovery
  core.py                    — DB helpers (fetch, format, auto-migrate)
  reports.py                 — PR report by body part with scoring
tests/
  test_normalizer.py         — normalizer unit tests
  test_reports.py            — PR report tests
  test_web_form.py           — structured form helper tests
scripts/
  summary.py                 — quick stats (default), PRs (--prs), or coaching prompts (--coach)
  web_form.py                — stdlib mobile web form: Log, Today, PRs
  exercise-web-form.service  — systemd unit for always-on localhost form server
  backfill_structured.py     — one-off backfill of structured columns (sets, reps, weight_kg, etc.)
  backup_db.py               — Azure Blob backup implementation (SQLite + CSV upload only)
  azure_lifecycle_policy_30d.json — Azure policy deleting workout backup blobs after 30 days
  restore_db.sh              — restore database from Azure Blob backup
skills/                      — Hermes agent skill definitions (loaded on demand)
  workout-summary/SKILL.md
  query-db/SKILL.md
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

## Telegram/Hermes

Hermes Agent can query workouts, run maintenance, and coach from Telegram. It does not log workouts or parse pasted workout text into rows:

- "show my PRs" → runs `uv run python scripts/summary.py --prs`, sends compact one-line-per-exercise results back
- "show recent workouts" → runs `uv run python scripts/summary.py`
- "coach me", "what should I train next?" → runs `uv run python scripts/summary.py --coach`, then gives concise advisory guidance from SQLite-backed history
- "show rows" → queries SQLite through the `query-db` skill

Hermes can play an advisory role over Telegram: look at last training dates by body part, spot stale high-rep PRs that may be ready for a weight increase, answer progress questions, and suggest the next focus. It should not present coaching as medical advice, should not invent data from memory, and should direct any new logs or edits back to the private form.

## Workout form

All workout logging happens through the mobile form. The form is intentionally small: open it from your phone, enter one or more structured rows, save, and verify the exact inserted rows shown back from SQLite.

Pages:

- `Log` — date, exercise, variation, sets, reps, weight, equipment, and per-hand fields
- `Today` — today's saved rows, with exact row selection for updates/deletes
- `PRs` — DB-backed PR output using the same report code as `scripts/summary.py --prs`

The form should not show "saved" until the SQLite write succeeds and the inserted rows are re-read from `data/workouts.sqlite`.

## Hermes Agent skills

The `skills/` folder teaches Hermes the procedures for this tracker. Each skill is a folder named `<name>/` with a `SKILL.md` inside:

```
skills/
  workout-summary/  — tiered summary: recent entries, PRs, and coaching prompts
  query-db/         — show raw table rows, excluding id/raw_text/details
```

Skills are auto-discovered by Hermes on startup. The agent picks the right skill based on what you ask, then runs the procedure in `SKILL.md`. You can also trigger any skill manually.

Backups are not a Hermes skill. Run `scripts/backup_db.py` directly from cron/systemd or an explicit shell session.

Hermes runtime memory lives outside this repo at `~/.hermes/memories/MEMORY.md` and is not part of the database backup.


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

# Exercise Tracker Design

## Purpose

This tracker keeps workout logs portable and easy to move between VPS instances.
The database is the source of truth. The primary user interface is a small stdlib mobile web form served from the VPS and reached from the phone over Tailscale. Hermes Agent remains available for summaries, PRs, backups, and raw DB inspection, but it does not log workout entries.

## Data model

### Schema (14 columns)

Each workout row stores:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | auto-increment |
| `logged_at` | TEXT | ISO timestamp in IST |
| `workout_date` | TEXT | IST date |
| `workout_type` | TEXT | currently `strength` for form-created rows; legacy rows may contain `cardio` or `note` |
| `exercise` | TEXT | canonical exercise name (via normalizer) |
| `variation` | TEXT | `default`, `flat`, `incline`, `decline`, `short grip`, `wide grip` |
| `details` | TEXT | compact set/reps/weight summary string |
| `raw_text` | TEXT | trace field; form-created rows store the selected exercise |
| `source` | TEXT | origin of row, currently `form` for web form entries |
| `sets` | INTEGER | number of sets |
| `reps` | INTEGER | number of reps |
| `weight_kg` | REAL | total weight in kg (NOT per-hand) |
| `equipment` | TEXT | `dumbbells`, `barbell`, `machine`, `cable`, `bodyweight`, `kettlebell`, `smith machine`, `band`, `other` |
| `per_hand` | INTEGER | boolean: was weight entered as per-hand? |

### Weight convention

- **Total weight stored** (NOT per-hand), with `per_hand` boolean flag
- Example: Dumbbell Shoulder Press "15 kg each hand" → `weight_kg=30.0, per_hand=1`
- Display format: `3x15 @ 30 (15 ea.)`
- Goblet squats: single dumbbell held with both hands, `per_hand=0`

### Auto-migration

`ensure_db()` in `tracker/core.py` creates the table on first call and **auto-adds** missing structured columns on subsequent calls (no manual migration needed). Indexes on `workout_date` and `workout_type` are also created.

SQLite triggers reject invalid structured rows:

- `variation` must be one of `default`, `flat`, `incline`, `decline`, `short grip`, `wide grip`
- `per_hand=1` is valid only when `equipment='dumbbells'`

## Variation rules

- Non-bench strength entries use `default` unless a grip is specified
- Bench press entries use `flat` for the base variation; incline and decline are tracked as separate rows
- Lat Pull Down grip variations use `short grip` or `wide grip` in the variation column (not in the exercise name)
- Legacy rows that stored grip in the exercise name (e.g. `Lat Pull Down (Short Grip)`) have been migrated to the variation column

## Structured entry behaviour

### Exercise name normalisation

`tracker/normalizer.py` normalizes exercise names to canonical forms. Current implementation truth:

- Bench press with "press" in text → `Barbell Bench Press` (if "barbell" in text) or `Dumbbell Bench Press` (default)
- Lat pull-down → always `Lat Pull Down`; grip is selected in the form variation field
- Rear delt → `Rear Delt Fly`
- Canonical names: `shoulder press` → `Dumbbell Shoulder Press`, `leg curl` → `Hamstring Curl`, `leg press` → `45 Degree Leg Press`, `seated row` / `horizontal row` → `Chest Supported Rows`, `seated row machine` → `Seated Row Machine`, `abs crunch` → `Seated Abs Crunch Machine`
- Title-case fallback for unknown exercises

Seated/horizontal row entries without a clear machine distinction are treated as `Chest Supported Rows`. Explicit `seated row machine` entries are tracked separately as `Seated Row Machine`.

### Equipment defaults

`scripts/web_form.py` provides exercise-specific default equipment values and lets the user override them before saving.

### Weight edge cases

- Weight is entered as total stored weight.
- For dumbbell entries that should display per-hand weight, set `per_hand=1`; display derives each-hand weight as `weight_kg / 2`.
- Bodyweight rows can leave weight blank.

### Logging behaviour

The form writes one structured strength row per submitted row. If a session includes multiple weights or variations for the same exercise, enter them as separate form rows. Reports use structured columns (`sets`, `reps`, `weight_kg`, `equipment`, `per_hand`) rather than reparsing `details`.

### Web form behaviour

`scripts/web_form.py` is the preferred daily logging path. It exposes:
- `Log` — structured strength entry with date, exercise, variation, sets, reps, weight, equipment, and per-hand controls; supports multiple rows before saving.
- `Today` — DB-backed list of today's strength rows with exact row selection for corrections and deletes.
- `PRs` — renders the same report path as `scripts/summary.py --prs`.

The form writes directly to `data/workouts.sqlite`, then re-queries inserted or edited rows before showing a saved/updated/deleted confirmation. A user-facing confirmation is only valid after both the SQLite write and the post-write read succeed.

The web form has no public-internet authentication layer. Serve it only on `127.0.0.1` for local use or on the VPS Tailscale IP for phone access over the private tailnet. Do not bind it to a public VPS interface unless a real auth proxy is added.

## Summary behaviour

- `default` variations stay hidden in display output
- `flat`, `incline`, and `decline` are shown for bench press
- Summary is grouped by body part first, then exercise
- PR scoring: highest weight → highest reps → highest sets → earliest date
- PR output is compact: one line per exercise, variations shown inline in brackets

Summary responses are tiered — Hermes picks the right one based on natural language:

| Level | Example trigger | Script |
|-------|----------------|--------|
| Short | "show recent workouts" | `uv run python scripts/summary.py` |
| Full PRs | "show my PRs", "best lifts" | `uv run python scripts/summary.py --prs` |

### Body part classification

Chest 🩻 | Back 🧱 | Shoulders 🧢 | Biceps 💪 | Triceps 🔻 | Legs 🦵 | Core ⚡ | Other 📦

Keywords for each group are in `tracker/reports.py:body_part()`. Special rules: `Rear Delt Fly` → Shoulders (not Back), `Hamstring Curl` → Legs (not Biceps).

## Hermes skills architecture

Skills live in `skills/<name>/SKILL.md` and teach Hermes the procedures for this tracker. The agent loads a skill's full content only when the task matches — descriptions are loaded at startup, full bodies on demand.

Three skills, all in `skills/`:
- `workout-summary` — pick the right summary tier and format for Telegram
- `backup-db` — SQLite + CSV upload to Azure Blob (retention handled server-side by a 30-day lifecycle policy, not by the skill)
- `query-db` — browse raw table rows, excluding id/raw_text/details

The data layer (`tracker/core.py`, `tracker/models.py`) is intentionally separate from the agent layer. Skills call the Python scripts; they do not replicate logic.

### Telegram topic skill binding

This tracker lives in the **"Health" DM topic** (`thread_id: 7218`) of Pritesh's Telegram DM with Mercury (the shared VPS Hermes agent). The interactive skills are auto-loaded on every new session in that topic via `platforms.telegram.extra.dm_topics` in `~/.hermes/config.yaml`:

```yaml
extra:
  dm_topics:
  - chat_id: 5727496535
    topics:
    - name: Health
      thread_id: 7218                 # REQUIRED for an existing topic, else it re-creates a duplicate
      skill:                          # a LIST is supported (auto_skill: str | list[str])
      - query-db
      - workout-summary
```

**Why:** without binding, a Telegram message in this topic starts a session that only has the skill *descriptions* in context — not the full procedures or `tracker/` script paths. On `gpt-4.1-mini` (Mercury's current main model, a weaker procedural instruction-follower than the DeepSeek/Kimi models used before) this caused the agent to **fumble queries with raw shell** instead of engaging the skill — e.g. a 2026-06-03 "show PRs" request where it hunted for a non-existent `scripts/summary.py --filter`. Binding force-loads the skill bodies so logging and queries follow the documented procedure.

- `backup-db` is **deliberately not bound** — it's a nightly cron-only workflow, and backup/delete authority should never load into an interactive logging session (cf. the 2026-05-28 wrong-container deletion incident).
- Binding fires only on **new sessions** and only on **incoming messages**, so it doesn't conflict with the crons' own `--skill`. Verify after a gateway restart: `grep "DM topic loaded from config" ~/.hermes/logs/gateway.log` should show `5727496535:Health -> thread_id=7218`.

Operational rule: interactive skills should use `cd /home/azureuser/exercise-tracker && ...` or otherwise set the repo root explicitly. Telegram sessions may not start in this repo, while cron jobs usually set `--workdir`.

Stateful rule: do not use sub-agents for workout updates, deletes, or DB queries. The active Health session must perform DB mutations directly when a skill allows them.

## Minimal form link

The preferred and only logging interface is a small mobile form, not a full workout dashboard. It exists to reduce the failure modes seen in chat-based logging: false "logged" confirmations before DB writes, wrong working directory, memory-based PR answers, ambiguous row edits, and delegated DB mutations.

SQLite remains the source of truth. The form must write directly to `data/workouts.sqlite`, then re-query the database before showing any saved/logged confirmation. A user-facing save confirmation is only valid after both the SQLite insert/update and the post-write read succeed.

V1 pages:
- `Log` — structured strength entry with date, exercise, variation, sets, reps, weight, equipment, and per-hand controls; supports multiple rows before saving.
- `Today` — DB-backed list of today's rows with exact row selection for corrections.
- `PRs` — renders the same report path as `scripts/summary.py --prs`.

Hermes remains useful as the summary and maintenance interface, but it should not log workout entries. Deployment/security is intentionally private-by-default: serve over Tailscale, not the public internet.

### Maintenance jobs

Recommended recurring maintenance:
1. **DB backup** (nightly at 03:00 IST): run `scripts/backup_db.py` to upload SQLite + CSV to Azure Blob. Use a container SAS with create/write only (`cw`, no delete/list). Old blobs are deleted by Azure lifecycle policy after 30 days.
2. **PR review** (manual or ad hoc): use the web form `PRs` page or run `uv run python scripts/summary.py --prs`.

The old Hermes memory PR update cron is no longer part of the primary workflow. PRs should come from SQLite-backed reports on demand.


## Open source trackers - best practices

Open-source workout trackers are useful references, but this project deliberately stays smaller than them:

- **wger** (https://github.com/wger-project/wger) is a self-hosted fitness manager with routines, automatic progression rules, nutrition, exercise wiki, mobile apps, and REST APIs. Relevant lesson: keep workout logs, exercise metadata, progression/reporting, and automation boundaries separate.
- **GitHub workout-tracker topic survey** (https://github.com/topics/workout-tracker) shows common tracker patterns: PR tracking, dashboards, exercise databases, imports from commercial apps, self-hosting, offline/privacy-first storage, and mobile-first logging. Relevant lesson: this repo should keep data portable and structured now, even if dashboards/imports are added later.
- **Nous Hermes 4 research** (https://arxiv.org/abs/2508.18255 and https://huggingface.co/collections/NousResearch/hermes-4-collection) is model-level evidence for structured multi-turn reasoning and instruction following. Treat it as support for skill-buffering and explicit procedures, not as Hermes Agent runtime documentation.

Design implication: the DB remains the source of truth; Python owns validation, reporting, and backup; Hermes skills are procedural wrappers that route read/maintenance intent and call repo tools.

## Maintenance notes

- Keep raw text intact
- Normalize exercise names in code, not by rewriting user input
- Backfill older rows when schema rules change: `uv run python scripts/backfill_structured.py`
- Keep the repo copyable as-is, with SQLite and env vars being enough to restore it
- Skills belong in the repo. Runtime Hermes memory does not; it is agent state and is not part of the database backup.
- After changing models/normalizer/web form code, run `uv run pytest`
- SQLite auto-ALTER in `ensure_db()` handles schema migration on startup; no manual DDL needed

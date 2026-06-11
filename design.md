# Exercise Tracker Design

## Purpose

This tracker keeps workout logs portable and easy to move between VPS instances.
The database is the source of truth. Hermes Agent is the sole interface — via Telegram for logging and queries, and via cron for scheduled reports. The Python scripts are tools that Hermes calls; they are not run directly by the user.

## Data model

### Schema (14 columns)

Each workout row stores:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | auto-increment |
| `logged_at` | TEXT | ISO timestamp in IST |
| `workout_date` | TEXT | IST date |
| `workout_type` | TEXT | `strength`, `cardio`, or `note` |
| `exercise` | TEXT | canonical exercise name (via normalizer) |
| `variation` | TEXT | `default`, `flat`, `incline`, `decline`, `short grip`, `wide grip` |
| `details` | TEXT | compact set/reps/weight summary string |
| `raw_text` | TEXT | original pasted input |
| `source` | TEXT | origin of row (`manual`, `telegram`, etc.) |
| `sets` | INTEGER | parsed number of sets |
| `reps` | INTEGER | parsed number of reps |
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

## Parsing behaviour

### Strength parsing

Handles these format variants (in priority order):

1. **Continuation lines**: bare `N x M [@ weight]` — inherits exercise from previous line
2. **Weight-first**: `Exercise - 20 kg 3 sets x 15 reps`
3. **Multi-set comma split**: `Exercise - 2 x 15 with 5 + 5 kg, 1 set of 15 rep with 7.5 kg`
4. **Standard**: `exercise N x M [@ weight]`
5. **Multi-set-of inside comma parsing**: `, N set(s) of M rep(s) [@ weight]`

Typo recovery: `woth` → `with`, `dumbell` → `dumbbell`, `biceo` → `bicep`, `calf rause` → `calf raise`, etc.

### Exercise name normalisation

`tracker/normalizer.py` normalizes exercise names to canonical forms. Current implementation truth:

- Bench press with "press" in text → `Barbell Bench Press` (if "barbell" in text) or `Dumbbell Bench Press` (default)
- Lat pull-down → always `Lat Pull Down`; grip goes into variation column via `detect_variations()`
- Rear delt → `Rear Delt Fly`
- Canonical names: `shoulder press` → `Dumbbell Shoulder Press`, `leg curl` → `Hamstring Curl`, `leg press` → `45 Degree Leg Press`, `seated row` / `horizontal row` → `Seated Row machine`, `abs crunch` → `Seated Abs Crunch Machine`
- Title-case fallback for unknown exercises

Known cleanup item: `AGENTS.md` prefers `Seated Horizontal Row`, while the current normalizer maps seated/horizontal row inputs to `Seated Row machine`. Do not rewrite existing DB rows casually; choose one canonical name deliberately and backfill if this is changed.

### Equipment inference

Keyword-based on exercise name + raw text (combined):

`dumbbells` | `barbell` | `cable` | `machine` | `bodyweight` | `kettlebell` | `smith machine` | `band` | `other`

Machine exercises are detected via a hardcoded set of exercise names (Chest Press, Pec Fly, Lat Pull Down, Seated Row machine, 45 Degree Leg Press, Horizontal Leg Press, etc.).

### Weight edge cases

- Barbell `empty bar` and barbell `0 kg` are stored as untracked weight: `weight_kg=NULL`
- Dumbbell `A + B kg` is stored as total `A+B` with `per_hand=1`
- Dumbbell explicit `each`, `ea.`, `per hand`, or `each hand` is doubled and stored as total, unless it is a single-implement movement such as goblet squat
- Dumbbell single-number weights are a user-policy hazard: current parser defaults them to `per_hand=1` for most dumbbell movements, but the logging skill treats user single-number dumbbell entries as total weight unless explicitly per-hand. Verify post-log PR output and fix rows before reporting.

### Logging behaviour

When a pasted line contains both incline and decline bench wording:
- the parser creates two strength rows
- one row gets `incline` variation
- one row gets `decline` variation
- both keep the same raw text for traceability

Lines that do not match strength or cardio patterns are preserved as `note` rows. Reports should use structured columns (`sets`, `reps`, `weight_kg`, `equipment`, `per_hand`) rather than reparsing `details`.

### Cardio parsing

Matches: `[distance km/mi] [activity] duration [min/hr] [in HH:MM]`

Examples: `20 min zone 2 cardio`, `5 km run 28 min`, `cycling 45 min`

## Summary behaviour

- `default` variations stay hidden in display output
- `flat`, `incline`, and `decline` are shown for bench press
- Summary is grouped by body part first, then exercise
- PR scoring: highest weight → highest reps → highest sets → earliest date
- PR output is compact: one line per exercise, variations shown inline in brackets

Summary responses are tiered — Hermes picks the right one based on natural language:

| Level | Example trigger | Script |
|-------|----------------|--------|
| Short | "show recent workouts" | `python summary.py` |
| Full PRs | "show my PRs", "best lifts" | `python summary.py --prs` |

### Body part classification

Chest 🩻 | Back 🧱 | Shoulders 🧢 | Biceps 💪 | Triceps 🔻 | Legs 🦵 | Core ⚡ | Other 📦

Keywords for each group are in `tracker/reports.py:body_part()`. Special rules: `Rear Delt Fly` → Shoulders (not Back), `Hamstring Curl` → Legs (not Biceps).

## Hermes skills architecture

Skills live in `skills/<name>/SKILL.md` and teach Hermes the procedures for this tracker. The agent loads a skill's full content only when the task matches — descriptions are loaded at startup, full bodies on demand.

Four skills, all in `skills/`:
- `log-workout` — parse and insert lines, handle incline/decline split, confirm count
- `workout-summary` — pick the right summary tier and format for Telegram
- `backup-db` — no-agent SQLite + CSV upload to Azure Blob (retention handled server-side by a 30-day lifecycle policy, not by the skill)
- `query-db` — browse raw table rows, excluding id/raw_text/details

The data layer (`tracker/core.py`, `tracker/parser.py`) is intentionally separate from the agent layer. Skills call the Python scripts; they do not replicate logic.

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
      - log-workout
      - query-db
      - workout-summary
```

**Why:** without binding, a Telegram message in this topic starts a session that only has the skill *descriptions* in context — not the full procedures or `tracker/` script paths. On `gpt-4.1-mini` (Mercury's current main model, a weaker procedural instruction-follower than the DeepSeek/Kimi models used before) this caused the agent to **fumble queries with raw shell** instead of engaging the skill — e.g. a 2026-06-03 "show PRs" request where it hunted for a non-existent `summary.py --filter`. Binding force-loads the skill bodies so logging and queries follow the documented procedure.

- `backup-db` is **deliberately not bound** — it's a nightly cron-only workflow, and backup/delete authority should never load into an interactive logging session (cf. the 2026-05-28 wrong-container deletion incident).
- Binding fires only on **new sessions** and only on **incoming messages**, so it doesn't conflict with the crons' own `--skill`. Verify after a gateway restart: `grep "DM topic loaded from config" ~/.hermes/logs/gateway.log` should show `5727496535:Health -> thread_id=7218`.

Operational rule: interactive skills should use `cd /home/azureuser/exercise-tracker && ...` or otherwise set the repo root explicitly. Telegram sessions may not start in this repo, while cron jobs usually set `--workdir`.

Stateful rule: do not use sub-agents for workout logging, workout updates, deletes, or DB queries. The active Health session owns the workout buffer and must perform DB writes directly.

### Cron jobs

Scheduled via Hermes cron (`hermes cron create ...`, persisted to `~/.hermes/cron/jobs.json`):
1. **PR summary** (weekly): runs `python summary.py --prs` and updates Hermes memory with latest PRs
2. **DB backup** (nightly at 03:00 IST): runs a Hermes `no-agent` wrapper (`~/.hermes/scripts/exercise_tracker_backup_db.py`) that executes repo code in `scripts/backup_db.py` to upload SQLite + CSV to Azure Blob. **Write-only** — the cron uses a container SAS with create/write only (`cw`, no delete/list), and old blobs are deleted by Azure lifecycle policy after 30 days. Install command and policy JSON live in `skills/backup-db/SKILL.md` and `scripts/azure_lifecycle_policy_30d.json`.


## Open source trackers - best practices

Open-source workout trackers are useful references, but this project deliberately stays smaller than them:

- **wger** (https://github.com/wger-project/wger) is a self-hosted fitness manager with routines, automatic progression rules, nutrition, exercise wiki, mobile apps, and REST APIs. Relevant lesson: keep workout logs, exercise metadata, progression/reporting, and automation boundaries separate.
- **GitHub workout-tracker topic survey** (https://github.com/topics/workout-tracker) shows common tracker patterns: PR tracking, dashboards, exercise databases, imports from commercial apps, self-hosting, offline/privacy-first storage, and mobile-first logging. Relevant lesson: this repo should keep data portable and structured now, even if dashboards/imports are added later.
- **Nous Hermes 4 research** (https://arxiv.org/abs/2508.18255 and https://huggingface.co/collections/NousResearch/hermes-4-collection) is model-level evidence for structured multi-turn reasoning and instruction following. Treat it as support for skill-buffering and explicit procedures, not as Hermes Agent runtime documentation.

Design implication: the DB remains the source of truth; Python owns parsing, validation, reporting, and backup; Hermes skills are procedural wrappers that route user intent, preserve the logging buffer, and call repo tools.

## Maintenance notes

- Keep raw text intact
- Normalize exercise names in code, not by rewriting user input
- Backfill older rows when schema rules change: `uv run python scripts/backfill_structured.py`
- Keep the repo copyable as-is, with SQLite and env vars being enough to restore it
- Skills belong in the repo. Runtime Hermes memory does not; it is agent state and is not part of the database backup.
- After changing parser/normalizer, run `uv run pytest` — 99 tests should pass
- SQLite auto-ALTER in `ensure_db()` handles schema migration on startup; no manual DDL needed

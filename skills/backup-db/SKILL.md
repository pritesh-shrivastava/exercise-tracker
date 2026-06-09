---
name: backup-db
description: Use when the user asks to back up the database, run a backup, or upload the workouts files to Azure Blob Storage. Uploads both the raw SQLite file and a CSV export. Also triggered by the nightly Hermes cron job.
version: 2.0.0
---

## When to use

- Manual: "back up the database", "upload a backup", "save the database"
- Scheduled: nightly Hermes no-agent cron job at 03:00 IST (see [Schedule](#schedule) below)

## Schedule

This skill is registered as a Hermes **no-agent** cron job that runs every night at 03:00 IST.
Hermes requires `--script` files to live under `~/.hermes/scripts/`, so deploy only the tiny
wrapper there. The backup implementation stays in this repo at `scripts/backup_db.py`.

```
install -m 755 /home/azureuser/exercise-tracker/scripts/hermes_backup_db_wrapper.py ~/.hermes/scripts/exercise_tracker_backup_db.py
hermes cron create "0 3 * * *" --name exercise-tracker-db-backup --script exercise_tracker_backup_db.py --no-agent --workdir /home/azureuser/exercise-tracker --deliver telegram:5727496535:7218
```

Notes:
- The cron expression is evaluated in the Hermes process's local timezone. The VPS runs on IST (`Asia/Kolkata`), so `0 3 * * *` fires at 03:00 IST. On a UTC VPS, use `30 21 * * *` (21:30 UTC = 03:00 IST next day).
- Verify the job was created: `hermes cron list`. Job definitions are persisted to `~/.hermes/cron/jobs.json`; execution outputs land in `~/.hermes/cron/output/{job_id}/`.
- To change the schedule, delete and recreate: `hermes cron delete <job_id>` then re-run the create command.
- Retention is owned by the Azure Blob lifecycle policy: **30 days**.
- The script must not list, prune, or delete blobs. Do not give the cron credential delete permission.

## Procedure

Each run uploads two artifacts to the same container, both with a datetime-stamped name (`workouts-YYYYMMDDTHHMMSS.<ext>`):
- `.sqlite` — exact restore artifact, consumed by `scripts/restore_db.sh`
- `.csv` — portable export of the `workouts` table, for external tools / human eyeballing

The datetime suffix means manual runs never overwrite the scheduled nightly run.

### 0. Configure storage auth

Preferred auth is a container-scoped SAS token with create/write permissions only. It should not include delete permission.
Set these in `~/.hermes/.env`:

```text
AZURE_STORAGE_ACCOUNT=<storage account>
AZURE_BACKUP_CONTAINER=<container>
AZURE_STORAGE_SAS_TOKEN=<container SAS with create/write, no delete>
```

Do not use `AZURE_STORAGE_KEY` for the cron job. An account key is too broad and can delete blobs.

### 1. Confirm the database exists

```
ls -lh data/workouts.sqlite
```

### 2. Run the deterministic backup script

Hermes runs the wrapper in `~/.hermes/scripts/exercise_tracker_backup_db.py`, which executes
`/home/azureuser/exercise-tracker/scripts/backup_db.py`.

The script loads `~/.hermes/.env`, exports CSV with Python, uploads the SQLite and CSV blobs, and exits non-zero on failure.
It uses a temporary directory for the CSV, so cleanup happens without explicit `rm`.

## Required env vars

- `AZURE_STORAGE_ACCOUNT` — storage account name (set in Azure portal at provisioning time)
- `AZURE_BACKUP_CONTAINER` — container name (e.g. `workout-backups`)
- `AZURE_STORAGE_SAS_TOKEN` — preferred, container-scoped create/write token with no delete permission

Set `AZURE_STORAGE_ACCOUNT`, `AZURE_BACKUP_CONTAINER`, and `AZURE_STORAGE_SAS_TOKEN` in `~/.hermes/.env` so they're always present.

## Provisioning

### Initial container setup

Create the container and lifecycle policy outside the backup script.
The script assumes the container exists and intentionally does not create/list/delete blobs.

Apply the 30-day lifecycle policy from the repo-owned policy file:

```bash
az storage account management-policy create \
  --account-name hermesappsbackup \
  --resource-group hermes-rg \
  --policy @/home/azureuser/exercise-tracker/scripts/azure_lifecycle_policy_30d.json
```

## Pitfalls

- The cron should be `no_agent: true`; `last_status=ok` on an agent job can mean the agent merely reported "skipped".
- Keep `~/.hermes/scripts/exercise_tracker_backup_db.py` as a wrapper only. Do not copy backup logic there.
- The durable backup implementation lives in `scripts/backup_db.py`; the wrapper source lives in `scripts/hermes_backup_db_wrapper.py`.
- The script loads `~/.hermes/.env` itself because no-agent cron process env may not include recently edited values.
- Do not add `az storage blob delete`, `az storage blob list`, or prune logic. Retention is the Azure lifecycle policy.
- Use `AZURE_STORAGE_SAS_TOKEN` for least privilege. The backup script intentionally rejects account-key auth.
- The container holds both `.sqlite` and `.csv` blobs. `restore_db.sh` filters to `.sqlite` so the CSVs don't confuse it.

## Verification

```bash
/home/azureuser/.hermes/scripts/exercise_tracker_backup_db.py --dry-run
```

The dry run validates env/database access and prints the two blob names it would upload.
Real verification is a successful no-agent script run that prints both uploaded blob names.
To restore, run `bash scripts/restore_db.sh` from the repo root — it picks the latest `.sqlite` automatically.

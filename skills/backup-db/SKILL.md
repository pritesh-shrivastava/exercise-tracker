---
name: backup-db
description: Use when the user asks to back up the database, run a backup, or upload the workouts files to Azure Blob Storage. Uploads both the raw SQLite file and a CSV export.
version: 2.1.0
---

## When to use

- Manual: "back up the database", "upload a backup", "save the database"
- Scheduled: optional nightly VPS cron/systemd timer at 03:00 IST

## Schedule

Backups are maintenance for the VPS, not part of the mobile logging path. The durable implementation lives in this repo at `scripts/backup_db.py`.

Manual run:

```bash
cd /home/azureuser/exercise-tracker && uv run python scripts/backup_db.py
```

Notes:
- For automation, run the same command from a normal VPS cron or systemd timer at 03:00 IST.
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

- The durable backup implementation lives in `scripts/backup_db.py`.
- The script loads `~/.hermes/.env` itself because no-agent cron process env may not include recently edited values.
- Do not add `az storage blob delete`, `az storage blob list`, or prune logic. Retention is the Azure lifecycle policy.
- Use `AZURE_STORAGE_SAS_TOKEN` for least privilege. The backup script intentionally rejects account-key auth.
- The container holds both `.sqlite` and `.csv` blobs. `restore_db.sh` filters to `.sqlite` so the CSVs don't confuse it.

## Verification

```bash
cd /home/azureuser/exercise-tracker && uv run python scripts/backup_db.py --dry-run
```

The dry run validates env/database access and prints the two blob names it would upload.
Real verification is a successful run that prints both uploaded blob names.
To restore, run `bash scripts/restore_db.sh` from the repo root — it picks the latest `.sqlite` automatically.

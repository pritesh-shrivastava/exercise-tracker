---
name: backup-db
description: Use when the user asks to back up the database, run a backup, or upload the workouts files to Azure Blob Storage. Uploads both the raw SQLite file and a CSV export. Also triggered by the nightly Hermes cron job.
version: 1.1.0
---

## When to use

- Manual: "back up the database", "upload a backup", "save the database"
- Scheduled: nightly Hermes cron job at 01:00 IST (see [Schedule](#schedule) below)

## Schedule

This skill is registered as a Hermes cron job that runs every night at 03:00 IST. Install once on the VPS:

```
hermes cron create "0 3 * * *" "Back up the workouts database to Azure Blob Storage and prune to the last 7 copies" --skill backup-db
```

Notes:
- The cron expression is evaluated in the Hermes process's local timezone. The VPS runs on IST (`Asia/Kolkata`), so `0 3 * * *` fires at 03:00 IST. On a UTC VPS, use `30 21 * * *` (21:30 UTC = 03:00 IST next day).
- Verify the job was created: `hermes cron list`. Job definitions are persisted to `~/.hermes/cron/jobs.json`; execution outputs land in `~/.hermes/cron/output/{job_id}/`.
- To change the schedule, delete and recreate: `hermes cron delete <job_id>` then re-run the create command.
- Retention is **7 most recent blobs** (see step 3 below). With a nightly schedule that's 7 days of history — bump the prune `head -n -7` if longer retention is needed.

## Procedure

Each nightly run uploads two artifacts to the same container, both with a datetime-stamped name (`workouts-YYYYMMDDTHHMMSS.<ext>`):
- `.sqlite` — exact restore artifact, consumed by `scripts/restore_db.sh`
- `.csv` — portable export of the `workouts` table, for external tools / human eyeballing

The datetime suffix means manual runs never overwrite the scheduled nightly run.

1. Confirm the database exists:
   ```
   ls -lh data/workouts.sqlite
   ```

2. Dump the `workouts` table to CSV with a header row:
   ```
   STAMP=$(date +%Y%m%dT%H%M%S)
   sqlite3 -header -csv data/workouts.sqlite "SELECT * FROM workouts" > "/tmp/workouts-${STAMP}.csv"
   ```

3. Upload both files to Azure Blob Storage:
   ```
   az storage blob upload \
     --account-name $AZURE_STORAGE_ACCOUNT \
     --container-name $AZURE_BACKUP_CONTAINER \
     --name "workouts-${STAMP}.sqlite" \
     --file data/workouts.sqlite \
     --account-key $AZURE_STORAGE_KEY --overwrite

   az storage blob upload \
     --account-name $AZURE_STORAGE_ACCOUNT \
     --container-name $AZURE_BACKUP_CONTAINER \
     --name "workouts-${STAMP}.csv" \
     --file "/tmp/workouts-${STAMP}.csv" \
     --account-key $AZURE_STORAGE_KEY --overwrite
   ```

4. Prune to keep only the 7 most recent backups **of each type** (separate retention per format):
   ```
   for EXT in sqlite csv; do
     az storage blob list \
       --account-name $AZURE_STORAGE_ACCOUNT \
       --container-name $AZURE_BACKUP_CONTAINER \
       --query "sort_by([?ends_with(name, '.${EXT}')], &name)[].name" \
       --account-key $AZURE_STORAGE_KEY \
       --output tsv | head -n -7 | xargs -r -I{} \
       az storage blob delete \
         --account-name $AZURE_STORAGE_ACCOUNT \
         --container-name $AZURE_BACKUP_CONTAINER \
         --name {} --account-key $AZURE_STORAGE_KEY
   done
   ```

5. Clean up the local CSV temp file:
   ```
   rm -f "/tmp/workouts-${STAMP}.csv"
   ```

6. Confirm remaining blobs and report counts (expect ≤3 of each type).

## Required env vars

- `AZURE_STORAGE_ACCOUNT` — storage account name (set in Azure portal at provisioning time)
- `AZURE_BACKUP_CONTAINER` — container name (e.g. `workout-backups`)
- `AZURE_STORAGE_KEY` — storage account key (Portal → Storage account → Security + networking → Access keys → key1)

Set these on the VPS — add to `~/.hermes/.env` and restart Hermes. Verify with `hermes cron run backup-db` after install.

## Provisioning

One private blob container, created manually once via the Azure portal. After creating it, record the account name, container name, and access key in the env vars above.

## Pitfalls

- Run from the repo root so `data/workouts.sqlite` resolves correctly.
- **`sqlite3` CLI may not be installed.** This VPS has Python's `sqlite3` module but not the standalone CLI. If `sqlite3` command fails, use the Python fallback: `python /home/azureuser/exercise-tracker/skills/backup-db/scripts/csv_export.py /tmp/workouts-${STAMP}.csv`. Or directly: `python -c "import sqlite3, csv; ..."`
- The prune step is destructive; verify the blob list looks correct before running in a new environment.
- `STAMP` is captured once at the top of the run — sqlite, csv, and prune all use the same timestamp. Do not recompute it inside each step or the upload names will drift.
- The container holds **both** .sqlite and .csv blobs. The prune loop separates them by extension; `restore_db.sh` filters to `.sqlite` so the CSVs don't confuse it.

## Verification

```
az storage blob list \
  --account-name $AZURE_STORAGE_ACCOUNT \
  --container-name $AZURE_BACKUP_CONTAINER \
  --account-key $AZURE_STORAGE_KEY \
  --output table
```
Should show up to 7 blobs of each type named `workouts-YYYYMMDDTHHMMSS.{sqlite,csv}` (≤14 total).
To restore, run `bash scripts/restore_db.sh` from the repo root — it picks the latest `.sqlite` automatically.

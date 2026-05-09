---
name: backup-db
description: Use when the user asks to back up the database, run a backup, or upload the SQLite file to Azure Blob Storage. Also triggered by the weekly backup cron job.
version: 1.0.0
---

## When to use

- Manual: "back up the database", "upload a backup", "save the database"
- Scheduled: weekly cron job on the VPS

## Procedure

1. Confirm the database exists:
   ```
   ls -lh data/workouts.sqlite
   ```

2. Upload to Azure Blob Storage with a datestamped name:
   ```
   az storage blob upload \
     --account-name $AZURE_STORAGE_ACCOUNT \
     --container-name $AZURE_BACKUP_CONTAINER \
     --name "workouts-$(date +%Y%m%d).sqlite" \
     --file data/workouts.sqlite \
     --auth-mode login
   ```

3. Prune to keep only the 3 most recent backups:
   ```
   az storage blob list \
     --account-name $AZURE_STORAGE_ACCOUNT \
     --container-name $AZURE_BACKUP_CONTAINER \
     --query "sort_by([].name, &@)" \
     --output tsv | head -n -3 | xargs -I{} \
     az storage blob delete \
       --account-name $AZURE_STORAGE_ACCOUNT \
       --container-name $AZURE_BACKUP_CONTAINER \
       --name {} --auth-mode login
   ```

4. Confirm remaining blobs and report count.

## Required env vars

- `AZURE_STORAGE_ACCOUNT` — storage account name
- `AZURE_BACKUP_CONTAINER` — container name (e.g. `workout-backups`)
- Azure CLI authenticated via `az login` or managed identity on the VPS

## Pitfalls

- Run from the repo root so `data/workouts.sqlite` resolves correctly.
- Blob name uses the upload date — running twice on the same day overwrites the earlier upload.
- The prune step is destructive; verify the blob list looks correct before running in a new environment.

## Verification

```
az storage blob list \
  --account-name $AZURE_STORAGE_ACCOUNT \
  --container-name $AZURE_BACKUP_CONTAINER \
  --output table
```
Should show 1–3 blobs named `workouts-YYYYMMDD.sqlite`.
To restore, run `bash scripts/restore_db.sh` from the repo root.

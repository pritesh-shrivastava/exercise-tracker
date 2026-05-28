---
name: backup-db
description: Use when the user asks to back up the database, run a backup, or upload the workouts files to Azure Blob Storage. Uploads both the raw SQLite file and a CSV export. Also triggered by the nightly Hermes cron job.
version: 2.0.0
---

## When to use

- Manual: "back up the database", "upload a backup", "save the database"
- Scheduled: nightly Hermes cron job at 03:00 IST (see [Schedule](#schedule) below)

## Schedule

This skill is registered as a Hermes cron job that runs every night at 03:00 IST. Install once on the VPS:

```
hermes cron create "0 3 * * *" "Back up the workouts database to Azure Blob Storage" --skill backup-db
```

Notes:
- The cron expression is evaluated in the Hermes process's local timezone. The VPS runs on IST (`Asia/Kolkata`), so `0 3 * * *` fires at 03:00 IST. On a UTC VPS, use `30 21 * * *` (21:30 UTC = 03:00 IST next day).
- Verify the job was created: `hermes cron list`. Job definitions are persisted to `~/.hermes/cron/jobs.json`; execution outputs land in `~/.hermes/cron/output/{job_id}/`.
- To change the schedule, delete and recreate: `hermes cron delete <job_id>` then re-run the create command.
- **Retention is handled server-side by an Azure lifecycle policy** (30 days, see [Provisioning](#provisioning)). Hermes never runs delete commands — this skill only writes. Adjust the retention window by editing the lifecycle policy in Azure, not the skill.

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

4. Clean up the local CSV temp file:
   ```
   rm -f "/tmp/workouts-${STAMP}.csv"
   ```

5. Confirm the two new blobs are visible (skip if running unattended).

**No delete step.** Old blobs are pruned server-side by the Azure
lifecycle policy (see [Provisioning](#provisioning)). This skill is
write-only by design — see [the rationale below](#why-write-only).

## Required env vars

- `AZURE_STORAGE_ACCOUNT` — storage account name (set in Azure portal at provisioning time)
- `AZURE_BACKUP_CONTAINER` — container name (e.g. `workout-backups`)
- `AZURE_STORAGE_KEY` — storage account key (Portal → Storage account → Security + networking → Access keys → key1)

Set these on the VPS — add to `~/.hermes/.env` and restart Hermes. Verify with `hermes cron run backup-db` after install.

## Provisioning

One private blob container, created manually once via the Azure portal. After creating it, record the account name, container name, and access key in the env vars above.

### Lifecycle policy — 30-day retention

Retention is enforced server-side by an Azure lifecycle management policy.
Run once against the storage account (replace `$AZURE_STORAGE_ACCOUNT`):

```bash
az storage account management-policy create \
  --account-name $AZURE_STORAGE_ACCOUNT \
  --resource-group hermes-rg \
  --policy '{
    "rules": [{
      "enabled": true,
      "name": "prune-workout-backups",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "baseBlob": {
            "delete": { "daysAfterModificationGreaterThan": 30 }
          }
        },
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": ["workouts-"]
        }
      }
    }]
  }'
```

Azure runs the rule once per day. Both `.sqlite` and `.csv` blobs are
matched by the `workouts-` prefix. Verify with:

```bash
az storage account management-policy show \
  --account-name $AZURE_STORAGE_ACCOUNT \
  --resource-group hermes-rg
```

### Why write-only

This skill intentionally has **no delete logic**. On 2026-05-28 a
different cron-triggered run that included destructive `az storage blob
delete` commands escalated into deleting the entire container. Retention
is now handled by the Azure lifecycle engine, which doesn't need any
caller credential and can't be tricked into deleting the wrong thing by
a model misinterpretation.

Outstanding hardening (tracked separately):

- The skill still uses `--account-key`. The key in `~/.hermes/.env`
  grants full storage-account power, including container delete. Long
  term, replace with a scoped role on a managed identity, or enable
  immutability / container soft-delete on this account so even a leaked
  key can't wipe history.

## Pitfalls

- Run from the repo root so `data/workouts.sqlite` resolves correctly.
- **`sqlite3` CLI may not be installed.** This VPS has Python's `sqlite3` module but not the standalone CLI. If `sqlite3` command fails, use the Python fallback: `python /home/azureuser/exercise-tracker/skills/backup-db/scripts/csv_export.py /tmp/workouts-${STAMP}.csv`. Or directly: `python -c "import sqlite3, csv; ..."`
- **Account key not in env.** If `$AZURE_STORAGE_KEY` is empty, retrieve it at runtime: `az storage account keys list --account-name $AZURE_STORAGE_ACCOUNT --query "[0].value" -o tsv`. Export it as `AZURE_STORAGE_KEY` before the upload commands. This requires the `az` session to have access to list keys (Contributor or Owner on the storage account) — which is a lower bar than the Blob Data Contributor role needed for `--auth-mode login`.\n- **`--auth-mode login` needs Blob Data Contributor.** On this VPS, the `az login` identity has Contributor but NOT Storage Blob Data Contributor, so `--auth-mode login` fails with a permissions error even though `az account show` confirms you're logged in. Always use `--account-key $AZURE_STORAGE_KEY` (not `--auth-mode login`) for blob operations here.
- `STAMP` is captured once at the top of the run — both sqlite and csv uploads use the same timestamp. Do not recompute it inside each step or the upload names will drift.
- The container holds **both** .sqlite and .csv blobs; `restore_db.sh` filters to `.sqlite` so the CSVs don't confuse it.
- **Do not add a delete step to this skill.** Retention belongs in the lifecycle policy, not in Hermes' execution path. See [Why write-only](#why-write-only).

## Verification

```
az storage blob list \
  --account-name $AZURE_STORAGE_ACCOUNT \
  --container-name $AZURE_BACKUP_CONTAINER \
  --account-key $AZURE_STORAGE_KEY \
  --output table
```
Should show up to ~30 blobs of each type named `workouts-YYYYMMDDTHHMMSS.{sqlite,csv}` (≤60 total, capped by the 30-day Azure lifecycle policy).
To restore, run `bash scripts/restore_db.sh` from the repo root — it picks the latest `.sqlite` automatically.

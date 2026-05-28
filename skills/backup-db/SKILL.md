---
name: backup-db
description: Use when the user asks to back up the database, run a backup, or upload the workouts files to Azure Blob Storage. Uploads both the raw SQLite file and a CSV export. Also triggered by the nightly Hermes cron job.
version: 2.0.0
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
- Retention is **3 most recent blobs** per format (Pritesh prefers 3). With a nightly schedule that's 3 days of history — bump the prune `head -n -N` is the one change point if longer retention is needed.

## Procedure

Each run uploads two artifacts to the same container, both with a datetime-stamped name (`workouts-YYYYMMDDTHHMMSS.<ext>`):
- `.sqlite` — exact restore artifact, consumed by `scripts/restore_db.sh`
- `.csv` — portable export of the `workouts` table, for external tools / human eyeballing

The datetime suffix means manual runs never overwrite the scheduled nightly run.

### 0. Resolve storage key and container

Azure storage keys rotate. The key in `~/.hermes/.env` may be stale. Test it at runtime before using:

```bash
# Test if the current $AZURE_STORAGE_KEY works, or fetch a fresh one
if az storage container exists \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --name "$AZURE_BACKUP_CONTAINER" \
  --account-key "$AZURE_STORAGE_KEY" \
  --query "exists" -o tsv 2>/dev/null | grep -q true; then
  ACCT_KEY="$AZURE_STORAGE_KEY"
else
  echo "Key stale — fetching fresh key from account..."
  ACCT_KEY=$(az storage account keys list \
    --account-name "$AZURE_STORAGE_ACCOUNT" \
    --query "[0].value" -o tsv)
  if [ -z "$ACCT_KEY" ]; then
    echo "FATAL: Cannot resolve AZURE_STORAGE_KEY. Log in with 'az login' first."
    exit 1
  fi
fi
```

Then ensure the container exists (it may have been deleted during resource cleanup):

```bash
az storage container create \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --name "$AZURE_BACKUP_CONTAINER" \
  --account-key "$ACCT_KEY" \
  --public-access off 2>/dev/null || true
```

Use `$ACCT_KEY` (not `$AZURE_STORAGE_KEY`) in all subsequent blob commands.

### 1. Confirm the database exists

```
ls -lh data/workouts.sqlite
```

### 2. Dump the workouts table to CSV

```bash
STAMP=$(date +%Y%m%dT%H%M%S)
sqlite3 -header -csv data/workouts.sqlite "SELECT * FROM workouts" > "/tmp/workouts-${STAMP}.csv"
```

If `sqlite3` CLI is not installed, fall back to Python:
```bash
python -c "
import sqlite3, csv
conn = sqlite3.connect('data/workouts.sqlite')
cursor = conn.execute('SELECT * FROM workouts')
cols = [desc[0] for desc in cursor.description]
with open('/tmp/workouts-${STAMP}.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(cols); w.writerows(cursor.fetchall())
conn.close()
"
```

### 3. Upload both files to Azure Blob Storage

```bash
az storage blob upload \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --container-name "$AZURE_BACKUP_CONTAINER" \
  --name "workouts-${STAMP}.sqlite" \
  --file data/workouts.sqlite \
  --account-key "$ACCT_KEY" --overwrite

az storage blob upload \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --container-name "$AZURE_BACKUP_CONTAINER" \
  --name "workouts-${STAMP}.csv" \
  --file "/tmp/workouts-${STAMP}.csv" \
  --account-key "$ACCT_KEY" --overwrite
```

### 4. Prune to keep only the 3 most recent (retention per format)

```bash
for EXT in sqlite csv; do
  az storage blob list \
    --account-name "$AZURE_STORAGE_ACCOUNT" \
    --container-name "$AZURE_BACKUP_CONTAINER" \
    --query "sort_by([?ends_with(name, '.${EXT}')], &name)[].name" \
    --account-key "$ACCT_KEY" \
    --output tsv | head -n -3 | xargs -r -I{} \
  az storage blob delete \
    --account-name "$AZURE_STORAGE_ACCOUNT" \
    --container-name "$AZURE_BACKUP_CONTAINER" \
    --name {} --account-key "$ACCT_KEY"
done
```

### 5. Clean up local temp CSV

```bash
rm -f "/tmp/workouts-${STAMP}.csv"
```

### 6. Verify

```bash
az storage blob list \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --container-name "$AZURE_BACKUP_CONTAINER" \
  --account-key "$ACCT_KEY" \
  --output table
```

Expect ≤3 blobs of each type (≤6 total). If this is the first run, expect 1 of each.

## Required env vars

- `AZURE_STORAGE_ACCOUNT` — storage account name (set in Azure portal at provisioning time)
- `AZURE_BACKUP_CONTAINER` — container name (e.g. `workout-backups`)
- `AZURE_STORAGE_KEY` — optional if `az login` is active (step 0 falls back to `az storage account keys list`). If set, it's tested first; if stale, the fallback kicks in automatically.

Set `AZURE_STORAGE_ACCOUNT` and `AZURE_BACKUP_CONTAINER` in `~/.hermes/.env` so they're always present. The key can also be there but will be refreshed automatically if rotated.

## Provisioning

### Initial container setup

The container is created automatically as part of step 0 if it doesn't exist. No manual portal steps needed beyond ensuring the storage account exists.

## Pitfalls

- Run from the repo root so `data/workouts.sqlite` resolves correctly.
- **`sqlite3` CLI may not be installed.** This VPS has Python's `sqlite3` module but not the standalone CLI. If `sqlite3` command fails, use the Python fallback: `python /home/azureuser/exercise-tracker/skills/backup-db/scripts/csv_export.py /tmp/workouts-${STAMP}.csv`. Or directly: `python -c "import sqlite3, csv; ..."`
- **$AZURE_STORAGE_KEY in .env may be stale.** Azure storage keys rotate. Don't rely on the env var. Step 0 handles this: tests the key first, fetches a fresh one via `az storage account keys list` if auth fails. If the `az` session itself is unauthenticated, run `az login` first. The `az` identity needs Contributor or Owner on the storage account to list keys (a lower bar than Blob Data Contributor needed for `--auth-mode login`).
- **Container may be missing** due to resource cleanup (Azure trial containers aren't persistent). Step 0 recreates it. This is safe — the `create` call is idempotent and fast.
- **Script path resolution bug.** `csv_export.py` uses `dirname(dirname(__file__))` but the script lives at `skills/backup-db/scripts/csv_export.py` — that only climbs 2 levels to `skills/backup-db/`. Fixed by adding a third `dirname` to reach the repo root.
- The prune step is destructive; verify the blob list looks correct before running in a new environment.
- `STAMP` is captured once at the top of the run — sqlite, csv, and prune all use the same timestamp. Do not recompute it inside each step or the upload names will drift.
- The container holds **both** .sqlite and .csv blobs. The prune loop separates them by extension; `restore_db.sh` filters to `.sqlite` so the CSVs don't confuse it.

## Verification

```bash
az storage blob list \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --container-name "$AZURE_BACKUP_CONTAINER" \
  --account-key "$ACCT_KEY" \
  --output table
```

Expect ≤3 blobs of each type named `workouts-YYYYMMDDTHHMMSS.{sqlite,csv}` (≤6 total). First-run will show 1 of each.
To restore, run `bash scripts/restore_db.sh` from the repo root — it picks the latest `.sqlite` automatically.

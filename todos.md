# TODOs

## Data Backup & Recovery
- [ ] Schedule the backup-db skill weekly via Hermes cron instead of a standalone cron job.
- [ ] Add weekly backup job to dump the raw SQLite database (`data/workouts.sqlite`) and upload it to Azure Blob Storage.

- [ ] Keep only the last 3 backup copies in Azure Blob Storage.

- [ ] Check Garmin Connect data export for old strength training history and recover/import anything useful.


## Telegram

- [ ] Enable voice memo logging — Hermes is already the Telegram gateway

## Migration
- Move app to VS Subscriptio from 30 day trial subscription
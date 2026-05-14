# TODOs

## Data Backup & Recovery
- [ ] Schedule the backup-db skill weekly via Hermes cron instead of a standalone cron job.
- [ ] Add weekly backup job to dump the raw SQLite database (`data/workouts.sqlite`) and upload it to Azure Blob Storage.
- [ ] Keep only the last 3 backup copies in Azure Blob Storage.
- [ ] Convert SQLite to CSV format before uploading to Azure Blob for portability.


## Telegram / Chat Input

- [ ] Enable voice memo logging — Hermes is already the Telegram gateway
- [ ] Support multi-message workout logging (accumulate exercises across multiple chat messages before logging to DB)


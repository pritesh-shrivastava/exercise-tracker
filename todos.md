# TODOs

## Data Backup & Recovery
- [x] Schedule the backup-db skill nightly via Hermes cron instead of a standalone cron job. (Install command in `skills/backup-db/SKILL.md`; needs to be run once on the VPS.)
- [x] Add backup job to dump the raw SQLite database (`data/workouts.sqlite`) and upload it to Azure Blob Storage.
- [x] Keep only the last 7 backup copies in Azure Blob Storage.
- [x] Convert SQLite to CSV format before uploading to Azure Blob for portability. (Upload both .sqlite and .csv each run; prune keeps last 7 of each.)


## Telegram / Chat Input

- [ ] Enable voice memo logging — Hermes is already the Telegram gateway
- [x] Support multi-message workout logging (accumulate exercises across multiple chat messages before logging to DB)


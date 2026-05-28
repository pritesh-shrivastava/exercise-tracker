# TODOs

## Data Backup & Recovery
- [x] Schedule the backup-db skill nightly via Hermes cron instead of a standalone cron job. (Install command in `skills/backup-db/SKILL.md`; needs to be run once on the VPS.)
- [x] Add backup job to dump the raw SQLite database (`data/workouts.sqlite`) and upload it to Azure Blob Storage.
- [x] Keep only the last 7 backup copies in Azure Blob Storage. *(Superseded 2026-05-28: replaced with a 30-day Azure lifecycle policy after Hermes-executed prune logic deleted the wrong container. See `skills/backup-db/SKILL.md` "Why write-only".)*
- [x] Convert SQLite to CSV format before uploading to Azure Blob for portability. (Upload both .sqlite and .csv each run; retention now handled by Azure lifecycle policy.)


## Telegram / Chat Input

- [ ] Enable voice memo logging — Hermes is already the Telegram gateway
- [x] Support multi-message workout logging (accumulate exercises across multiple chat messages before logging to DB)


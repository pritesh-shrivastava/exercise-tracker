# TODOs

## Backup & Recovery

- [ ] Add weekly backup job to dump the raw SQLite database (`data/workouts.sqlite`) and upload it to Azure Blob Storage.
- [ ] Keep only the last 3 backup copies in Azure Blob Storage.
- [ ] Check Garmin Connect data export for old strength training history and recover/import anything useful.

## Hermes Skills

- [ ] Schedule the backup-db skill weekly via Hermes cron instead of a standalone cron job.


## Telegram

- [ ] Run `/sethome` in the Telegram chat so Hermes can send proactive messages (weekly summaries, cron outputs).
- [ ] Enable voice memo logging — Hermes is already the Telegram gateway; just set `GROQ_API_KEY` on the VPS for fast free-tier Whisper transcription via Groq.
- [ ] Generate a weekly PR report with current best set for each exercise and send it to Telegram.

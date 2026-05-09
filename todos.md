# TODOs

## Backup & Recovery

- [ ] Add weekly backup job to dump the raw SQLite database (`data/workouts.sqlite`) and upload it to Azure Blob Storage.
- [ ] Keep only the last 3 backup copies in Azure Blob Storage.
- [x] Add a restore note/script for recovering the DB from Azure Blob if the VPS dies. (`restore_db.sh`)
- [ ] Check Garmin Connect data export for old strength training history and recover/import anything useful.

## Hermes Skills

- [x] Create `skills/log-workout/SKILL.md` — teach Hermes how to log workout lines, including incline/decline bench split behavior and IST timezone assumption.
- [x] Create `skills/workout-summary/SKILL.md` — tiered summary responses: short (last 5), weekly volume by muscle group, full PRs and trends.
- [x] Create `skills/backup-db/SKILL.md` — replace the raw cron backup with a skill so Hermes can trigger it on schedule or on demand.
- [ ] Schedule the backup-db skill weekly via Hermes cron instead of a standalone cron job.

## Hermes Memory

- [ ] PR memory update is automated — weekly cron runs `pr_summary.py`, Hermes parses the output and overwrites the `## Personal Records` section in memory. No manual step needed.
- [ ] Write training preferences (Pull→Push→Legs rotation, kg not lbs, IST timezone) into Hermes memory.

## Telegram

- [ ] Run `/sethome` in the Telegram chat so Hermes can send proactive messages (weekly summaries, cron outputs).
- [ ] Voice memo support — pick one approach:
  - **Option A (recommended)**: Route Telegram through Hermes's gateway instead of the standalone `telegram_bot.py`. Voice transcription (Whisper) is built-in; set `GROQ_API_KEY` for fast free-tier cloud transcription via Groq.
  - **Option B**: Keep `telegram_bot.py` standalone — download the OGG voice file from Telegram, send to Groq/Whisper API, get transcript, pass through existing `insert_lines()` pipeline. More code, but keeps the bot independent of Hermes.
- [ ] Note: GPT-5.4 mini does not support audio input natively — transcription must happen before the model sees the message (Hermes or Groq/Whisper handle this, not the model).

# TODOs

## Data Backup & Recovery

### Backup credential hardening (post-2026-05-28 incident)
Goal: remove the standing `AZURE_STORAGE_KEY` (full storage-account power) from `~/.hermes/.env`. See `skills/backup-db/SKILL.md` "Why write-only" → "Outstanding hardening".

- [ ] **Quick safety net first:** enable container soft-delete + blob versioning on the storage account (Azure portal, no code change). Makes any accidental delete reversible within the window.
- [ ] (Optional, stronger) Enable time-based immutability / retention policy on the `workout-backups` container so blobs cannot be deleted before expiry, even by the account owner.
- [ ] Create a managed identity for the VPS (system-assigned on the Azure VM, or user-assigned if Hermes runs elsewhere).
- [ ] Grant the identity `Storage Blob Data Contributor` scoped to the `workout-backups` container only (not the whole storage account). This is the role the current `az login` identity lacks — see pitfall at `skills/backup-db/SKILL.md:144`.
- [ ] Switch the two `az storage blob upload` calls in `skills/backup-db/SKILL.md` from `--account-key $AZURE_STORAGE_KEY` to `--auth-mode login`. Update `scripts/restore_db.sh` and any other `AZURE_STORAGE_KEY` callers the same way (grep first).
- [ ] Verify the new auth path end-to-end via `hermes cron run backup-db` and a manual `bash scripts/restore_db.sh` dry run.
- [ ] Rotate (regenerate) both storage account keys in the Azure portal. This is the step that actually closes the hole — until rotation, any copy of the old key still works.
- [ ] Remove `AZURE_STORAGE_KEY` from `~/.hermes/.env` on the VPS and restart Hermes.


## Telegram / Chat Input

- [ ] Enable voice memo logging — Hermes is already the Telegram gateway

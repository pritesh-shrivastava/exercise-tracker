# TODOs

## Data Backup & Recovery

### Backup credential hardening (post-2026-05-28 incident)

- [x] Replace agent-driven backup cron with a Hermes `no-agent` script wrapper.
- [x] Move durable backup logic into repo-owned `scripts/backup_db.py`.
- [x] Remove script-side blob list/prune/delete behavior.
- [x] Replace `AZURE_STORAGE_KEY` in `~/.hermes/.env` with `AZURE_STORAGE_SAS_TOKEN`.
- [x] Use a container SAS with create/write only (`cw`, no delete/list).
- [x] Apply Azure lifecycle policy deleting `workout-backups/workouts-*` blobs after 30 days.
- [x] Verify one real backup upload with SAS auth.

Still optional hardening:

- [ ] Enable container soft-delete + blob versioning on the storage account. Makes accidental delete reversible within the window.
- [ ] Enable time-based immutability / retention policy on the `workout-backups` container so blobs cannot be deleted before expiry, even by the account owner.
- [ ] Rotate/regenerate both storage account keys in the Azure portal. `~/.hermes/.env` no longer stores the key, but rotation closes any old copies.


## Telegram / Chat Input

- [ ] Enable voice memo logging — Hermes is already the Telegram gateway

#!/usr/bin/env python3
"""Hermes cron wrapper for the repo-owned backup script.

Hermes no-agent cron requires scripts to live under ~/.hermes/scripts. Deploy
this tiny wrapper there; it executes the real implementation from this repo.
"""

from __future__ import annotations

import runpy
from pathlib import Path

BACKUP_SCRIPT = Path("/home/azureuser/exercise-tracker/scripts/backup_db.py")

if not BACKUP_SCRIPT.exists():
    raise SystemExit(f"Backup script not found: {BACKUP_SCRIPT}")

runpy.run_path(str(BACKUP_SCRIPT), run_name="__main__")

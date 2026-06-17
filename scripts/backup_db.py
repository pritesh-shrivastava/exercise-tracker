#!/usr/bin/env python3
"""Upload workout DB backups to Azure Blob Storage without pruning.

This script can run manually or from a VPS cron/systemd timer. It never lists or
deletes blobs; Azure lifecycle policy owns retention.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "workouts.sqlite"
ENV_PATH = Path.home() / ".hermes" / ".env"


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def auth_args() -> list[str]:
    sas = os.environ.get("AZURE_STORAGE_SAS_TOKEN", "").strip()
    if sas:
        return ["--sas-token", sas]

    raise RuntimeError("AZURE_STORAGE_SAS_TOKEN is required")


def export_csv(out_path: Path) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT * FROM workouts")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    return len(rows)


def upload_blob(
    *,
    account: str,
    container: str,
    blob_name: str,
    file_path: Path,
    auth: list[str],
    dry_run: bool,
) -> None:
    cmd = [
        "az",
        "storage",
        "blob",
        "upload",
        "--account-name",
        account,
        "--container-name",
        container,
        "--name",
        blob_name,
        "--file",
        str(file_path),
        "--overwrite",
        "false",
        "--only-show-errors",
        *auth,
    ]
    if dry_run:
        print("DRY RUN:", " ".join(cmd[:14] + ["...", str(file_path.name)]))
        return
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print planned blob names only")
    args = parser.parse_args()

    load_env_file()

    account = required_env("AZURE_STORAGE_ACCOUNT")
    container = required_env("AZURE_BACKUP_CONTAINER")
    auth = auth_args()

    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found: {DB_PATH}")

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    sqlite_blob = f"workouts-{stamp}.sqlite"
    csv_blob = f"workouts-{stamp}.csv"

    with tempfile.TemporaryDirectory(prefix="exercise-tracker-backup-") as tmpdir:
        csv_path = Path(tmpdir) / csv_blob
        row_count = export_csv(csv_path)

        upload_blob(
            account=account,
            container=container,
            blob_name=sqlite_blob,
            file_path=DB_PATH,
            auth=auth,
            dry_run=args.dry_run,
        )
        upload_blob(
            account=account,
            container=container,
            blob_name=csv_blob,
            file_path=csv_path,
            auth=auth,
            dry_run=args.dry_run,
        )

    mode = "DRY RUN - " if args.dry_run else ""
    print(f"{mode}Backup complete")
    print(f"account: {account}")
    print(f"container: {container}")
    print("auth: sas-token")
    print(f"rows: {row_count}")
    print(f"uploaded: {sqlite_blob}")
    print(f"uploaded: {csv_blob}")
    print("retention: Azure lifecycle policy, no script-side deletes")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

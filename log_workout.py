#!/usr/bin/env python3
"""Append pasted workouts to a local SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from tracker_core import insert_lines


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"


def main() -> int:
    parser = argparse.ArgumentParser(description="Log workout text to SQLite")
    parser.add_argument("text", nargs="*", help="Workout text. If omitted, read from stdin.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    args = parser.parse_args()

    text = "\n".join(args.text) if args.text else sys.stdin.read()
    count = insert_lines(Path(args.db), text, source="manual")
    print(f"Logged {count} workout line(s) into {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

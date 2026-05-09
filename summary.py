#!/usr/bin/env python3
"""Workout summary and PR report.

Usage:
  python summary.py       # recent activity (last 5 entries)
  python summary.py --prs # personal records by body part
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tracker.core import fetch_summary, format_summary
from tracker.reports import format_prs

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"


def main() -> int:
    parser = argparse.ArgumentParser(description="Workout summary and PR report")
    parser.add_argument("--prs", action="store_true", help="Show personal records by body part")
    args = parser.parse_args()

    if args.prs:
        if not DEFAULT_DB.exists():
            raise SystemExit(f"No database found at {DEFAULT_DB}")
        print(format_prs(DEFAULT_DB))
    else:
        print(format_summary(fetch_summary(DEFAULT_DB)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

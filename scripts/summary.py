#!/usr/bin/env python3
"""Workout summary and PR report.

Usage:
  python scripts/summary.py       # recent activity (last 5 entries)
  python scripts/summary.py --prs # personal records by body part
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tracker.core import fetch_recent_activity, format_recent_activity  # noqa: E402
from tracker.reports import format_prs_compact  # noqa: E402

DEFAULT_DB = REPO_ROOT / "data" / "workouts.sqlite"


def main() -> int:
    parser = argparse.ArgumentParser(description="Workout summary and PR report")
    parser.add_argument("--prs", action="store_true", help="Show personal records by body part")
    args = parser.parse_args()

    if args.prs:
        if not DEFAULT_DB.exists():
            raise SystemExit(f"No database found at {DEFAULT_DB}")
        print(format_prs_compact(DEFAULT_DB))
    else:
        print(format_recent_activity(fetch_recent_activity(DEFAULT_DB)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

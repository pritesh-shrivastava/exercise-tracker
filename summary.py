#!/usr/bin/env python3
"""Quick stats for the workout tracker."""

from __future__ import annotations

from pathlib import Path

from tracker_core import fetch_summary, format_summary


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"


def main() -> int:
    summary = fetch_summary(DEFAULT_DB)
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

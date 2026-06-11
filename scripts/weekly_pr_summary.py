#!/usr/bin/env python3
"""Weekly PR summary: print to stdout and update runtime Hermes memory.

Designed to be run as a cron script. Prints the PR summary to stdout
(which Hermes delivers to Telegram), and updates
~/.hermes/memories/MEMORY.md with structured PR data so the agent has fast access.
NOTE: Deployed copy at ~/.hermes/scripts/weekly_pr_summary.py
(Hermes cron sandbox requires scripts there). That copy has
BASE_DIR hardcoded - update both when DB path changes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"
MEMORY_FILE = Path.home() / ".hermes" / "memories" / "MEMORY.md"

# We import after path setup so it works without uv run
sys.path.insert(0, str(BASE_DIR))
from tracker.reports import format_prs_compact, format_stale_pr_increment_candidates  # noqa: E402


def format_for_memory(pr_text: str) -> str:
    """Convert the compact PR output into a structured memory block."""
    lines = pr_text.strip().split("\n")
    if not lines:
        return ""

    block = "## Personal Records\n\n"
    block += f"PR snapshot: {Path.home().stem}\n\n"

    for line in lines:
        # Lines start with emoji + space + exercise name
        # e.g. "🩻  Chest Press Vertical   3×10 @ 15kg      - 04 Dec 2025"
        emoji_match = re.match(r"([\U0001F300-\U0010FFFF])  (.+)", line)
        if not emoji_match:
            continue

        rest = emoji_match.group(2).strip()

        # Rest is: "Exercise  [variations]  sets×reps @ weight  date"
        # Split on 2+ spaces
        parts = re.split(r"  +", rest)
        if len(parts) >= 3:
            exercise = parts[0].strip()
            perf = parts[-2].strip() if len(parts) >= 3 else ""
            date = parts[-1].strip() if len(parts) >= 3 else ""

            # Extract variation from perf-ish part if it looks like a bracket
            variation = ""
            if len(parts) >= 4:
                variation = parts[1].strip().strip("[]")
            elif "[" in exercise:
                idx = exercise.index("[")
                variation = exercise[idx:].strip("[]")
                exercise = exercise[:idx].strip()

            block += f"- **{exercise}**"
            if variation:
                block += f" ({variation})"
            block += f": {perf} ({date})\n"

    return block


def update_memory(pr_text: str) -> bool:
    """Replace or append the ## Personal Records section in runtime memory."""
    block = format_for_memory(pr_text)
    if not block:
        return False

    memory_content = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""

    # Pattern to find existing Personal Records section
    section_pattern = re.compile(
        r"## Personal Records\n.*?(?=\n## |\Z)", re.DOTALL
    )

    if section_pattern.search(memory_content):
        memory_content = section_pattern.sub(block.rstrip("\n"), memory_content)
    else:
        memory_content = memory_content.rstrip("\n") + "\n\n" + block

    MEMORY_FILE.write_text(memory_content, encoding="utf-8")
    return True


def main() -> int:
    if not DEFAULT_DB.exists():
        print(f"No database found at {DEFAULT_DB}")
        return 1

    stale_text = format_stale_pr_increment_candidates(DEFAULT_DB)
    pr_text = format_prs_compact(DEFAULT_DB)
    if stale_text:
        print(stale_text)
        print()
        print("---")
        print()
    print(pr_text)

    # Also update memory for fast agent access
    try:
        if update_memory(pr_text):
            print("\n[memory updated]", file=sys.stderr)
    except Exception as e:
        print(f"\n[memory update failed: {e}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

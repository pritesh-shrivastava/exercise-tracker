#!/usr/bin/env python3
"""Normalize exercise names already stored in the SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from exercise_normalizer import normalize_exercise


DB = Path(__file__).resolve().parent / "data" / "workouts.sqlite"


def main() -> int:
    if not DB.exists():
        print(f"No database found at {DB}")
        return 0

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, exercise, raw_text FROM workouts ORDER BY id").fetchall()
        updates = []
        for row in rows:
            normalized = normalize_exercise(row["exercise"], row["raw_text"])
            if normalized != row["exercise"]:
                updates.append((normalized, row["id"], row["exercise"]))

        for normalized, row_id, old in updates:
            conn.execute("UPDATE workouts SET exercise = ? WHERE id = ?", (normalized, row_id))
            print(f"{row_id}: {old} -> {normalized}")
        conn.commit()

    print(f"Updated {len(updates)} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Normalize exercise names already stored in the SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tracker.core import ensure_db
from tracker.normalizer import normalize_exercise
from tracker.parser import detect_variations

DB = Path(__file__).resolve().parent.parent / "data" / "workouts.sqlite"


def main() -> int:
    if not DB.exists():
        print(f"No database found at {DB}")
        return 0

    ensure_db(DB)

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, exercise, variation, raw_text, logged_at, workout_date, workout_type, details, source"
            " FROM workouts ORDER BY id"
        ).fetchall()

        updates = []
        inserts = []
        deletes = []
        for row in rows:
            normalized = normalize_exercise(row["exercise"], row["raw_text"])
            target_variations = detect_variations(normalized, row["raw_text"] or "")

            if len(target_variations) > 1:
                deletes.append(row["id"])
                for variation in target_variations:
                    inserts.append((
                        row["logged_at"], row["workout_date"], row["workout_type"],
                        normalized, variation, row["details"], row["raw_text"], row["source"],
                    ))
                continue

            variation = target_variations[0]
            if normalized != row["exercise"] or variation != row["variation"]:
                updates.append((normalized, variation, row["id"], row["exercise"], row["variation"]))

        for normalized, variation, row_id, old_exercise, old_variation in updates:
            print(f"{row_id}: {old_exercise} [{old_variation}] -> {normalized} [{variation}]")
        conn.executemany(
            "UPDATE workouts SET exercise = ?, variation = ? WHERE id = ?",
            [(n, v, rid) for n, v, rid, *_ in updates],
        )

        for row_id in deletes:
            print(f"{row_id}: deleted combined incline/decline row")
        if deletes:
            conn.executemany("DELETE FROM workouts WHERE id = ?", [(rid,) for rid in deletes])

        if inserts:
            conn.executemany(
                "INSERT INTO workouts"
                " (logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                inserts,
            )
            for row in inserts:
                print(f"split row -> {row[3]} [{row[4]}]")

        conn.commit()

    print(f"Updated {len(updates)} row(s); deleted {len(deletes)} row(s); inserted {len(inserts)} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

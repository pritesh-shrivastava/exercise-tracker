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
        columns = {row[1] for row in conn.execute("PRAGMA table_info(workouts)")}
        if "variation" not in columns:
            conn.execute("ALTER TABLE workouts ADD COLUMN variation TEXT NOT NULL DEFAULT 'default'")
            conn.execute("UPDATE workouts SET variation = 'default' WHERE variation IS NULL OR variation = ''")

        rows = conn.execute("SELECT id, exercise, variation, raw_text, logged_at, workout_date, workout_type, details, source FROM workouts ORDER BY id").fetchall()
        updates = []
        inserts = []
        deletes = []
        for row in rows:
            normalized = normalize_exercise(row["exercise"], row["raw_text"])
            raw = (row["raw_text"] or "").lower()
            exercise_name = (row["exercise"] or "").lower()
            is_bench = "bench" in raw or "bench" in exercise_name
            if is_bench and "incline" in raw and "decline" in raw:
                if row["variation"] in {"incline", "decline"}:
                    target_variations = [row["variation"]]
                else:
                    target_variations = ["incline", "decline"]
            elif is_bench:
                if "flat" in raw:
                    target_variations = ["flat"]
                elif "incline" in raw:
                    target_variations = ["incline"]
                elif "decline" in raw:
                    target_variations = ["decline"]
                else:
                    target_variations = ["flat"]
            else:
                target_variations = ["default"]

            if len(target_variations) > 1:
                deletes.append(row["id"])
                for variation in target_variations:
                    inserts.append((row["logged_at"], row["workout_date"], row["workout_type"], normalized, variation, row["details"], row["raw_text"], row["source"]))
                continue

            variation = target_variations[0]
            if normalized != row["exercise"] or variation != row["variation"]:
                updates.append((normalized, variation, row["id"], row["exercise"], row["variation"]))

        for normalized, variation, row_id, old_exercise, old_variation in updates:
            conn.execute("UPDATE workouts SET exercise = ?, variation = ? WHERE id = ?", (normalized, variation, row_id))
            print(f"{row_id}: {old_exercise} [{old_variation}] -> {normalized} [{variation}]")

        for row_id in deletes:
            conn.execute("DELETE FROM workouts WHERE id = ?", (row_id,))
            print(f"{row_id}: deleted combined incline/decline row")

        if inserts:
            conn.executemany(
                "INSERT INTO workouts (logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                inserts,
            )
            for idx, row in enumerate(inserts, start=1):
                print(f"split row -> {row[3]} [{row[4]}]")

        conn.commit()

    print(f"Updated {len(updates)} row(s); deleted {len(deletes)} row(s); inserted {len(inserts)} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

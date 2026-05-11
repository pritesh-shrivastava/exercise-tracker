#!/usr/bin/env python3
"""Backfill sets, reps, weight_kg, equipment, per_hand columns from existing data.

Run after schema migration to populate all old rows.

For equipment inference, this matches the logic in tracker.parser.infer_equipment.
For weight_kg: converts per-hand weights to total for dumbbells.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"


def parse_sets_reps(details: str) -> tuple[int, int]:
    """Extract sets and reps from details string like '3x15 @ 5'."""
    m = re.search(r"(\d+)x(\d+)", details or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def parse_weight_str(details: str) -> float | None:
    """Extract weight from details string. Returns the stored value (may be per-hand)."""
    if not details:
        return None
    m = re.search(r"@\s*(\d+(?:\.\d+)?)", details.lower())
    if m:
        return float(m.group(1))
    return None


def infer_equipment(exercise: str, raw_text: str) -> str:
    """Match the parser.infer_equipment logic."""
    combined = f"{exercise} {raw_text}".lower()
    if "bodyweight" in combined or combined.strip().startswith("bodyweight"):
        return "bodyweight"
    if "barbell" in combined:
        return "barbell"
    if any(x in combined for x in ["dumbbell", "dumbell", "dumbbell "]):
        return "dumbbells"
    if "kettlebell" in combined or "kettle bell" in combined:
        return "kettlebell"
    if "cable" in combined:
        return "cable"
    if "machine" in combined:
        return "machine"
    if "smith" in combined:
        return "smith machine"
    if "band" in combined:
        return "band"
    return "other"


def has_plus_notation(raw_text: str) -> bool:
    """Check if the raw text explicitly uses 'X + Y' weight notation."""
    return bool(re.search(r"\d+\s*\+\s*\d+\s*kg", raw_text, re.IGNORECASE))


def is_goblet_squat(exercise: str, raw_text: str) -> bool:
    """Check if this is a goblet squat (single dumbbell)."""
    return "goblet" in (exercise + " " + raw_text).lower()


def backfill(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    columns = {row[1] for row in conn.execute("PRAGMA table_info(workouts)")}
    for col in ("sets", "reps", "weight_kg", "equipment", "per_hand"):
        if col not in columns:
            raise SystemExit(
                f"Column '{col}' not found. Run ensure_db() first to add schema columns."
            )

    rows = conn.execute(
        "SELECT id, workout_type, details, exercise, raw_text, equipment FROM workouts "
        "WHERE per_hand IS NULL"
    ).fetchall()

    if not rows:
        print("No rows need backfilling.")
        conn.close()
        return 0

    updated = 0
    for row in rows:
        if row["workout_type"] != "strength":
            conn.execute(
                "UPDATE workouts SET sets=0, reps=0, equipment=?, per_hand=0 WHERE id=?",
                (infer_equipment(row["exercise"], row["raw_text"]), row["id"]),
            )
            updated += 1
            continue

        sets, reps = parse_sets_reps(row["details"])
        weight_kg = parse_weight_str(row["details"])
        equip = row["equipment"] or infer_equipment(row["exercise"], row["raw_text"])

        is_db = equip == "dumbbells"
        per_hand = int(is_db)

        if is_db and weight_kg is not None and not is_goblet_squat(row["exercise"], row["raw_text"]):
            # Old rows stored per-hand weight — double to get total
            if not has_plus_notation(row["raw_text"]):
                # e.g. "15 kg dumbbell" → stored as 15 (per-hand), total = 30
                weight_kg = weight_kg * 2
            # For + notation (e.g. "7.5 + 7.5"): need to check if details already has the sum
            # If details shows "7.5+7.5", it was already summed to 15 (total). Keep it.
            # If details shows "@ 7.5" but raw has "7.5+7.5", old regex only captured first num.
            # In that case details shows single number, and we double it.
            # Since we use parse_weight_str on details (not raw_text), we check:
            # If raw has "+" but details doesn't contain "+", the old parser lost the second half.
            if "+" not in (row["details"] or ""):
                weight_kg = weight_kg * 2

        conn.execute(
            "UPDATE workouts SET sets=?, reps=?, weight_kg=?, equipment=?, per_hand=? WHERE id=?",
            (sets, reps, weight_kg, equip, per_hand, row["id"]),
        )
        updated += 1

    conn.commit()
    conn.close()
    return updated


def main() -> int:
    if not DEFAULT_DB.exists():
        raise SystemExit(f"No database found at {DEFAULT_DB}")
    count = backfill(DEFAULT_DB)
    print(f"Backfilled {count} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
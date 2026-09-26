"""Shared tracker helpers for storage, stats, and formatting."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tracker.exercises import EXERCISE_DEFAULT_BODY_PART, EXERCISE_DEFAULT_MOVEMENT_TYPE
from tracker.models import VALID_VARIATIONS
from tracker.reports import BODY_PART_ORDER, body_part

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT NOT NULL,
                workout_date TEXT NOT NULL,
                workout_type TEXT NOT NULL,
                exercise TEXT NOT NULL,
                variation TEXT NOT NULL DEFAULT 'default',
                details TEXT,
                raw_text TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                sets INTEGER DEFAULT 0,
                reps INTEGER DEFAULT 0,
                weight_kg REAL,
                equipment TEXT NOT NULL DEFAULT '',
                per_hand INTEGER DEFAULT 0,
                body_part TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Migrate existing tables — add missing columns
        columns = {row[1] for row in conn.execute("PRAGMA table_info(workouts)")}
        migrations = [
            ("variation", "ALTER TABLE workouts ADD COLUMN variation TEXT NOT NULL DEFAULT 'default'",
             "UPDATE workouts SET variation = 'default' WHERE variation IS NULL OR variation = ''"),
            ("sets", "ALTER TABLE workouts ADD COLUMN sets INTEGER DEFAULT 0",
             None),
            ("reps", "ALTER TABLE workouts ADD COLUMN reps INTEGER DEFAULT 0",
             None),
            ("weight_kg", "ALTER TABLE workouts ADD COLUMN weight_kg REAL",
             None),
        ]
        for col, add_sql, update_sql in migrations:
            if col not in columns:
                conn.execute(add_sql)
                if update_sql:
                    conn.execute(update_sql)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(workout_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_type ON workouts(workout_type)")

        # Exercise metadata (movement type + canonical body part)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exercise_meta (
                exercise TEXT PRIMARY KEY,
                movement_type TEXT NOT NULL,
                body_part TEXT NOT NULL DEFAULT '',
                equipment TEXT NOT NULL DEFAULT '',
                per_hand INTEGER NOT NULL DEFAULT 0,
                CHECK (movement_type IN ('compound', 'isolation')),
                CHECK (body_part = '' OR body_part IN ('Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Core')),
                CHECK (equipment IN ('', 'dumbbells', 'barbell', 'machine', 'cable', 'bodyweight', 'kettlebell', 'smith machine', 'band', 'other')),
                CHECK (per_hand IN (0, 1))
            )
            """
        )
        # Migrate existing exercise_meta tables created by older versions.
        meta_cols = {row[1] for row in conn.execute("PRAGMA table_info(exercise_meta)")}
        if "equipment" not in meta_cols:
            conn.execute("ALTER TABLE exercise_meta ADD COLUMN equipment TEXT NOT NULL DEFAULT ''")
        if "per_hand" not in meta_cols:
            conn.execute("ALTER TABLE exercise_meta ADD COLUMN per_hand INTEGER NOT NULL DEFAULT 0")
        # Seed defaults idempotently.
        # We don't delete anything (manual overrides or older exercises stay intact).
        for exercise, movement_type in EXERCISE_DEFAULT_MOVEMENT_TYPE.items():
            conn.execute(
                "INSERT OR IGNORE INTO exercise_meta (exercise, movement_type) VALUES (?, ?)",
                (exercise, movement_type),
            )
        for exercise, part in EXERCISE_DEFAULT_BODY_PART.items():
            if not part:
                continue
            conn.execute(
                "UPDATE exercise_meta SET body_part = ? WHERE exercise = ? AND (body_part IS NULL OR body_part = '')",
                (part, exercise),
            )

        # Seed equipment/per_hand from defaults.
        from tracker.exercises import EXERCISE_DEFAULT_EQUIPMENT, EXERCISE_DEFAULT_PER_HAND
        for exercise, equip in EXERCISE_DEFAULT_EQUIPMENT.items():
            if not equip:
                continue
            conn.execute(
                "UPDATE exercise_meta SET equipment = ? WHERE exercise = ? AND (equipment IS NULL OR equipment = '')",
                (equip, exercise),
            )
        for exercise in EXERCISE_DEFAULT_PER_HAND:
            conn.execute(
                "UPDATE exercise_meta SET per_hand = 1 WHERE exercise = ?",
                (exercise,),
            )
        # Classifier fallback for any remaining blanks.
        for (exercise,) in conn.execute(
            "SELECT DISTINCT exercise FROM workouts WHERE exercise NOT IN (SELECT exercise FROM exercise_meta)"
        ):
            conn.execute(
                "INSERT OR IGNORE INTO exercise_meta (exercise, movement_type, body_part) VALUES (?, 'compound', ?)",
                (exercise, body_part(exercise)),
            )
        conn.execute(
            "UPDATE exercise_meta SET body_part = ? WHERE (body_part IS NULL OR body_part = '')",
            ("",),
        )

        valid_body_parts = "', '".join(BODY_PART_ORDER)
        valid_variations = "', '".join(sorted(VALID_VARIATIONS))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exercise_meta_exercise ON exercise_meta(exercise)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exercise_meta_body_part ON exercise_meta(body_part)")
        conn.execute("DROP TRIGGER IF EXISTS workouts_validate_insert")
        conn.execute("DROP TRIGGER IF EXISTS workouts_validate_update")
        conn.execute(f"""
        CREATE TRIGGER workouts_validate_insert
        BEFORE INSERT ON workouts
        BEGIN
          SELECT CASE
            WHEN NEW.variation NOT IN ('{valid_variations}')
            THEN RAISE(ABORT, 'invalid variation')
          END;
        END
        """)
        conn.execute(f"""
        CREATE TRIGGER workouts_validate_update
        BEFORE UPDATE ON workouts
        BEGIN
          SELECT CASE
            WHEN NEW.variation NOT IN ('{valid_variations}')
            THEN RAISE(ABORT, 'invalid variation')
          END;
        END
        """)
        conn.commit()


def fetch_recent_activity(db_path: Path, recent_limit: int = 5) -> dict:
    if not db_path.exists():
        return {"exists": False}

    ensure_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        agg = conn.execute(
            "SELECT COUNT(DISTINCT workout_date) AS total_days, COUNT(*) AS total_entries,"
            " MIN(workout_date) AS date_min, MAX(workout_date) AS date_max FROM workouts"
        ).fetchone()
        if not agg or agg["total_entries"] == 0:
            return {"exists": True, "empty": True}

        type_rows = conn.execute(
            "SELECT workout_type, COUNT(*) AS cnt FROM workouts GROUP BY workout_type ORDER BY workout_type"
        ).fetchall()
        # Last N distinct dates, most recent first
        recent = conn.execute(
            "SELECT workout_date, workout_type, exercise, variation, details,"
            " sets, reps, weight_kg, equipment, per_hand, body_part, raw_text"
            " FROM workouts WHERE workout_date IN ("
            "  SELECT DISTINCT workout_date FROM workouts ORDER BY workout_date DESC LIMIT ?"
            ") ORDER BY workout_date DESC, id",
            (recent_limit,),
        ).fetchall()

    return {
        "exists": True,
        "empty": False,
        "total_days": agg["total_days"],
        "total_entries": agg["total_entries"],
        "date_min": agg["date_min"],
        "date_max": agg["date_max"],
        "type_counts": {r["workout_type"]: r["cnt"] for r in type_rows},
        "recent": [dict(r) for r in recent],
    }


def format_recent_activity(summary: dict) -> str:
    if not summary.get("exists"):
        return "No database yet."
    if summary.get("empty"):
        return "No workouts logged yet."

    lines = [
        "Workout summary",
        f"- Days trained: {summary['total_days']}",
        f"- Total entries: {summary['total_entries']}",
        f"- Date range: {summary['date_min']} to {summary['date_max']}",
        "- By type:",
    ]
    for key, value in summary["type_counts"].items():
        lines.append(f"  - {key}: {value}")

    lines.append("")
    lines.append("Recent activity:")
    # Pre-compute body-part label per date
    date_parts: dict[str, set[str]] = {}
    for row in summary["recent"]:
        date_parts.setdefault(row["workout_date"], set()).add(row_body_part(row["exercise"], row.get("body_part")))
    last_date = None
    for row in summary["recent"]:
        variation = f" [{row['variation']}]" if row.get("variation") and row["variation"] not in ("default", "") else ""
        if row["workout_date"] != last_date:
            parts = date_parts[row["workout_date"]]
            label = " / ".join(sorted(parts))
            date_label = f"\n{row['workout_date']} ({label}):"
        else:
            date_label = ""
        lines.append(f"{date_label}    {row['exercise']}{variation}")
        last_date = row["workout_date"]
    return "\n".join(lines)

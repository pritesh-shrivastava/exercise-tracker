"""Shared tracker helpers for storage, stats, and formatting."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tracker.parser import WorkoutRecord, classify_lines

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
                per_hand INTEGER DEFAULT 0
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
            ("equipment", "ALTER TABLE workouts ADD COLUMN equipment TEXT NOT NULL DEFAULT ''",
             None),
            ("per_hand", "ALTER TABLE workouts ADD COLUMN per_hand INTEGER DEFAULT 0",
             None),
        ]
        for col, add_sql, update_sql in migrations:
            if col not in columns:
                conn.execute(add_sql)
                if update_sql:
                    conn.execute(update_sql)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(workout_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workouts_type ON workouts(workout_type)")
        conn.commit()


def insert_lines(db_path: Path, text: str, source: str = "manual") -> int:
    ensure_db(db_path)
    ts = now_ist()
    now = ts.isoformat()
    workout_date = ts.date().isoformat()
    rows = []
    for rec in classify_lines(text):
        if not isinstance(rec, WorkoutRecord):
            continue
        rows.append((
            now, workout_date, rec.workout_type, rec.exercise, rec.variation,
            rec.details, rec.raw_text, source,
            rec.sets, rec.reps, rec.weight_kg, rec.equipment, rec.per_hand,
        ))

    if not rows:
        return 0

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO workouts
            (logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source,
             sets, reps, weight_kg, equipment, per_hand)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def fetch_summary(db_path: Path, recent_limit: int = 5) -> dict:
    if not db_path.exists():
        return {"exists": False}

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        agg = conn.execute(
            "SELECT COUNT(*) AS total, MIN(workout_date) AS date_min, MAX(workout_date) AS date_max FROM workouts"
        ).fetchone()
        if not agg or agg["total"] == 0:
            return {"exists": True, "empty": True}

        type_rows = conn.execute(
            "SELECT workout_type, COUNT(*) AS cnt FROM workouts GROUP BY workout_type ORDER BY workout_type"
        ).fetchall()
        recent = conn.execute(
            "SELECT workout_date, workout_type, exercise, variation, details, sets, reps, weight_kg, equipment, per_hand, raw_text"
            " FROM workouts ORDER BY id DESC LIMIT ?",
            (recent_limit,),
        ).fetchall()

    return {
        "exists": True,
        "empty": False,
        "total_entries": agg["total"],
        "date_min": agg["date_min"],
        "date_max": agg["date_max"],
        "type_counts": {r["workout_type"]: r["cnt"] for r in type_rows},
        "recent": [dict(r) for r in recent],
    }


def format_summary(summary: dict) -> str:
    if not summary.get("exists"):
        return "No database yet."
    if summary.get("empty"):
        return "No workouts logged yet."

    lines = [
        "Workout summary",
        f"- Total entries: {summary['total_entries']}",
        f"- Date range: {summary['date_min']} to {summary['date_max']}",
        "- By type:",
    ]
    for key, value in summary["type_counts"].items():
        lines.append(f"  - {key}: {value}")

    lines.append("")
    lines.append("Recent entries:")
    for row in summary["recent"]:
        variation = f" [{row['variation']}]" if row.get("variation") else ""
        details = f" — {row['details']}" if row.get("details") else ""
        equip = f" ({row['equipment']})" if row.get("equipment") and row["equipment"] != "other" else ""
        lines.append(f"- {row['workout_date']} | {row['workout_type']} | {row['exercise']}{variation}{details}{equip}")
    return "\n".join(lines)
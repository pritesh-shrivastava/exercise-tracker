"""Tests for tracker.reports — PR report generation."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from tracker.reports import _body_part, _fmt_date, _parse_weight, format_prs


def test_parse_weight_basic():
    assert _parse_weight("3x5 @ 100kg") == 100.0


def test_parse_weight_decimal():
    assert _parse_weight("3x10 @ 7.5kg") == 7.5


def test_parse_weight_sum():
    assert _parse_weight("3x15 @ 7.5+7.5 dumbbell") == 15.0


def test_parse_weight_missing():
    assert _parse_weight("3x10") == -1.0


def test_parse_weight_empty():
    assert _parse_weight("") == -1.0


@pytest.mark.parametrize("exercise,expected", [
    ("Bench Press", "Chest"),
    ("Pec Fly", "Chest"),
    ("Lat Pull Down", "Back"),
    ("Seated Row", "Back"),
    ("Shoulder Press", "Shoulders"),
    ("Lateral Raise", "Shoulders"),
    ("Rear Delt Fly", "Shoulders"),
    ("Squat", "Legs"),
    ("Leg Press", "Legs"),
    ("Calf Raise", "Legs"),
    ("Bicep Curl", "Arms"),
    ("Tricep Pushdown", "Arms"),
    ("Abs Crunch", "Core"),
    ("Plank", "Core"),
    ("Something Random", "Other"),
])
def test_body_part_classification(exercise, expected):
    assert _body_part(exercise) == expected


def test_body_part_rear_delt_not_back():
    assert _body_part("Rear Delt Fly") == "Shoulders"


def test_body_part_leg_curl_not_arms():
    assert _body_part("Leg Curl") == "Legs"


def test_fmt_date_recent_is_green():
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    result = _fmt_date(today)
    assert "🟢" in result


def test_fmt_date_old_is_red():
    result = _fmt_date("2020-01-01")
    assert "🔴" in result


def _make_db(rows: list[tuple]) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    db = Path(tmp.name)
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT, workout_date TEXT, workout_type TEXT,
                exercise TEXT, variation TEXT, details TEXT,
                raw_text TEXT, source TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO workouts (logged_at, workout_date, workout_type, exercise, variation, details, raw_text, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    return db


def test_format_prs_empty_db():
    db = _make_db([])
    result = format_prs(db)
    assert "No strength workouts" in result


def test_format_prs_shows_exercise():
    db = _make_db([
        ("2026-05-01T10:00:00", "2026-05-01", "strength", "Bench Press", "flat", "3x5 @ 80kg", "bench 3x5 @ 80kg", "manual"),
    ])
    result = format_prs(db)
    assert "Bench Press" in result
    assert "80" in result


def test_format_prs_picks_best_weight():
    db = _make_db([
        ("2026-04-01T10:00:00", "2026-04-01", "strength", "Bench Press", "flat", "3x5 @ 70kg", "bench 3x5 @ 70kg", "manual"),
        ("2026-05-01T10:00:00", "2026-05-01", "strength", "Bench Press", "flat", "3x5 @ 80kg", "bench 3x5 @ 80kg", "manual"),
    ])
    result = format_prs(db)
    assert "80" in result
    assert "70" not in result


def test_format_prs_groups_by_body_part():
    db = _make_db([
        ("2026-05-01T10:00:00", "2026-05-01", "strength", "Bench Press", "flat", "3x5 @ 80kg", "bench 3x5 @ 80kg", "manual"),
        ("2026-05-01T10:00:00", "2026-05-01", "strength", "Squat", "default", "3x5 @ 100kg", "squats 3x5 @ 100kg", "manual"),
    ])
    result = format_prs(db)
    assert "Chest" in result
    assert "Legs" in result

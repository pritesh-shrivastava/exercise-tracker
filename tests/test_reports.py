"""Tests for tracker.reports — PR report generation."""

from pathlib import Path

import pytest

from tracker.core import ensure_db, insert_lines
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
    assert "🟢" in _fmt_date(today)


def test_fmt_date_old_is_red():
    assert "🔴" in _fmt_date("2020-01-01")


def test_format_prs_empty_db(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    ensure_db(db)
    assert "No strength workouts" in format_prs(db)


def test_format_prs_shows_exercise(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "bench 3x5 @ 80kg")
    result = format_prs(db)
    assert "Bench Press" in result or "bench" in result.lower()
    assert "80" in result


def test_format_prs_picks_best_weight(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "bench 3x5 @ 70kg")
    insert_lines(db, "bench 3x5 @ 80kg")
    result = format_prs(db)
    assert "80" in result
    assert "70" not in result


def test_format_prs_groups_by_body_part(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "bench press 3x5 @ 80kg\nsquats 3x5 @ 100kg")
    result = format_prs(db)
    assert "Chest" in result
    assert "Legs" in result

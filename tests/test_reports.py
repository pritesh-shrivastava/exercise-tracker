"""Tests for tracker.reports — PR report generation."""

from pathlib import Path

import pytest

from tracker.core import ensure_db, insert_lines
from tracker.parser import classify_lines, infer_equipment
from tracker.reports import _body_part, _fmt_date, format_prs


# --- Parser structured output tests ---

def test_parser_sets_reps():
    recs = classify_lines("bench 3x5 @ 80kg")
    assert recs[0].sets == 3
    assert recs[0].reps == 5


def test_parser_weight_kg():
    recs = classify_lines("bench 3x5 @ 80kg")
    assert recs[0].weight_kg == 80.0


def test_parser_weight_decimal():
    recs = classify_lines("bench 3x10 @ 7.5kg")
    assert recs[0].weight_kg == 7.5


def test_parser_weight_sum():
    recs = classify_lines("Dumbell shrugs - 3 x 12 with 10 + 10 kg")
    assert recs[0].weight_kg == 20.0  # 10kg per dumbbell = 20 total
    assert recs[0].per_hand is True


def test_parser_weight_missing():
    recs = classify_lines("pullups 3x10")
    assert recs[0].weight_kg is None


# --- Equipment classification tests ---

@pytest.mark.parametrize("exercise,raw,expected", [
    ("Dumbbell Shoulder Press", "dumbbell press", "dumbbells"),
    ("Bodyweight Abs Crunch", "bodyweight crunch", "bodyweight"),
    ("Cable Rope Upright Row", "cable row", "cable"),
    ("Barbell Bench Press", "barbell bench", "barbell"),
    ("Chest Press Vertical", "chest press vertical", "machine"),
    ("Pec Fly", "pec fly", "machine"),
    ("Rear Delt Fly", "rear delt fly", "machine"),
    ("Leg Press", "leg press", "machine"),
    ("Face Pull", "face pull", "machine"),
    ("Bicep Curl", "bicep curl", "other"),
    ("Kettlebell Swing", "kettlebell swing", "kettlebell"),
])
def test_infer_equipment(exercise, raw, expected):
    assert infer_equipment(exercise, raw) == expected


# --- Body part classification ---

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


# --- Date formatting ---

def test_fmt_date_recent_is_green():
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    assert "🟢" in _fmt_date(today)


def test_fmt_date_old_is_red():
    assert "🔴" in _fmt_date("2020-01-01")


# --- Integration: format_prs ---

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


def test_format_prs_picks_highest_weight_from_structured(tmp_path: Path):
    """New PR logic uses weight_kg column directly, not parsed details string."""
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "bench 3x5 @ 70kg")
    insert_lines(db, "bench 3x5 @ 80kg")
    result = format_prs(db)
    assert "80" in result
    assert "70" not in result, "Lower weight should not appear in PRs"
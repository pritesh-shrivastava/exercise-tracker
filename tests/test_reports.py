"""Tests for tracker.reports — PR report generation."""

from pathlib import Path

import pytest

from tracker.core import ensure_db, insert_lines
from tracker.parser import classify_lines, infer_equipment
from tracker.reports import _fmt_date, body_part
from tracker.reports import format_prs_compact as format_prs

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
    ("Barbell Incline Press", "Chest"),
    ("Dumbbell Incline Press", "Chest"),
    ("Machine Incline Press", "Chest"),
    ("Pec Fly", "Chest"),
    ("Lat Pull Down", "Back"),
    ("Seated Row", "Back"),
    ("Shoulder Press", "Shoulders"),
    ("Lateral Raise", "Shoulders"),
    ("Rear Delt Fly", "Shoulders"),
    ("Squat", "Legs"),
    ("Leg Press", "Legs"),
    ("Calf Raise", "Legs"),
    ("Bicep Curl", "Biceps"),
    ("Barbell Curl", "Biceps"),
    ("Dumbbell Hammer Curl", "Biceps"),
    ("Reverse Curl on Cable", "Biceps"),
    ("Tricep Pushdown", "Triceps"),
    ("Cable Overhead Tricep Extension", "Triceps"),
    ("Assisted Dips", "Triceps"),
    ("Dips", "Triceps"),
    ("Abs Crunch", "Core"),
    ("Plank", "Core"),
    ("Something Random", "Other"),
    ("Face Pull", "Shoulders"),
    ("Dumbbell Shrugs", "Shoulders"),
])
def test_body_part_classification(exercise, expected):
    assert body_part(exercise) == expected


def test_body_part_rear_delt_not_back():
    assert body_part("Rear Delt Fly") == "Shoulders"


def test_body_part_leg_curl_not_biceps():
    assert body_part("Hamstring Curl") == "Legs"


# --- Date formatting ---

def test_fmt_date_recent_is_new():
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    assert "+" in _fmt_date(today)


def test_fmt_date_old_is_minus():
    assert "-" in _fmt_date("2020-01-01")


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


def test_format_prs_groups_by_body_part(tmp_path):
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "bench press 3x5 @ 80kg\nsquats 3x5 @ 100kg")
    result = format_prs(db)
    assert "🩻" in result  # Chest
    assert "🦵" in result  # Legs


def test_format_prs_picks_highest_weight_from_structured(tmp_path: Path):
    """New PR logic uses weight_kg column directly, not parsed details string."""
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "bench 3x5 @ 70kg")
    insert_lines(db, "bench 3x5 @ 80kg")
    result = format_prs(db)
    assert "80" in result
    assert "70" not in result, "Lower weight should not appear in PRs"


def test_format_prs_splits_variations_with_different_weight(tmp_path: Path):
    """Variations of one exercise with different PR weights get separate lines."""
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "Lat pull down 3x15 @ 35kg")  # default
    insert_lines(db, "Lat pull down 3x15 @ 31kg with short grip")
    result = format_prs(db)
    lat_lines = [ln for ln in result.splitlines() if "Lat Pull Down" in ln]
    assert len(lat_lines) == 2, f"expected default + short grip as separate lines, got: {lat_lines}"
    assert any("35kg" in ln and "short grip" not in ln for ln in lat_lines)
    assert any("31kg" in ln and "short grip" in ln for ln in lat_lines)


def test_format_prs_clubs_same_weight_variations(tmp_path: Path):
    """Variations sharing the same PR weight stay clubbed on one line."""
    db = tmp_path / "workouts.sqlite"
    insert_lines(db, "Lat pull down 3x15 @ 31kg with short grip")
    insert_lines(db, "Lat pull down 3x15 @ 31kg with wide grip")
    result = format_prs(db)
    lat_lines = [ln for ln in result.splitlines() if "Lat Pull Down" in ln]
    assert len(lat_lines) == 1, f"same-weight variations should club into one line, got: {lat_lines}"
    assert "short grip" in lat_lines[0] and "wide grip" in lat_lines[0]

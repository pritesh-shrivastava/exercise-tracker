"""Tests for tracker.reports — PR report generation."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from tracker.core import ensure_db
from tracker.reports import (
    _fmt_date,
    body_part,
    format_stale_pr_increment_candidates,
)
from tracker.reports import format_prs_compact as format_prs


def _insert_strength(
    db: Path,
    *,
    workout_date: str,
    exercise: str,
    details: str,
    sets: int,
    reps: int,
    weight_kg: float | None,
    variation: str = "default",
    equipment: str = "machine",
    per_hand: bool = False,
) -> None:
    ensure_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO workouts
            (logged_at, workout_date, workout_type, exercise, variation, details,
             raw_text, source, sets, reps, weight_kg, equipment, per_hand)
            VALUES (?, ?, 'strength', ?, ?, ?, ?, 'test', ?, ?, ?, ?, ?)
            """,
            (
                f"{workout_date}T00:00:00+05:30",
                workout_date,
                exercise,
                variation,
                details,
                details,
                sets,
                reps,
                weight_kg,
                equipment,
                int(per_hand),
            ),
        )
        conn.commit()

# --- Body part classification ---

@pytest.mark.parametrize("exercise,expected", [
    ("Bench Press", "Chest"),
    ("Barbell Bench Press", "Chest"),
    ("Dumbbell Incline Press", "Chest"),
    ("Machine Incline Press", "Chest"),
    ("Pec Fly", "Chest"),
    ("Lat Pull Down", "Back"),
    ("Seated Row", "Back"),
    ("Barbell Deadlift", "Back"),
    ("Shoulder Press", "Shoulders"),
    ("Lateral Raise", "Shoulders"),
    ("Rear Delt Fly", "Shoulders"),
    ("Squat", "Legs"),
    ("Leg Press", "Legs"),
    ("Calf Raise", "Legs"),
    ("Hip Thrust", "Legs"),
    ("Kettlebell Swing", "Legs"),
    ("Kettleball Swing", "Legs"),
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
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Bench Press",
        variation="flat",
        details="3x5 @ 80kg",
        sets=3,
        reps=5,
        weight_kg=80,
        equipment="dumbbells",
        per_hand=True,
    )
    result = format_prs(db)
    assert "Bench Press" in result or "bench" in result.lower()
    assert "80" in result


def test_format_prs_picks_best_weight(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Bench Press",
        details="3x5 @ 70kg",
        sets=3,
        reps=5,
        weight_kg=70,
        variation="flat",
        equipment="dumbbells",
        per_hand=True,
    )
    _insert_strength(
        db,
        workout_date="2026-01-02",
        exercise="Dumbbell Bench Press",
        details="3x5 @ 80kg",
        sets=3,
        reps=5,
        weight_kg=80,
        variation="flat",
        equipment="dumbbells",
        per_hand=True,
    )
    result = format_prs(db)
    assert "80" in result
    assert "70" not in result


def test_format_prs_groups_by_body_part(tmp_path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Bench Press",
        details="3x5 @ 80kg",
        sets=3,
        reps=5,
        weight_kg=80,
        variation="flat",
        equipment="dumbbells",
        per_hand=True,
    )
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Barbell Squat",
        details="3x5 @ 100kg",
        sets=3,
        reps=5,
        weight_kg=100,
        equipment="barbell",
    )
    result = format_prs(db)
    assert "🩻" in result  # Chest
    assert "🦵" in result  # Legs


def test_format_prs_picks_highest_weight_from_structured(tmp_path: Path):
    """New PR logic uses weight_kg column directly, not parsed details string."""
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Bench Press",
        details="3x5 @ 70kg",
        sets=3,
        reps=5,
        weight_kg=70,
        variation="flat",
        equipment="dumbbells",
        per_hand=True,
    )
    _insert_strength(
        db,
        workout_date="2026-01-02",
        exercise="Dumbbell Bench Press",
        details="3x5 @ 80kg",
        sets=3,
        reps=5,
        weight_kg=80,
        variation="flat",
        equipment="dumbbells",
        per_hand=True,
    )
    result = format_prs(db)
    assert "80" in result
    assert "70" not in result, "Lower weight should not appear in PRs"


def test_format_prs_picks_lowest_assistance_weight(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Assisted Dips",
        details="3x8 @ 40kg",
        sets=3,
        reps=8,
        weight_kg=40,
    )
    _insert_strength(
        db,
        workout_date="2026-01-02",
        exercise="Assisted Dips",
        details="2x15 @ 35kg",
        sets=2,
        reps=15,
        weight_kg=35,
    )

    result = format_prs(db)

    assert "Assisted Dips" in result
    assert "2×15 @ 35kg" in result
    assert "40kg" not in result


def test_format_prs_splits_variations_with_different_weight(tmp_path: Path):
    """Variations of one exercise with different PR weights get separate lines."""
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Lat Pull Down",
        details="3x15 @ 35kg",
        sets=3,
        reps=15,
        weight_kg=35,
    )
    _insert_strength(
        db,
        workout_date="2026-01-02",
        exercise="Lat Pull Down",
        details="3x15 @ 31kg",
        sets=3,
        reps=15,
        weight_kg=31,
        variation="short grip",
    )
    result = format_prs(db)
    lat_lines = [ln for ln in result.splitlines() if "Lat Pull Down" in ln]
    assert len(lat_lines) == 2, f"expected default + short grip as separate lines, got: {lat_lines}"
    assert any("35kg" in ln and "short grip" not in ln for ln in lat_lines)
    assert any("31kg" in ln and "short grip" in ln for ln in lat_lines)


def test_format_prs_clubs_same_weight_variations(tmp_path: Path):
    """Variations sharing the same PR weight stay clubbed on one line."""
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Lat Pull Down",
        details="3x15 @ 31kg",
        sets=3,
        reps=15,
        weight_kg=31,
        variation="short grip",
    )
    _insert_strength(
        db,
        workout_date="2026-01-02",
        exercise="Lat Pull Down",
        details="3x15 @ 31kg",
        sets=3,
        reps=15,
        weight_kg=31,
        variation="wide grip",
    )
    result = format_prs(db)
    lat_lines = [ln for ln in result.splitlines() if "Lat Pull Down" in ln]
    assert len(lat_lines) == 1, f"same-weight variations should club into one line, got: {lat_lines}"
    assert "short grip" in lat_lines[0] and "wide grip" in lat_lines[0]


def test_stale_pr_increment_candidates_include_old_weighted_15_rep_pr(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Calf Raise",
        details="3x15 @ 20kg",
        sets=3,
        reps=15,
        weight_kg=20.0,
    )

    result = format_stale_pr_increment_candidates(db, as_of=date(2026, 2, 5))

    assert "Stale PRs ready for weight increase" in result
    assert "Calf Raise" in result
    assert "3×15 @ 20kg" in result
    assert "PR: 01 Jan 2026" in result


def test_stale_pr_increment_candidates_exclude_recent_pr(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-20",
        exercise="Calf Raise",
        details="3x15 @ 20kg",
        sets=3,
        reps=15,
        weight_kg=20.0,
    )

    result = format_stale_pr_increment_candidates(db, as_of=date(2026, 2, 5))

    assert result == ""


def test_stale_pr_increment_candidates_exclude_low_rep_pr(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Tricep Pushdown",
        details="3x12 @ 25kg",
        sets=3,
        reps=12,
        weight_kg=25.0,
    )

    result = format_stale_pr_increment_candidates(db, as_of=date(2026, 2, 5))

    assert result == ""


def test_stale_pr_increment_candidates_exclude_bodyweight_pr(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Bodyweight Abs Crunch",
        details="3x20",
        sets=3,
        reps=20,
        weight_kg=None,
        equipment="bodyweight",
    )

    result = format_stale_pr_increment_candidates(db, as_of=date(2026, 2, 5))

    assert result == ""


def test_stale_pr_increment_candidates_preserve_per_hand_display(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Bench Press",
        details="3x15 @ 15kg",
        sets=3,
        reps=15,
        weight_kg=15.0,
        variation="incline",
        equipment="dumbbells",
        per_hand=True,
    )

    result = format_stale_pr_increment_candidates(db, as_of=date(2026, 2, 5))

    assert "Dumbbell Bench Press [incline]" in result
    assert "3×15 @ 15kg (7.5ea.)" in result

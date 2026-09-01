"""Tests for tracker.reports — PR report generation."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from tracker.core import ensure_db
from tracker.reports import (
    body_part,
    format_stale_pr_increment_candidates,
    format_training_advice,
    progression_series,
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
    body_part: str = "",
) -> None:
    ensure_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO workouts
            (logged_at, workout_date, workout_type, exercise, variation, details,
             raw_text, source, sets, reps, weight_kg, equipment, per_hand, body_part)
            VALUES (?, ?, 'strength', ?, ?, ?, ?, 'test', ?, ?, ?, ?, ?, ?)
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
                body_part,
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
    ("Barbell Romanian Deadlift", "Back"),
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
    ("Small Barbell Curl", "Biceps"),
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


def test_body_part_pulldown_is_back():
    assert body_part("Straight Arm Cable Pulldown") == "Back"


# --- Integration: format_prs ---

def test_format_prs_empty_db(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    ensure_db(db)
    assert "No strength workouts" in format_prs(db)


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


def test_format_prs_uses_stored_body_part_tag(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Custom Pulley Thing",
        details="3x12 @ 25kg",
        sets=3,
        reps=12,
        weight_kg=25,
        equipment="cable",
        body_part="Back",
    )

    result = format_prs(db)

    assert result.startswith("🧱")
    assert "Custom Pulley Thing" in result


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


def test_format_prs_splits_variations_even_when_same_weight(tmp_path: Path):
    """PR output always splits variations into separate lines (no collapsing)."""
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
    assert len(lat_lines) == 2, f"expected one PR line per variation, got: {lat_lines}"
    assert any("[short grip]" in ln for ln in lat_lines)
    assert any("[wide grip]" in ln for ln in lat_lines)



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

    assert "Stale PRs ready for progression" in result
    assert "Calf Raise" in result
    assert "3×15 @ 20kg" in result
    assert "add weight" in result
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


def test_stale_pr_increment_candidates_include_old_weighted_under_12_rep_pr(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Tricep Pushdown",
        details="3x11 @ 25kg",
        sets=3,
        reps=11,
        weight_kg=25.0,
    )

    result = format_stale_pr_increment_candidates(db, as_of=date(2026, 2, 5))

    assert "Tricep Pushdown" in result
    assert "3×11 @ 25kg" in result
    assert "add reps" in result


def test_stale_pr_increment_candidates_exclude_middle_rep_pr(tmp_path: Path):
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


def test_training_advice_empty_db(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    ensure_db(db)

    result = format_training_advice(db, as_of=date(2026, 2, 5))

    assert result == "No strength workouts logged yet."


def test_training_advice_suggests_stale_or_untrained_focus(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Bench Press",
        details="3x10 @ 30kg",
        sets=3,
        reps=10,
        weight_kg=30.0,
        equipment="dumbbells",
        per_hand=True,
    )
    _insert_strength(
        db,
        workout_date="2026-02-04",
        exercise="Lat Pull Down",
        details="3x12 @ 35kg",
        sets=3,
        reps=12,
        weight_kg=35.0,
    )

    result = format_training_advice(db, as_of=date(2026, 2, 5))

    assert "Training coach" in result
    assert "- As of: 2026-02-05" in result
    assert "- Legs: no logged strength work yet" in result
    assert "- Chest:" not in result
    assert "Use this as advisory only" in result


def test_training_advice_includes_progression_candidates_for_next_area_only(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Shoulder Press",
        details="3x15 @ 20kg",
        sets=3,
        reps=15,
        weight_kg=20.0,
    )
    _insert_strength(
        db,
        workout_date="2026-01-01",
        exercise="Dumbbell Bench Press",
        details="3x15 @ 30kg",
        sets=3,
        reps=15,
        weight_kg=30.0,
    )
    _insert_strength(
        db,
        workout_date="2026-02-04",
        exercise="Calf Raise",
        details="3x10 @ 25kg",
        sets=3,
        reps=10,
        weight_kg=25.0,
    )

    result = format_training_advice(db, as_of=date(2026, 2, 5))

    assert "- Shoulders & Abs:" in result
    assert "Progression prompts:" in result
    assert "Dumbbell Shoulder Press" in result
    assert "3×15 @ 20kg" in result
    assert "Dumbbell Bench Press" not in result


def test_training_advice_prefers_area_whose_most_recent_part_is_staler(tmp_path: Path):
    """Regression: avoid picking an area just because one paired part is very stale.

    Scenario (as_of=2026-09-01):
      Chest=1, Triceps=1
      Shoulders=3, Core=10
      Back=8, Biceps=8
      Legs=6
    Expect: Back & Biceps (min-days-since=8) beats Shoulders & Abs (min=3).
    """
    db = tmp_path / "workouts.sqlite"

    # Chest & Triceps: last trained 1 day ago
    _insert_strength(db, workout_date="2026-08-31", exercise="Dumbbell Bench Press", details="3x10 @ 30kg", sets=3, reps=10, weight_kg=30.0, body_part="Chest")
    _insert_strength(db, workout_date="2026-08-31", exercise="Tricep Pushdown", details="3x12 @ 25kg", sets=3, reps=12, weight_kg=25.0, body_part="Triceps")

    # Shoulders & Abs: shoulders 3 days ago, core 10 days ago
    _insert_strength(db, workout_date="2026-08-29", exercise="Dumbbell Shoulder Press", details="3x12 @ 20kg", sets=3, reps=12, weight_kg=20.0, body_part="Shoulders")
    _insert_strength(db, workout_date="2026-08-22", exercise="Abs Crunch", details="3x15", sets=3, reps=15, weight_kg=None, equipment="bodyweight", body_part="Core")

    # Back & Biceps: both 8 days ago
    _insert_strength(db, workout_date="2026-08-24", exercise="Lat Pull Down", details="3x12 @ 35kg", sets=3, reps=12, weight_kg=35.0, body_part="Back")
    _insert_strength(db, workout_date="2026-08-24", exercise="Dumbbell Bicep Curl", details="3x12 @ 15kg", sets=3, reps=12, weight_kg=15.0, body_part="Biceps")

    # Legs: 6 days ago
    _insert_strength(db, workout_date="2026-08-26", exercise="Calf Raise", details="3x12 @ 25kg", sets=3, reps=12, weight_kg=25.0, body_part="Legs")

    result = format_training_advice(db, as_of=date(2026, 9, 1))

    assert "Suggested next focus:" in result
    assert "- Back & Biceps:" in result


def test_training_advice_caps_progression_candidates_at_six(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    for idx, exercise in enumerate(
        [
            "Machine Shoulder Press",
            "Dumbbell Shoulder Press",
            "Arnold Press",
            "Lateral Raise",
            "Front Raise",
            "Rear Delt Fly",
            "Face Pull",
        ],
        start=1,
    ):
        _insert_strength(
            db,
            workout_date="2026-01-01",
            exercise=exercise,
            details=f"3x15 @ {idx}kg",
            sets=3,
            reps=15,
            weight_kg=float(idx),
        )
    _insert_strength(
        db,
        workout_date="2026-02-04",
        exercise="Calf Raise",
        details="3x10 @ 25kg",
        sets=3,
        reps=10,
        weight_kg=25.0,
    )

    result = format_training_advice(db, as_of=date(2026, 2, 5))
    prompt_lines = [
        line
        for line in result.splitlines()
        if line.startswith("- ") and " — " in line
    ]

    assert len(prompt_lines) == 6
    assert any("Arnold Press" in line for line in prompt_lines)
    assert all("Rear Delt Fly" not in line for line in prompt_lines)


def test_progression_series_excludes_two_weighted_entries(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    for day, weight in enumerate((20.0, 22.5), start=1):
        _insert_strength(
            db,
            workout_date=f"2026-01-0{day}",
            exercise="Lat Pull Down",
            details=f"3x12 @ {weight}kg",
            sets=3,
            reps=12,
            weight_kg=weight,
        )

    assert progression_series(db) == []


def test_progression_series_includes_three_weighted_entries(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    for day, weight in enumerate((20.0, 22.5, 25.0), start=1):
        _insert_strength(
            db,
            workout_date=f"2026-01-0{day}",
            exercise="Seated Cable Row",
            details=f"3x12 @ {weight}kg",
            sets=3,
            reps=12,
            weight_kg=weight,
        )

    series = progression_series(db)

    assert len(series) == 1
    assert series[0].exercise == "Seated Cable Row"
    assert [point.weight_kg for point in series[0].points] == [20.0, 22.5, 25.0]


def test_progression_series_ignores_null_weights_for_threshold(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    for day, weight in enumerate((20.0, 22.5), start=1):
        _insert_strength(
            db,
            workout_date=f"2026-01-0{day}",
            exercise="Pec Fly",
            details=f"3x12 @ {weight}kg",
            sets=3,
            reps=12,
            weight_kg=weight,
        )
    _insert_strength(
        db,
        workout_date="2026-01-04",
        exercise="Pec Fly",
        details="3x12",
        sets=3,
        reps=12,
        weight_kg=None,
    )

    assert progression_series(db) == []


def test_progression_series_keeps_variations_separate(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    for day, weight in enumerate((20.0, 22.5), start=1):
        _insert_strength(
            db,
            workout_date=f"2026-01-0{day}",
            exercise="Lat Pull Down",
            variation="short grip",
            details=f"3x12 @ {weight}kg",
            sets=3,
            reps=12,
            weight_kg=weight,
        )
    for day, weight in enumerate((30.0, 32.5, 35.0), start=1):
        _insert_strength(
            db,
            workout_date=f"2026-01-0{day}",
            exercise="Lat Pull Down",
            variation="wide grip",
            details=f"3x12 @ {weight}kg",
            sets=3,
            reps=12,
            weight_kg=weight,
        )

    series = progression_series(db)

    assert len(series) == 1
    assert series[0].variation == "wide grip"


def test_progression_series_orders_by_body_part(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    rows = (
        ("Lat Pull Down", "Back", 30.0),
        ("Dumbbell Bench Press", "Chest", 20.0),
        ("Seated Abs Crunch Machine", "Core", 40.0),
    )
    for exercise, part, base_weight in rows:
        for day, increment in enumerate((0.0, 2.5, 5.0), start=1):
            _insert_strength(
                db,
                workout_date=f"2026-01-0{day}",
                exercise=exercise,
                details=f"3x12 @ {base_weight + increment}kg",
                sets=3,
                reps=12,
                weight_kg=base_weight + increment,
                body_part=part,
            )

    series = progression_series(db)

    assert [(item.part, item.exercise) for item in series] == [
        ("Chest", "Dumbbell Bench Press"),
        ("Back", "Lat Pull Down"),
        ("Core", "Seated Abs Crunch Machine"),
    ]


def test_progression_series_tracks_pr_increases(tmp_path: Path):
    db = tmp_path / "workouts.sqlite"
    for day, weight in enumerate((20.0, 25.0, 22.5, 27.5), start=1):
        _insert_strength(
            db,
            workout_date=f"2026-01-0{day}",
            exercise="Small Barbell Curl",
            details=f"3x12 @ {weight}kg",
            sets=3,
            reps=12,
            weight_kg=weight,
        )

    series = progression_series(db)

    assert series[0].exercise == "Small Barbell Curl"
    assert [point.weight_kg for point in series[0].pr_points] == [20.0, 25.0, 27.5]

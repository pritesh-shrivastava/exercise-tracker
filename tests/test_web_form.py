"""Tests for the small workout web form helpers."""

import sqlite3
from pathlib import Path

from scripts.web_form import (
    FormRow,
    _parse_form_submission,
    _rows_from_post,
    consume_form_token,
    delete_form_row,
    form_row_from_values,
    insert_form_rows,
    new_form_token,
    normalize_bind_host,
    render_log_page,
    render_prs_page,
    render_recent_page,
    update_form_row,
)
from tracker.core import ensure_db


def test_form_row_normalizes_aliases() -> None:
    row = form_row_from_values({
        "workout_date": "2026-06-16",
        "exercise": "sumo squats",
        "variation": "default",
        "sets": "2",
        "reps": "15",
        "weight_kg": "10",
        "equipment": "other",
    })

    assert row.exercise == "Sumo Squat"
    assert row.weight_kg == 10.0


def test_form_row_applies_default_equipment() -> None:
    row = form_row_from_values({
        "workout_date": "2026-06-16",
        "exercise": "Kettleball swing",
        "variation": "default",
        "sets": "3",
        "reps": "15",
        "weight_kg": "12",
    })

    assert row.exercise == "Kettlebell Swing"
    assert row.equipment == "kettlebell"


def test_form_row_supports_deadlift() -> None:
    row = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "deadlift",
        "variation": "default",
        "sets": "3",
        "reps": "12",
        "weight_kg": "20",
    })

    assert row.exercise == "Barbell Deadlift"
    assert row.equipment == "barbell"


def test_form_row_defaults_per_hand_for_selected_dumbbell_exercises() -> None:
    row = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "Dumbbell Bench Press",
        "variation": "flat",
        "sets": "3",
        "reps": "12",
        "weight_kg": "20",
        "per_hand_defaulted": "1",
    })
    lunge = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "Weighted Lunge",
        "variation": "default",
        "sets": "3",
        "reps": "12",
        "weight_kg": "20",
        "equipment": "dumbbells",
        "per_hand_defaulted": "1",
    })

    assert row.per_hand is True
    assert lunge.per_hand is True


def test_form_row_allows_unchecking_default_per_hand() -> None:
    row = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "Dumbbell Overhead Tricep Extension",
        "variation": "default",
        "sets": "3",
        "reps": "12",
        "weight_kg": "10",
        "per_hand_defaulted": "0",
    })

    assert row.per_hand is False


def test_form_row_maps_barbell_incline_to_bench_variation() -> None:
    row = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "barbell incline press",
        "variation": "default",
        "sets": "3",
        "reps": "12",
        "weight_kg": "20",
    })

    assert row.exercise == "Barbell Bench Press"
    assert row.variation == "incline"
    assert row.equipment == "barbell"


def test_form_row_merges_plain_curl_names() -> None:
    hammer = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "hammer curl",
        "variation": "default",
        "sets": "3",
        "reps": "12",
        "weight_kg": "10",
    })
    preacher = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "preacher curl",
        "variation": "default",
        "sets": "3",
        "reps": "12",
        "weight_kg": "10",
    })

    assert hammer.exercise == "Dumbbell Hammer Curl"
    assert hammer.equipment == "dumbbells"
    assert preacher.exercise == "Bicep Preacher Curl"
    assert preacher.equipment == "machine"


def test_form_row_uses_custom_exercise_when_present() -> None:
    row = form_row_from_values({
        "workout_date": "2026-06-19",
        "exercise": "Bodyweight Squat",
        "custom_exercise": "sled push",
        "variation": "default",
        "sets": "4",
        "reps": "20",
        "weight_kg": "60",
        "equipment": "machine",
    })

    assert row.exercise == "Sled Push"
    assert row.equipment == "machine"


def test_log_page_uses_grouped_exercise_select() -> None:
    html = render_log_page()

    assert 'name="workout_date"' in html
    assert 'name="body_focus"' in html
    assert 'value="Back,Biceps"' in html
    assert 'value="Chest,Triceps"' in html
    assert 'value="Shoulders,Core"' in html
    assert html.count("<legend>Row ") == 6
    assert 'name="r1_workout_date"' not in html
    assert 'name="r6_exercise"' in html
    assert 'name="r6_custom_exercise"' in html
    assert 'name="r1_sets" value="3"' in html
    assert 'name="r1_reps" value="12"' in html
    assert '<optgroup label="Legs" data-original-index=' in html
    assert '<optgroup label="Recent">' not in html
    assert '<optgroup label="Arms">' not in html
    assert '<optgroup label="Biceps" data-original-index=' in html
    assert '<optgroup label="Triceps" data-original-index=' in html
    assert '<optgroup label="Back" data-original-index=' in html
    assert 'value="Barbell Deadlift" data-equipment="barbell"' in html
    assert 'value="Dumbbell Bench Press" data-equipment="dumbbells" data-per-hand="1"' in html
    assert 'value="Weighted Lunge" data-equipment="dumbbells" data-per-hand="1"' in html
    assert 'value="Goblet Squat" data-equipment="" data-per-hand="0"' in html
    assert 'value="Barbell Incline Press"' not in html
    assert 'value="Bodyweight Squat" data-equipment="bodyweight"' in html
    assert 'value="Kettlebell Swing" data-equipment="kettlebell"' in html
    assert "data-exercise-select" in html
    assert 'value="Hammer Curl"' not in html
    assert 'value="Preacher Curl"' not in html


def test_arm_exercises_are_split_by_biceps_and_triceps() -> None:
    html = render_log_page()
    biceps_group = html.split('<optgroup label="Biceps" data-original-index="3">', 1)[1].split("</optgroup>", 1)[0]
    triceps_group = html.split('<optgroup label="Triceps" data-original-index="4">', 1)[1].split("</optgroup>", 1)[0]

    assert "Dumbbell Hammer Curl" in biceps_group
    assert "Bicep Preacher Curl" in biceps_group
    assert "Reverse Curl on Cable" in biceps_group
    assert "Tricep Pushdown" not in biceps_group
    assert "Tricep Pushdown" in triceps_group
    assert "Assisted Dips" in triceps_group
    assert "Dumbbell Hammer Curl" not in triceps_group


def test_deadlift_is_in_back_group() -> None:
    html = render_log_page()
    back_group = html.split('<optgroup label="Back" data-original-index="1">', 1)[1].split("</optgroup>", 1)[0]
    legs_group = html.split('<optgroup label="Legs" data-original-index="5">', 1)[1].split("</optgroup>", 1)[0]

    assert "Barbell Deadlift" in back_group
    assert "Barbell Deadlift" not in legs_group


def test_post_rows_use_shared_workout_date() -> None:
    rows = _rows_from_post({
        "workout_date": ["2026-06-18"],
        "r1_exercise": ["Bodyweight Squat"],
        "r1_variation": ["default"],
        "r1_sets": ["3"],
        "r1_reps": ["25"],
        "r1_weight_kg": [""],
        "r1_equipment": ["bodyweight"],
        "r6_exercise": ["deadlift"],
        "r6_variation": ["default"],
        "r6_sets": ["3"],
        "r6_reps": ["12"],
        "r6_weight_kg": ["20"],
        "r6_equipment": [""],
    })

    assert [row.workout_date for row in rows] == ["2026-06-18", "2026-06-18"]
    assert rows[1].exercise == "Barbell Deadlift"


def test_post_rows_accept_custom_exercise_without_dropdown_choice() -> None:
    rows = _rows_from_post({
        "workout_date": ["2026-06-18"],
        "r1_custom_exercise": ["sled push"],
        "r1_variation": ["default"],
        "r1_sets": ["4"],
        "r1_reps": ["20"],
        "r1_weight_kg": ["60"],
        "r1_equipment": ["machine"],
    })

    assert len(rows) == 1
    assert rows[0].exercise == "Sled Push"


def test_form_submission_keeps_valid_rows_when_another_row_is_invalid() -> None:
    submission = _parse_form_submission({
        "workout_date": ["2026-06-18"],
        "body_focus": ["Legs"],
        "r1_exercise": ["Bodyweight Squat"],
        "r1_variation": ["default"],
        "r1_sets": ["3"],
        "r1_reps": ["25"],
        "r1_weight_kg": [""],
        "r1_equipment": ["bodyweight"],
        "r2_exercise": ["Hamstring Curl"],
        "r2_variation": ["default"],
        "r2_sets": ["three"],
        "r2_reps": ["12"],
        "r2_weight_kg": ["20"],
        "r2_equipment": ["machine"],
    })

    assert [row.exercise for row in submission.rows] == ["Bodyweight Squat"]
    assert len(submission.invalid_rows) == 1
    assert submission.invalid_rows[0].values["exercise"] == "Hamstring Curl"
    assert submission.invalid_rows[0].values["sets"] == "three"
    assert submission.invalid_rows[0].error == "Row 2: sets must be a whole number"
    assert submission.workout_date == "2026-06-18"
    assert submission.body_focus == "Legs"


def test_partial_submission_inserts_valid_rows_and_renders_only_failed_rows(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    submission = _parse_form_submission({
        "workout_date": ["2026-06-18"],
        "r1_exercise": ["Bodyweight Squat"],
        "r1_variation": ["default"],
        "r1_sets": ["3"],
        "r1_reps": ["25"],
        "r1_weight_kg": [""],
        "r1_equipment": ["bodyweight"],
        "r2_exercise": ["Hamstring Curl"],
        "r2_variation": ["default"],
        "r2_sets": ["bad"],
        "r2_reps": ["12"],
        "r2_weight_kg": ["20"],
        "r2_equipment": ["machine"],
    })

    saved = insert_form_rows(db, submission.rows)
    html = render_log_page(
        saved=saved,
        error="Fix the failed row.",
        invalid_rows=submission.invalid_rows,
        workout_date=submission.workout_date,
    )

    with sqlite3.connect(db) as conn:
        exercises = [row[0] for row in conn.execute("SELECT exercise FROM workouts")]
    assert exercises == ["Bodyweight Squat"]
    assert "Saved 1 valid row(s)" in html
    assert html.count("<legend>Failed row ") == 1
    assert 'value="Hamstring Curl"' in html
    assert 'name="r1_sets" value="bad"' in html
    assert html.count("<legend>Row ") == 0


def test_insert_form_rows_re_reads_inserted_rows(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    rows = insert_form_rows(db, [
        FormRow(
            workout_date="2026-06-16",
            exercise="Hip Thrust",
            variation="default",
            sets=3,
            reps=15,
            weight_kg=20.0,
            equipment="other",
            per_hand=False,
        )
    ])

    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["exercise"] == "Hip Thrust"
    assert rows[0]["details"] == "3x15 @ 20kg"


def test_update_form_row_re_reads_exact_row(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    saved = insert_form_rows(db, [
        FormRow(
            workout_date="2026-06-16",
            exercise="Sumo Squat",
            variation="default",
            sets=2,
            reps=15,
            weight_kg=10.0,
            equipment="other",
            per_hand=False,
        )
    ])

    updated = update_form_row(
        db,
        saved[0]["id"],
        FormRow(
            workout_date="2026-06-16",
            exercise="Sumo Squat",
            variation="default",
            sets=1,
            reps=12,
            weight_kg=12.0,
            equipment="other",
            per_hand=False,
        ),
    )

    assert updated["id"] == saved[0]["id"]
    assert updated["sets"] == 1
    assert updated["reps"] == 12
    assert updated["weight_kg"] == 12.0
    assert updated["details"] == "1x12 @ 12kg"


def test_delete_form_row_returns_deleted_row(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    saved = insert_form_rows(db, [
        FormRow(
            workout_date="2026-06-16",
            exercise="Hip Thrust",
            variation="default",
            sets=3,
            reps=15,
            weight_kg=20.0,
            equipment="other",
            per_hand=False,
        )
    ])

    deleted = delete_form_row(db, saved[0]["id"])

    assert deleted["id"] == saved[0]["id"]
    assert deleted["exercise"] == "Hip Thrust"
    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM workouts WHERE id = ?", (saved[0]["id"],)).fetchone()[0]
    assert count == 0


def test_form_token_is_single_use() -> None:
    token = new_form_token()

    consume_form_token(token)

    try:
        consume_form_token(token)
    except ValueError as exc:
        assert "already submitted" in str(exc)
    else:
        raise AssertionError("token should not be reusable")


def test_empty_bind_host_is_rejected() -> None:
    try:
        normalize_bind_host("  ")
    except ValueError as exc:
        assert "--host resolved to an empty value" in str(exc)
    else:
        raise AssertionError("empty host should be rejected")


def test_render_prs_page_uses_report_path(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    ensure_db(db)
    insert_form_rows(db, [
        FormRow(
            workout_date="2026-06-16",
            exercise="Bodyweight Calf Raise",
            variation="default",
            sets=3,
            reps=20,
            weight_kg=None,
            equipment="bodyweight",
            per_hand=False,
        )
    ])

    html = render_prs_page(db)

    assert "<table>" in html
    assert "<pre>" not in html
    assert "<h2>Legs</h2>" in html
    assert "Bodyweight Calf Raise" in html
    assert "3×20" in html


def test_render_prs_page_filters_by_body_part(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    ensure_db(db)
    insert_form_rows(db, [
        FormRow(
            workout_date="2026-06-16",
            exercise="Bodyweight Calf Raise",
            variation="default",
            sets=3,
            reps=20,
            weight_kg=None,
            equipment="bodyweight",
            per_hand=False,
        ),
        FormRow(
            workout_date="2026-06-16",
            exercise="Dumbbell Bench Press",
            variation="flat",
            sets=3,
            reps=12,
            weight_kg=20.0,
            equipment="dumbbells",
            per_hand=True,
        ),
    ])

    html = render_prs_page(db, selected_part="Chest")

    assert '<select name="part"' in html
    assert 'value="Chest" selected' in html
    assert "<h2>Chest</h2>" in html
    assert "<h2>Legs</h2>" not in html
    assert "Dumbbell Bench Press" in html
    assert "Bodyweight Calf Raise" not in html


def test_render_prs_page_marks_stale_and_fresh_dates(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    ensure_db(db)
    insert_form_rows(db, [
        FormRow(
            workout_date="2026-06-18",
            exercise="Lat Pull Down",
            variation="default",
            sets=3,
            reps=12,
            weight_kg=36.0,
            equipment="machine",
            per_hand=False,
        ),
        FormRow(
            workout_date="2026-04-01",
            exercise="Dumbbell Bench Press",
            variation="flat",
            sets=3,
            reps=12,
            weight_kg=20.0,
            equipment="dumbbells",
            per_hand=True,
        ),
    ])

    html = render_prs_page(db)

    assert "pr-date-fresh" in html
    assert "pr-date-stale" in html


def test_render_recent_page_shows_last_10_without_ids(tmp_path: Path) -> None:
    db = tmp_path / "workouts.sqlite"
    for idx in range(12):
        insert_form_rows(db, [
            FormRow(
                workout_date="2026-06-16",
                exercise=f"Test Exercise {idx}",
                variation="default",
                sets=3,
                reps=12,
                weight_kg=float(idx),
                equipment="other",
                per_hand=False,
            )
        ])

    html = render_recent_page(db)

    assert "<h1>Recent</h1>" in html
    assert "<th>ID</th>" not in html
    assert "Test Exercise 11" in html
    assert "Test Exercise 2" in html
    assert "Test Exercise 0" not in html

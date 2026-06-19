"""Tests for the small workout web form helpers."""

import sqlite3
from pathlib import Path

from scripts.web_form import (
    FormRow,
    consume_form_token,
    delete_form_row,
    form_row_from_values,
    insert_form_rows,
    new_form_token,
    normalize_bind_host,
    render_log_page,
    render_prs_page,
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


def test_log_page_uses_grouped_exercise_select() -> None:
    html = render_log_page()

    assert '<optgroup label="Legs">' in html
    assert 'value="Bodyweight Squat" data-equipment="bodyweight"' in html
    assert 'value="Kettlebell Swing" data-equipment="kettlebell"' in html
    assert "data-exercise-select" in html


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

    assert "Bodyweight Calf Raise" in html
    assert "3×20" in html

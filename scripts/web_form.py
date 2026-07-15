#!/usr/bin/env python3
"""Small mobile web form for logging workouts.

No external runtime dependencies: this uses Python's stdlib HTTP server and the
existing tracker modules.
"""

from __future__ import annotations

import argparse
import html
import secrets
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tracker.core import ensure_db, now_ist  # noqa: E402
from tracker.models import (  # noqa: E402
    BODY_PART_VALUES,
    EQUIPMENT_VALUES,
    VALID_VARIATIONS,
    WorkoutRecord,
    format_details,
    validate_record,
)
from tracker.normalizer import normalize_exercise  # noqa: E402
from tracker.reports import (  # noqa: E402
    BODY_PART_ORDER,
    ProgressionPoint,
    ProgressionSeries,
    pr_display_rows,
    progression_series,
    row_body_part,
)

DEFAULT_DB = REPO_ROOT / "data" / "workouts.sqlite"
FORM_TOKENS: set[str] = set()

EXERCISE_GROUPS = {
    "Chest": [
        "Barbell Bench Press",
        "Dumbbell Bench Press",
        "Dumbbell Pec Fly",
        "Pec Fly",
        "Push Up",
        "Vertical Chest Press Machine",
    ],
    "Back": [
        "45 Degree T Bar Row",
        "Assisted Pull Up",
        "Back Extension",
        "Barbell Deadlift",
        "Chest Supported Rows",
        "Compound Row Machine",
        "Dumbbell Rows",
        "Dumbbell Romanian Deadlift",
        "Lat Pull Down",
        "Pull Up",
        "Seated Cable Row",
        "Single Arm Dumbbell Row",
        "Straight Arm Cable Pulldown",
    ],
    "Shoulders": [
        "Cable Rope Upright Row",
        "Dumbbell Arnold Press",
        "Dumbbell Shoulder Press",
        "Dumbbell Shrugs",
        "Face Pull",
        "Front Raise",
        "Lateral Raise",
        "Rear Delt Fly",
    ],
    "Biceps": [
        "Small Barbell Curl",
        "Bicep Curl on Cable",
        "Bicep Preacher Curl",
        "Chin Up",
        "Dumbbell Bicep Curl",
        "Dumbbell Hammer Curl",
        "Hammer Curl on Cable",
        "Reverse Curl on Cable",
    ],
    "Triceps": [
        "Assisted Dips",
        "Cable Overhead Tricep Extension",
        "Dumbbell Overhead Tricep Extension",
        "Tricep Pushdown",
    ],
    "Legs": [
        "45 Degree Leg Press",
        "Barbell Squat",
        "Bodyweight Calf Raise",
        "Bodyweight Squat",
        "Bulgarian Split Squat",
        "Calf Raise",
        "Glute Kickback Machine",
        "Goblet Squat",
        "Hamstring Curl",
        "Hip Abduction Machine",
        "Hip Thrust",
        "Horizontal Leg Press",
        "Kettlebell Swing",
        "Leg Extension",
        "Sumo Squat",
        "Weighted Lunge",
    ],
    "Core": [
        "Bodyweight Abs Crunch",
        "Decline Bench Situp",
        "Leg Raise",
        "Plank Oblique Crunch",
        "Seated Abs Crunch Machine",
        "Situps",
    ],
}

EXERCISE_DEFAULT_EQUIPMENT = {
    "45 Degree Leg Press": "machine",
    "45 Degree T Bar Row": "machine",
    "Assisted Dips": "machine",
    "Assisted Pull Up": "machine",
    "Barbell Bench Press": "barbell",
    "Small Barbell Curl": "barbell",
    "Barbell Deadlift": "barbell",
    "Barbell Squat": "barbell",
    "Back Extension": "bodyweight",
    "Bicep Curl on Cable": "cable",
    "Bicep Preacher Curl": "machine",
    "Bodyweight Abs Crunch": "bodyweight",
    "Bodyweight Calf Raise": "bodyweight",
    "Bodyweight Squat": "bodyweight",
    "Bulgarian Split Squat": "dumbbells",
    "Cable Overhead Tricep Extension": "cable",
    "Cable Rope Upright Row": "cable",
    "Calf Raise": "machine",
    "Chest Supported Rows": "machine",
    "Chin Up": "bodyweight",
    "Compound Row Machine": "machine",
    "Dumbbell Arnold Press": "dumbbells",
    "Dumbbell Bench Press": "dumbbells",
    "Dumbbell Bicep Curl": "dumbbells",
    "Dumbbell Hammer Curl": "dumbbells",
    "Dumbbell Overhead Tricep Extension": "dumbbells",
    "Dumbbell Pec Fly": "dumbbells",
    "Dumbbell Romanian Deadlift": "dumbbells",
    "Dumbbell Rows": "dumbbells",
    "Dumbbell Shoulder Press": "dumbbells",
    "Dumbbell Shrugs": "dumbbells",
    "Decline Bench Situp": "bodyweight",
    "Face Pull": "cable",
    "Front Raise": "dumbbells",
    "Glute Kickback Machine": "machine",
    "Goblet Squat": "dumbbells",
    "Hamstring Curl": "machine",
    "Hammer Curl on Cable": "cable",
    "Hip Abduction Machine": "machine",
    "Hip Thrust": "other",
    "Horizontal Leg Press": "machine",
    "Kettlebell Swing": "kettlebell",
    "Lat Pull Down": "machine",
    "Lateral Raise": "dumbbells",
    "Leg Extension": "machine",
    "Leg Raise": "bodyweight",
    "Pec Fly": "machine",
    "Plank Oblique Crunch": "bodyweight",
    "Pull Up": "bodyweight",
    "Push Up": "bodyweight",
    "Rear Delt Fly": "machine",
    "Reverse Curl on Cable": "cable",
    "Seated Abs Crunch Machine": "machine",
    "Seated Cable Row": "machine",
    "Single Arm Dumbbell Row": "dumbbells",
    "Situps": "bodyweight",
    "Straight Arm Cable Pulldown": "cable",
    "Sumo Squat": "dumbbells",
    "Tricep Pushdown": "cable",
    "Vertical Chest Press Machine": "machine",
    "Weighted Lunge": "dumbbells",
}
EXERCISE_DEFAULT_BODY_PART = {
    exercise: group
    for group, exercises in EXERCISE_GROUPS.items()
    for exercise in exercises
}
EXERCISE_DEFAULT_PER_HAND = frozenset({
    "Dumbbell Arnold Press",
    "Dumbbell Bench Press",
    "Dumbbell Bicep Curl",
    "Dumbbell Hammer Curl",
    "Dumbbell Pec Fly",
    "Dumbbell Rows",
    "Dumbbell Shoulder Press",
    "Dumbbell Shrugs",
    "Front Raise",
    "Lateral Raise",
    "Weighted Lunge",
})

VARIATION_CHOICES = ["default", "flat", "incline", "decline", "short grip", "wide grip", "reverse grip"]
BODY_FOCUS_CHOICES = [
    ("", "blank"),
    ("Back,Biceps", "Back + Biceps"),
    ("Chest,Triceps", "Chest + Triceps"),
    ("Legs", "Legs"),
    ("Shoulders,Core", "Shoulders + Abs"),
]
EQUIPMENT_CHOICES = [
    "",
    "bodyweight",
    "dumbbells",
    "barbell",
    "machine",
    "cable",
    "kettlebell",
    "smith machine",
    "band",
    "other",
]
BODY_PART_CHOICES = [""] + BODY_PART_ORDER
LOG_ROW_COUNT = 6


@dataclass(frozen=True)
class FormRow:
    workout_date: str
    exercise: str
    variation: str
    sets: int
    reps: int
    weight_kg: float | None
    equipment: str
    per_hand: bool
    body_part: str = ""


@dataclass(frozen=True)
class InvalidFormRow:
    values: dict[str, str]
    error: str


@dataclass(frozen=True)
class FormSubmission:
    rows: list[FormRow]
    invalid_rows: list[InvalidFormRow]
    workout_date: str
    body_focus: str


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _parse_int(value: str, field: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a whole number") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return parsed


def _parse_weight(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError("weight must be a number") from exc
    if parsed < 0:
        raise ValueError("weight must not be negative")
    return parsed


def form_row_from_values(values: dict[str, str], *, prefix: str = "") -> FormRow:
    custom_exercise = values.get(f"{prefix}custom_exercise", "").strip()
    exercise_raw = custom_exercise or values.get(f"{prefix}exercise", "").strip()
    if not exercise_raw:
        raise ValueError("exercise is required")
    workout_date = values.get(f"{prefix}workout_date", "").strip()
    if not workout_date:
        raise ValueError("date is required")

    exercise = normalize_exercise(exercise_raw, exercise_raw)
    variation = values.get(f"{prefix}variation", "default").strip() or "default"
    if variation == "default" and exercise == "Barbell Bench Press" and "incline" in exercise_raw.lower():
        variation = "incline"
    equipment = values.get(f"{prefix}equipment", "").strip()
    if not equipment:
        equipment = EXERCISE_DEFAULT_EQUIPMENT.get(exercise, "")
    selected_body_part = values.get(f"{prefix}body_part", "").strip()
    default_body_part = EXERCISE_DEFAULT_BODY_PART.get(exercise, "")
    body_part = selected_body_part or default_body_part or row_body_part(exercise)
    per_hand_key = f"{prefix}per_hand"
    per_hand_defaulted_key = f"{prefix}per_hand_defaulted"
    per_hand = values.get(per_hand_key, "") == "1"
    if not per_hand and per_hand_key not in values and values.get(per_hand_defaulted_key, "") == "1":
        per_hand = exercise in EXERCISE_DEFAULT_PER_HAND
    row = FormRow(
        workout_date=workout_date,
        exercise=exercise,
        variation=variation,
        sets=_parse_int(values.get(f"{prefix}sets", "").strip(), "sets"),
        reps=_parse_int(values.get(f"{prefix}reps", "").strip(), "reps"),
        weight_kg=_parse_weight(values.get(f"{prefix}weight_kg", "")),
        equipment=equipment,
        per_hand=per_hand,
        body_part=body_part,
    )
    _validate_form_row(row)
    return row


def _validate_form_row(row: FormRow) -> None:
    if row.variation not in VALID_VARIATIONS:
        raise ValueError(f"invalid variation: {row.variation}")
    if row.equipment not in EQUIPMENT_VALUES:
        raise ValueError(f"invalid equipment: {row.equipment}")
    if row.body_part not in BODY_PART_VALUES:
        raise ValueError(f"invalid body part: {row.body_part}")
    rec = WorkoutRecord(
        "strength",
        row.exercise,
        row.variation,
        format_details(row.sets, row.reps, row.weight_kg),
        row.exercise,
        row.sets,
        row.reps,
        row.weight_kg,
        row.equipment,
        row.per_hand,
        row.body_part,
    )
    validate_record(rec)


def _fetch_rows_by_ids(conn: sqlite3.Connection, row_ids: list[int]) -> list[sqlite3.Row]:
    if not row_ids:
        return []
    placeholders = ",".join("?" for _ in row_ids)
    return list(conn.execute(
        f"""
        SELECT id, logged_at, workout_date, workout_type, exercise, variation, details,
               sets, reps, weight_kg, equipment, per_hand, body_part
        FROM workouts
        WHERE id IN ({placeholders})
        ORDER BY id
        """,
        row_ids,
    ))


def insert_form_rows(db_path: Path, rows: list[FormRow]) -> list[sqlite3.Row]:
    ensure_db(db_path)
    ts = now_ist().isoformat()
    inserted_ids: list[int] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for row in rows:
            _validate_form_row(row)
            details = format_details(row.sets, row.reps, row.weight_kg)
            cur = conn.execute(
                """
                INSERT INTO workouts
                (logged_at, workout_date, workout_type, exercise, variation, details,
                 raw_text, source, sets, reps, weight_kg, equipment, per_hand, body_part)
                VALUES (?, ?, 'strength', ?, ?, ?, ?, 'form', ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    row.workout_date,
                    row.exercise,
                    row.variation,
                    details,
                    row.exercise,
                    row.sets,
                    row.reps,
                    row.weight_kg,
                    row.equipment,
                    int(row.per_hand),
                    row.body_part,
                ),
            )
            if cur.lastrowid is None:
                raise RuntimeError("SQLite insert did not return a row id")
            inserted_ids.append(cur.lastrowid)
        conn.commit()
        return _fetch_rows_by_ids(conn, inserted_ids)


def update_form_row(db_path: Path, row_id: int, row: FormRow) -> sqlite3.Row:
    ensure_db(db_path)
    _validate_form_row(row)
    details = format_details(row.sets, row.reps, row.weight_kg)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            UPDATE workouts
            SET workout_date = ?, exercise = ?, variation = ?, details = ?,
                raw_text = ?, sets = ?, reps = ?, weight_kg = ?, equipment = ?, per_hand = ?, body_part = ?
            WHERE id = ? AND workout_type = 'strength'
            """,
            (
                row.workout_date,
                row.exercise,
                row.variation,
                details,
                row.exercise,
                row.sets,
                row.reps,
                row.weight_kg,
                row.equipment,
                int(row.per_hand),
                row.body_part,
                row_id,
            ),
        )
        conn.commit()
        fetched = _fetch_rows_by_ids(conn, [row_id])
    if not fetched:
        raise ValueError(f"no strength row found for id {row_id}")
    return fetched[0]


def delete_form_row(db_path: Path, row_id: int) -> sqlite3.Row:
    ensure_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        fetched = _fetch_rows_by_ids(conn, [row_id])
        if not fetched:
            raise ValueError(f"no strength row found for id {row_id}")
        conn.execute("DELETE FROM workouts WHERE id = ? AND workout_type = 'strength'", (row_id,))
        conn.commit()
    return fetched[0]


def fetch_today_rows(db_path: Path, workout_date: str | None = None) -> list[sqlite3.Row]:
    ensure_db(db_path)
    day = workout_date or now_ist().date().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return list(conn.execute(
            """
            SELECT id, logged_at, workout_date, workout_type, exercise, variation, details,
                   sets, reps, weight_kg, equipment, per_hand, body_part
            FROM workouts
            WHERE workout_date = ? AND workout_type = 'strength'
            ORDER BY id DESC
            """,
            (day,),
        ))


def fetch_recent_rows(db_path: Path, limit: int = 10) -> list[sqlite3.Row]:
    ensure_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return list(conn.execute(
            """
            SELECT id, logged_at, workout_date, workout_type, exercise, variation, details,
                   sets, reps, weight_kg, equipment, per_hand, body_part
            FROM workouts
            WHERE workout_type = 'strength'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ))


def _flatten_form(data: dict[str, list[str]]) -> dict[str, str]:
    return {key: values[-1] if values else "" for key, values in data.items()}


def new_form_token() -> str:
    token = secrets.token_urlsafe(24)
    FORM_TOKENS.add(token)
    return token


def consume_form_token(token: str) -> None:
    if not token or token not in FORM_TOKENS:
        raise ValueError("form already submitted or expired; reload and try again")
    FORM_TOKENS.remove(token)


def _rows_from_post(data: dict[str, list[str]]) -> list[FormRow]:
    submission = _parse_form_submission(data)
    if submission.invalid_rows:
        raise ValueError(submission.invalid_rows[0].error)
    return submission.rows


def _parse_form_submission(data: dict[str, list[str]]) -> FormSubmission:
    rows: list[FormRow] = []
    invalid_rows: list[InvalidFormRow] = []
    flattened = _flatten_form(data)
    shared_date = flattened.get("workout_date", "").strip()
    shared_body_focus = flattened.get("body_focus", "")
    default_body_part = shared_body_focus if shared_body_focus in BODY_PART_ORDER else ""
    for idx in range(1, LOG_ROW_COUNT + 1):
        prefix = f"r{idx}_"
        row_fields = ("exercise", "custom_exercise", "sets", "reps", "weight_kg")
        if not any(data.get(f"{prefix}{field}", [""])[-1].strip() for field in row_fields):
            continue
        prefixed_values = dict(flattened)
        if shared_date and not prefixed_values.get(f"{prefix}workout_date"):
            prefixed_values[f"{prefix}workout_date"] = shared_date
        if default_body_part and not prefixed_values.get(f"{prefix}body_part"):
            prefixed_values[f"{prefix}body_part"] = default_body_part
        try:
            rows.append(form_row_from_values(prefixed_values, prefix=prefix))
        except ValueError as exc:
            row_values = {
                field: prefixed_values.get(f"{prefix}{field}", "")
                for field in (
                    "workout_date",
                    "exercise",
                    "custom_exercise",
                    "variation",
                    "sets",
                    "reps",
                    "weight_kg",
                    "equipment",
                    "body_part",
                    "per_hand",
                    "per_hand_defaulted",
                )
            }
            invalid_rows.append(InvalidFormRow(row_values, f"Row {idx}: {exc}"))
    if not rows and not invalid_rows:
        raise ValueError("enter at least one workout row")
    return FormSubmission(
        rows=rows,
        invalid_rows=invalid_rows,
        workout_date=shared_date,
        body_focus=shared_body_focus,
    )


def _layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <style>
    :root {{ color-scheme: light dark; --border: #8b8f9740; --accent: #0f766e; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      line-height: 1.4;
    }}
    header {{
      position: sticky;
      top: 0;
      background: Canvas;
      border-bottom: 1px solid var(--border);
      padding: 10px 14px;
    }}
    nav {{ display: flex; gap: 8px; max-width: 980px; margin: 0 auto; }}
    nav a, button, .button {{
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 9px 12px;
      text-decoration: none;
      color: CanvasText;
      background: Canvas;
      font: inherit;
    }}
    main {{ max-width: 980px; margin: 0 auto; padding: 14px; }}
    h1 {{ font-size: 1.35rem; margin: 8px 0 14px; }}
    h2 {{ font-size: 1.05rem; margin: 22px 0 10px; }}
    form {{ display: grid; gap: 12px; }}
    fieldset {{ border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin: 0; }}
    legend {{ padding: 0 6px; font-weight: 650; }}
    .grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }}
    label {{ display: grid; gap: 4px; font-size: 0.86rem; }}
    input, select {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: Canvas;
      color: CanvasText;
    }}
    .exercise {{ grid-column: span 2; }}
    .custom-exercise {{ grid-column: span 2; }}
    .check {{ align-content: end; }}
    .check span {{ min-height: 20px; }}
    .check input {{ width: 22px; min-height: 22px; }}
    button.primary {{ color: white; background: var(--accent); border-color: var(--accent); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 8px 6px; text-align: left; vertical-align: top; }}
    pre {{ overflow-x: auto; white-space: pre; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }}
    .notice {{ border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }}
    .error {{ border-color: #b91c1c; color: #b91c1c; }}
    .pr-date {{
      border-radius: 999px;
      display: inline-block;
      font-weight: 650;
      min-width: 104px;
      padding: 3px 8px;
      text-align: center;
    }}
    .pr-date-fresh {{ background: #16a34a24; color: #15803d; }}
    .pr-date-stale {{ background: #dc262624; color: #b91c1c; }}
    .chart-list {{ display: grid; gap: 18px; }}
    .chart-panel {{ border: 1px solid var(--border); border-radius: 8px; padding: 12px; }}
    .chart-heading {{ display: flex; justify-content: space-between; gap: 10px; margin-bottom: 8px; }}
    .chart-heading h2 {{ margin: 0; }}
    .chart-meta {{ color: color-mix(in srgb, CanvasText 68%, Canvas); font-size: 0.9rem; }}
    .progression-chart {{ width: 100%; height: auto; display: block; }}
    .axis {{ stroke: var(--border); stroke-width: 1; }}
    .history-line {{ fill: none; stroke: #2563eb; stroke-width: 3; }}
    .pr-line {{ fill: none; stroke: var(--accent); stroke-width: 3; stroke-dasharray: 7 5; }}
    .history-point {{ fill: #2563eb; }}
    .pr-point {{ fill: var(--accent); stroke: Canvas; stroke-width: 2; }}
    .chart-label {{ fill: CanvasText; font-size: 12px; }}
    .legend {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 0; font-size: 0.9rem; }}
    .legend span::before {{
      content: "";
      display: inline-block;
      width: 18px;
      height: 3px;
      margin-right: 6px;
      vertical-align: middle;
      background: #2563eb;
    }}
    .legend .pr::before {{ background: var(--accent); }}
    @media (max-width: 760px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .exercise {{ grid-column: span 2; }}
      .custom-exercise {{ grid-column: span 2; }}
      .chart-heading {{ display: block; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      td {{ border-bottom: 0; padding: 4px 0; }}
      tr {{ border-bottom: 1px solid var(--border); padding: 8px 0; }}
    }}
  </style>
  <script>
    function applyBodyFocus() {{
      const focusSelect = document.querySelector('select[name="body_focus"]');
      if (!focusSelect) return;
      const priority = focusSelect && focusSelect.value ? focusSelect.value.split(',') : [];
      document.querySelectorAll('select[data-exercise-select]').forEach((select) => {{
        const blank = select.querySelector('option[value=""]');
        const groups = Array.from(select.querySelectorAll('optgroup'));
        groups.sort((a, b) => {{
          const ai = priority.indexOf(a.label);
          const bi = priority.indexOf(b.label);
          if (ai !== -1 || bi !== -1) {{
            if (ai === -1) return 1;
            if (bi === -1) return -1;
            return ai - bi;
          }}
          return Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex);
        }});
        select.replaceChildren(blank, ...groups);
      }});
    }}
    function applyExerciseDefaults(select) {{
      const selected = select.options[select.selectedIndex];
      const row = select.closest('.grid');
      if (!selected || !row) return;
      const equipment = selected.dataset.equipment || '';
      const bodyPart = selected.dataset.bodyPart || '';
      const perHand = selected.dataset.perHand === '1';
      const equipmentSelect = row.querySelector('select[name$="equipment"]');
      const bodyPartSelect = row.querySelector('select[name$="body_part"]');
      const weightInput = row.querySelector('input[name$="weight_kg"]');
      const perHandInput = row.querySelector('input[name$="per_hand"]');
      const perHandDefaultedInput = row.querySelector('input[name$="per_hand_defaulted"]');
      if (equipmentSelect && equipment) equipmentSelect.value = equipment;
      if (bodyPartSelect && bodyPart) bodyPartSelect.value = bodyPart;
      if (weightInput && equipment === 'bodyweight') weightInput.value = '';
      if (perHandInput) perHandInput.checked = perHand;
      if (perHandDefaultedInput) perHandDefaultedInput.value = perHand ? '1' : '0';
    }}
    document.addEventListener('change', (event) => {{
      if (event.target.matches('select[name="body_focus"]')) {{
        applyBodyFocus();
      }}
      if (event.target.matches('select[data-exercise-select]')) {{
        applyExerciseDefaults(event.target);
      }}
    }});
    document.addEventListener('DOMContentLoaded', applyBodyFocus);
  </script>
</head>
<body>
  <header>
    <nav>
      <a href="/log">Log</a><a href="/today">Today</a><a href="/recent">Recent</a>
      <a href="/prs">PRs</a><a href="/progression">Progression</a>
    </nav>
  </header>
  <main>{body}</main>
</body>
</html>"""


def _options(values: list[str], selected: str) -> str:
    return "\n".join(
        (
            f'<option value="{_escape(value)}"{" selected" if value == selected else ""}>'
            f"{_escape(value or 'blank')}</option>"
        )
        for value in values
    )


def _labelled_options(values: list[tuple[str, str]], selected: str) -> str:
    return "\n".join(
        (
            f'<option value="{_escape(value)}"{" selected" if value == selected else ""}>'
            f"{_escape(label)}</option>"
        )
        for value, label in values
    )


def _exercise_options(selected: str) -> str:
    parts = []
    seen: set[str] = set()
    for idx, (group, exercises) in enumerate(EXERCISE_GROUPS.items()):
        options = []
        for exercise in exercises:
            seen.add(exercise)
            equipment = EXERCISE_DEFAULT_EQUIPMENT.get(exercise, "")
            body_part = EXERCISE_DEFAULT_BODY_PART.get(exercise, "")
            is_selected = " selected" if exercise == selected else ""
            per_hand = "1" if exercise in EXERCISE_DEFAULT_PER_HAND else "0"
            options.append(
                f'<option value="{_escape(exercise)}" data-equipment="{_escape(equipment)}"'
                f' data-body-part="{_escape(body_part)}"'
                f' data-per-hand="{per_hand}"{is_selected}>'
                f"{_escape(exercise)}</option>"
            )
        parts.append(
            f'<optgroup label="{_escape(group)}" data-original-index="{idx}">{"".join(options)}</optgroup>'
        )
    if selected and selected not in seen:
        parts.insert(0, f'<option value="{_escape(selected)}" selected>{_escape(selected)}</option>')
    return '<option value=""></option>' + "".join(parts)


def _row_fields(
    prefix: str,
    *,
    workout_date: str,
    row: Mapping[str, Any] | sqlite3.Row | None = None,
    include_date: bool = True,
) -> str:
    values: dict[str, Any] = dict(row) if row is not None else {}
    date_value = values.get("workout_date", workout_date)
    exercise = values.get("exercise", "")
    variation = values.get("variation", "default")
    sets = values.get("sets", "") if row is not None else 3
    reps = values.get("reps", "") if row is not None else 12
    weight = values.get("weight_kg", "")
    custom_exercise = values.get("custom_exercise", "")
    equipment = values.get("equipment", "") or EXERCISE_DEFAULT_EQUIPMENT.get(str(exercise), "")
    body_part = values.get("body_part", "") or EXERCISE_DEFAULT_BODY_PART.get(str(exercise), "")
    default_per_hand = row is None and str(exercise) in EXERCISE_DEFAULT_PER_HAND
    checked_value = values.get("per_hand", 0)
    checked = " checked" if checked_value in (1, "1", True) or default_per_hand else ""
    defaulted = str(values.get("per_hand_defaulted", "1" if default_per_hand else "0"))
    date_field = (
        f'<label>Date<input type="date" name="{prefix}workout_date" value="{_escape(date_value)}"></label>'
        if include_date
        else ""
    )
    return f"""
<div class="grid">
  {date_field}
  <label class="exercise">Exercise
    <select name="{prefix}exercise" data-exercise-select>{_exercise_options(str(exercise))}</select>
  </label>
  <label class="custom-exercise">Custom exercise
    <input name="{prefix}custom_exercise" value="{_escape(custom_exercise)}" placeholder="Type only if not listed">
  </label>
  <label>Variation<select name="{prefix}variation">{_options(VARIATION_CHOICES, str(variation))}</select></label>
  <label>Sets<input inputmode="numeric" name="{prefix}sets" value="{_escape(sets)}"></label>
  <label>Reps<input inputmode="numeric" name="{prefix}reps" value="{_escape(reps)}"></label>
  <label>Weight kg<input inputmode="decimal" name="{prefix}weight_kg" value="{_escape(weight)}"></label>
  <label>Equipment<select name="{prefix}equipment">{_options(EQUIPMENT_CHOICES, str(equipment))}</select></label>
  <label>Body part<select name="{prefix}body_part">{_options(BODY_PART_CHOICES, str(body_part))}</select></label>
  <label class="check"><span>Per hand</span><input type="checkbox" name="{prefix}per_hand" value="1"{checked}></label>
  <input type="hidden" name="{prefix}per_hand_defaulted" value="{defaulted}">
</div>"""


def _render_rows(rows: list[sqlite3.Row], *, include_id: bool = True) -> str:
    if not rows:
        return "<p>No rows.</p>"
    body = []
    for row in rows:
        weight = "" if row["weight_kg"] is None else f'{row["weight_kg"]:g}'
        per_hand = "yes" if row["per_hand"] else ""
        variation = "" if row["variation"] == "default" else row["variation"]
        id_cell = f"<td>{row['id']}</td>" if include_id else ""
        body.append(
            "<tr>"
            f"{id_cell}<td>{_escape(row['workout_date'])}</td><td>{_escape(row['exercise'])}</td>"
            f"<td>{_escape(variation)}</td><td>{row['sets']}×{row['reps']}</td><td>{_escape(weight)}</td>"
            f"<td>{_escape(row['equipment'])}</td><td>{_escape(row['body_part'])}</td><td>{per_hand}</td>"
            "</tr>"
        )
    id_header = "<th>ID</th>" if include_id else ""
    return (
        f"<table><thead><tr>{id_header}<th>Date</th><th>Exercise</th><th>Var</th><th>Sets</th>"
        "<th>Kg</th><th>Equip</th><th>Part</th><th>Each</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_log_page(
    *,
    saved: list[sqlite3.Row] | None = None,
    error: str = "",
    invalid_rows: list[InvalidFormRow] | None = None,
    workout_date: str = "",
    body_focus: str = "",
) -> str:
    today = now_ist().date().isoformat()
    token = new_form_token()
    selected_date = workout_date or today
    notices = []
    if saved is not None:
        notices.append(
            f'<div class="notice">Saved {len(saved)} valid row(s) after DB re-read.</div>'
            + _render_rows(saved)
        )
    if error:
        notices.append(f'<div class="notice error">{_escape(error)}</div>')
    if invalid_rows:
        fieldsets = "\n".join(
            f"<fieldset><legend>Failed row {idx}: {_escape(invalid.error)}</legend>"
            f"{_row_fields(f'r{idx}_', workout_date=selected_date, row=invalid.values, include_date=False)}</fieldset>"
            for idx, invalid in enumerate(invalid_rows, start=1)
        )
    else:
        fieldsets = "\n".join(
            f"<fieldset><legend>Row {idx}</legend>"
            f"{_row_fields(f'r{idx}_', workout_date=selected_date, include_date=False)}</fieldset>"
            for idx in range(1, LOG_ROW_COUNT + 1)
        )
    notice = "".join(notices)
    body = f"""
<h1>Log Workout</h1>
{notice}
<form method="post" action="/log">
  <input type="hidden" name="token" value="{_escape(token)}">
  <label>Workout date<input type="date" name="workout_date" value="{_escape(selected_date)}"></label>
  <label>Body part trained<select name="body_focus">{_labelled_options(BODY_FOCUS_CHOICES, body_focus)}</select></label>
  {fieldsets}
  <button class="primary" type="submit">Save Rows</button>
</form>"""
    return _layout("Log Workout", body)


def render_today_page(
    db_path: Path,
    *,
    updated: sqlite3.Row | None = None,
    deleted: sqlite3.Row | None = None,
    error: str = "",
) -> str:
    today = now_ist().date().isoformat()
    rows = fetch_today_rows(db_path, today)
    notice = f'<div class="notice error">{_escape(error)}</div>' if error else ""
    if updated is not None:
        notice = '<div class="notice">Updated after DB re-read.</div>' + _render_rows([updated])
    if deleted is not None:
        notice = '<div class="notice">Deleted row after DB lookup.</div>' + _render_rows([deleted])
    forms = []
    for row in rows:
        forms.append(
            f"""
<fieldset>
  <legend>ID {row['id']}</legend>
  <form method="post" action="/today?id={row['id']}">
    {_row_fields("", workout_date=today, row=row)}
    <button class="primary" type="submit">Update ID {row['id']}</button>
  </form>
  <form method="post" action="/today/delete?id={row['id']}">
    <button type="submit">Delete ID {row['id']}</button>
  </form>
</fieldset>"""
        )
    body = f"""
<h1>Today</h1>
{notice}
{''.join(forms) if forms else '<p>No strength rows for today.</p>'}"""
    return _layout("Today", body)


def render_recent_page(db_path: Path) -> str:
    rows = fetch_recent_rows(db_path)
    body = f"""
<h1>Recent</h1>
{_render_rows(rows, include_id=False)}"""
    return _layout("Recent", body)


def render_prs_page(db_path: Path, *, selected_part: str = "") -> str:
    if not db_path.exists():
        return _layout("PRs", "<h1>PRs</h1><p>No database yet.</p>")

    rows = pr_display_rows(db_path)
    selected_part = selected_part if selected_part in BODY_PART_ORDER else ""
    filter_form = _prs_filter_form(selected_part)
    if selected_part:
        rows = [row for row in rows if row.part == selected_part]
    if not rows:
        return _layout("PRs", f"<h1>PRs</h1>{filter_form}<p>No strength workouts logged yet.</p>")

    sections = []
    current_part = ""
    section_rows: list[str] = []
    for row in rows:
        if row.part != current_part:
            if section_rows:
                sections.append(_prs_section(current_part, section_rows))
            current_part = row.part
            section_rows = []
        section_rows.append(
            "<tr>"
            f"<td>{_escape(row.exercise)}</td>"
            f"<td>{_escape(row.variation)}</td>"
            f"<td>{_escape(row.performance)}</td>"
            f"<td>{_pr_date_badge(row.pr_date)}</td>"
            "</tr>"
        )
    if section_rows:
        sections.append(_prs_section(current_part, section_rows))

    return _layout("PRs", f"<h1>PRs</h1>{filter_form}{''.join(sections)}")


def render_progression_page(db_path: Path, *, selected_part: str = "") -> str:
    if not db_path.exists():
        return _layout("Progression", "<h1>Progression</h1><p>No database yet.</p>")

    series = progression_series(db_path)
    selected_part = selected_part if selected_part in BODY_PART_ORDER else ""
    filter_form = _body_part_filter_form("/progression", selected_part)
    if selected_part:
        series = [item for item in series if item.part == selected_part]
    if not series:
        return _layout(
            "Progression",
            f"<h1>Progression</h1>{filter_form}<p>No exercises have 3 or more weighted entries yet.</p>",
        )

    charts = "".join(_progression_panel(item) for item in series)
    body = f"""
<h1>Progression</h1>
{filter_form}
<div class="legend"><span>Logged weight</span><span class="pr">PR step</span></div>
<div class="chart-list">{charts}</div>"""
    return _layout("Progression", body)


def _prs_filter_form(selected_part: str) -> str:
    return _body_part_filter_form("/prs", selected_part)


def _body_part_filter_form(action: str, selected_part: str) -> str:
    options = [""] + BODY_PART_ORDER
    return f"""
<form method="get" action="{_escape(action)}">
  <label>Body part<select name="part" onchange="this.form.submit()">{_options(options, selected_part)}</select></label>
</form>"""


def _pr_date_badge(pr_date: str) -> str:
    date_text = _escape(pr_date)
    css_class = "pr-date-stale" if _pr_date_is_stale(pr_date) else "pr-date-fresh"
    return f'<span class="pr-date {css_class}">{date_text}</span>'


def _pr_date_is_stale(pr_date: str) -> bool:
    try:
        parsed = datetime.strptime(pr_date[2:], "%d %b %Y").date()
    except ValueError:
        return False
    return (now_ist().date() - parsed).days > 30


def _prs_section(part: str, rows: list[str]) -> str:
    return (
        f"<h2>{_escape(part)}</h2>"
        "<table><thead><tr><th>Exercise</th><th>Variation</th><th>Best set</th><th>PR date</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _progression_panel(series: ProgressionSeries) -> str:
    variation = "" if series.variation in ("", "default") else f" [{series.variation}]"
    pr_lookup = {id(point) for point in series.pr_points}
    latest_points = series.points[-3:]
    rows = "".join(
        "<tr>"
        f"<td>{_escape(point.workout_date)}</td>"
        f"<td>{_escape(point.performance)}</td>"
        f"<td>{'yes' if id(point) in pr_lookup else ''}</td>"
        "</tr>"
        for point in latest_points
    )
    return f"""
<section class="chart-panel">
  <div class="chart-heading">
    <h2>{_escape(series.exercise)}{_escape(variation)}</h2>
    <div class="chart-meta">{_escape(series.part)} · {len(series.points)} weighted entries</div>
  </div>
  {_progression_svg(series.points, series.pr_points)}
  <table>
    <thead><tr><th>Date</th><th>Latest set</th><th>PR step</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def _progression_svg(points: list[ProgressionPoint], pr_points: list[ProgressionPoint]) -> str:
    width = 720
    height = 220
    left = 52
    right = 14
    top = 18
    bottom = 36
    plot_width = width - left - right
    plot_height = height - top - bottom
    weights = [point.weight_kg for point in points]
    min_weight = min(weights)
    max_weight = max(weights)
    if min_weight == max_weight:
        min_weight -= 1
        max_weight += 1
    else:
        padding = (max_weight - min_weight) * 0.12
        min_weight -= padding
        max_weight += padding

    dates = [_date_ordinal(point.workout_date, idx) for idx, point in enumerate(points)]
    min_date = min(dates)
    max_date = max(dates)

    def xy(point: ProgressionPoint, idx: int) -> tuple[float, float]:
        if min_date == max_date:
            x_ratio = 0.5
        else:
            x_ratio = (_date_ordinal(point.workout_date, idx) - min_date) / (max_date - min_date)
        y_ratio = (point.weight_kg - min_weight) / (max_weight - min_weight)
        return left + x_ratio * plot_width, top + (1 - y_ratio) * plot_height

    coords = [xy(point, idx) for idx, point in enumerate(points)]
    pr_lookup = {id(point) for point in pr_points}
    pr_coords = [(x, y) for (x, y), point in zip(coords, points) if id(point) in pr_lookup]
    history_polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    pr_polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in pr_coords)
    point_nodes = []
    for idx, (x, y) in enumerate(coords):
        point = points[idx]
        css_class = "pr-point" if id(point) in pr_lookup else "history-point"
        point_nodes.append(
            f'<g><circle class="{css_class}" cx="{x:.1f}" cy="{y:.1f}" r="4.5">'
            f"<title>{_escape(point.workout_date)} · {_escape(point.performance)}</title>"
            "</circle></g>"
        )

    y_min_label = f"{min(weights):g}kg"
    y_max_label = f"{max(weights):g}kg"
    first_date = points[0].workout_date
    last_date = points[-1].workout_date
    return f"""
<svg class="progression-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Weight progression chart">
  <line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}"></line>
  <line class="axis" x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"></line>
  <text class="chart-label" x="4" y="{top + 4}">{_escape(y_max_label)}</text>
  <text class="chart-label" x="4" y="{height - bottom}">{_escape(y_min_label)}</text>
  <text class="chart-label" x="{left}" y="{height - 10}">{_escape(first_date)}</text>
  <text class="chart-label" text-anchor="end" x="{width - right}" y="{height - 10}">{_escape(last_date)}</text>
  <polyline class="history-line" points="{history_polyline}"></polyline>
  <polyline class="pr-line" points="{pr_polyline}"></polyline>
  {''.join(point_nodes)}
</svg>"""


def _date_ordinal(value: str, fallback: int) -> int:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().toordinal()
    except ValueError:
        return fallback


def normalize_bind_host(host: str) -> str:
    bind_host = host.strip()
    if not bind_host:
        raise ValueError("--host resolved to an empty value; install/configure Tailscale or use --host 127.0.0.1")
    return bind_host


class WorkoutFormHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB

    def _send_html(self, body: str, *, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(303)
            self.send_header("Location", "/log")
            self.end_headers()
            return
        if parsed.path == "/log":
            self._send_html(render_log_page())
            return
        if parsed.path == "/today":
            self._send_html(render_today_page(self.db_path))
            return
        if parsed.path == "/recent":
            self._send_html(render_recent_page(self.db_path))
            return
        if parsed.path == "/prs":
            selected_part = parse_qs(parsed.query).get("part", [""])[-1]
            self._send_html(render_prs_page(self.db_path, selected_part=selected_part))
            return
        if parsed.path == "/progression":
            selected_part = parse_qs(parsed.query).get("part", [""])[-1]
            self._send_html(render_progression_page(self.db_path, selected_part=selected_part))
            return
        self._send_html(_layout("Not Found", "<h1>Not Found</h1>"), status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        data = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        if parsed.path == "/log":
            try:
                consume_form_token(data.get("token", [""])[-1])
                submission = _parse_form_submission(data)
                saved = insert_form_rows(self.db_path, submission.rows) if submission.rows else []
            except ValueError as exc:
                self._send_html(render_log_page(error=str(exc)), status=400)
                return
            if submission.invalid_rows:
                error = (
                    f"Saved {len(saved)} valid row(s). "
                    f"Fix and resubmit the {len(submission.invalid_rows)} failed row(s) below."
                )
                self._send_html(
                    render_log_page(
                        saved=saved,
                        error=error,
                        invalid_rows=submission.invalid_rows,
                        workout_date=submission.workout_date,
                        body_focus=submission.body_focus,
                    ),
                    status=400 if not saved else 200,
                )
                return
            self._send_html(render_log_page(saved=saved))
            return
        if parsed.path == "/today":
            try:
                row_id = int(parse_qs(parsed.query).get("id", [""])[-1])
                updated = update_form_row(self.db_path, row_id, form_row_from_values(_flatten_form(data)))
            except ValueError as exc:
                self._send_html(render_today_page(self.db_path, error=str(exc)), status=400)
                return
            self._send_html(render_today_page(self.db_path, updated=updated))
            return
        if parsed.path == "/today/delete":
            try:
                row_id = int(parse_qs(parsed.query).get("id", [""])[-1])
                deleted = delete_form_row(self.db_path, row_id)
            except ValueError as exc:
                self._send_html(render_today_page(self.db_path, error=str(exc)), status=400)
                return
            self._send_html(render_today_page(self.db_path, deleted=deleted))
            return
        self._send_html(_layout("Not Found", "<h1>Not Found</h1>"), status=404)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the workout tracker mobile form")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    args = parser.parse_args()
    try:
        host = normalize_bind_host(args.host)
    except ValueError as exc:
        parser.error(str(exc))

    handler = type("ConfiguredWorkoutFormHandler", (WorkoutFormHandler,), {"db_path": Path(args.db)})
    server = ThreadingHTTPServer((host, args.port), handler)
    print(f"Workout form running at http://{host}:{args.port}/log")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

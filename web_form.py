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
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from tracker.core import ensure_db, now_ist
from tracker.normalizer import normalize_exercise
from tracker.parser import (
    EQUIPMENT_VALUES,
    VALID_VARIATIONS,
    WorkoutRecord,
    format_details,
    validate_record,
)
from tracker.reports import format_prs_compact

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"
FORM_TOKENS: set[str] = set()

EXERCISE_GROUPS = {
    "Recent": [
        "Bodyweight Squat",
        "Bodyweight Calf Raise",
        "45 Degree Leg Press",
        "Hamstring Curl",
        "Hip Thrust",
        "Kettlebell Swing",
        "Sumo Squat",
    ],
    "Chest": [
        "Barbell Bench Press",
        "Barbell Incline Press",
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
        "Chest Supported Rows",
        "Compound Row Machine",
        "Dumbbell Rows",
        "Lat Pull Down",
        "Seated Row Machine",
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
    "Arms": [
        "Assisted Dips",
        "Barbell Curl",
        "Bicep Curl on Cable",
        "Bicep Preacher Curl",
        "Cable Overhead Tricep Extension",
        "Dumbbell Bicep Curl",
        "Dumbbell Hammer Curl",
        "Dumbbell Overhead Tricep Extension",
        "Hammer Curl",
        "Hammer Curl on Cable",
        "Preacher Curl",
        "Reverse Curl on Cable",
        "Tricep Pushdown",
    ],
    "Legs": [
        "45 Degree Leg Press",
        "Barbell Squat",
        "Bodyweight Calf Raise",
        "Bodyweight Squat",
        "Calf Raise",
        "Glute Kickback Machine",
        "Goblet Squat",
        "Hamstring Curl",
        "Hip Thrust",
        "Horizontal Leg Press",
        "Kettlebell Swing",
        "Leg Extension",
        "Sumo Squat",
        "Weighted Lunge",
    ],
    "Core": [
        "Bodyweight Abs Crunch",
        "Leg Raise",
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
    "Barbell Curl": "barbell",
    "Barbell Incline Press": "barbell",
    "Barbell Squat": "barbell",
    "Bicep Curl on Cable": "cable",
    "Bodyweight Abs Crunch": "bodyweight",
    "Bodyweight Calf Raise": "bodyweight",
    "Bodyweight Squat": "bodyweight",
    "Cable Overhead Tricep Extension": "cable",
    "Cable Rope Upright Row": "cable",
    "Calf Raise": "machine",
    "Chest Supported Rows": "machine",
    "Compound Row Machine": "machine",
    "Dumbbell Arnold Press": "dumbbells",
    "Dumbbell Bench Press": "dumbbells",
    "Dumbbell Bicep Curl": "dumbbells",
    "Dumbbell Hammer Curl": "dumbbells",
    "Dumbbell Overhead Tricep Extension": "dumbbells",
    "Dumbbell Pec Fly": "dumbbells",
    "Dumbbell Rows": "dumbbells",
    "Dumbbell Shoulder Press": "dumbbells",
    "Dumbbell Shrugs": "dumbbells",
    "Face Pull": "cable",
    "Glute Kickback Machine": "machine",
    "Hamstring Curl": "machine",
    "Hammer Curl on Cable": "cable",
    "Horizontal Leg Press": "machine",
    "Kettlebell Swing": "kettlebell",
    "Lat Pull Down": "machine",
    "Lateral Raise": "dumbbells",
    "Pec Fly": "machine",
    "Preacher Curl": "machine",
    "Push Up": "bodyweight",
    "Rear Delt Fly": "machine",
    "Reverse Curl on Cable": "cable",
    "Seated Abs Crunch Machine": "machine",
    "Seated Row Machine": "machine",
    "Situps": "bodyweight",
    "Tricep Pushdown": "cable",
    "Vertical Chest Press Machine": "machine",
}

VARIATION_CHOICES = ["default", "flat", "incline", "decline", "short grip", "wide grip"]
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
    exercise_raw = values.get(f"{prefix}exercise", "").strip()
    if not exercise_raw:
        raise ValueError("exercise is required")
    workout_date = values.get(f"{prefix}workout_date", "").strip()
    if not workout_date:
        raise ValueError("date is required")

    exercise = normalize_exercise(exercise_raw, exercise_raw)
    variation = values.get(f"{prefix}variation", "default").strip() or "default"
    equipment = values.get(f"{prefix}equipment", "").strip()
    if not equipment:
        equipment = EXERCISE_DEFAULT_EQUIPMENT.get(exercise, "")
    row = FormRow(
        workout_date=workout_date,
        exercise=exercise,
        variation=variation,
        sets=_parse_int(values.get(f"{prefix}sets", "").strip(), "sets"),
        reps=_parse_int(values.get(f"{prefix}reps", "").strip(), "reps"),
        weight_kg=_parse_weight(values.get(f"{prefix}weight_kg", "")),
        equipment=equipment,
        per_hand=values.get(f"{prefix}per_hand", "") == "1",
    )
    _validate_form_row(row)
    return row


def _validate_form_row(row: FormRow) -> None:
    if row.variation not in VALID_VARIATIONS:
        raise ValueError(f"invalid variation: {row.variation}")
    if row.equipment not in EQUIPMENT_VALUES:
        raise ValueError(f"invalid equipment: {row.equipment}")
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
    )
    validate_record(rec)


def _fetch_rows_by_ids(conn: sqlite3.Connection, row_ids: list[int]) -> list[sqlite3.Row]:
    if not row_ids:
        return []
    placeholders = ",".join("?" for _ in row_ids)
    return list(conn.execute(
        f"""
        SELECT id, logged_at, workout_date, workout_type, exercise, variation, details,
               sets, reps, weight_kg, equipment, per_hand
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
                 raw_text, source, sets, reps, weight_kg, equipment, per_hand)
                VALUES (?, ?, 'strength', ?, ?, ?, ?, 'form', ?, ?, ?, ?, ?)
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
                raw_text = ?, sets = ?, reps = ?, weight_kg = ?, equipment = ?, per_hand = ?
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
                   sets, reps, weight_kg, equipment, per_hand
            FROM workouts
            WHERE workout_date = ? AND workout_type = 'strength'
            ORDER BY id DESC
            """,
            (day,),
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
    rows: list[FormRow] = []
    for idx in range(1, 6):
        prefix = f"r{idx}_"
        row_fields = ("exercise", "sets", "reps", "weight_kg")
        if not any(data.get(f"{prefix}{field}", [""])[-1].strip() for field in row_fields):
            continue
        rows.append(form_row_from_values(_flatten_form(data), prefix=prefix))
    if not rows:
        raise ValueError("enter at least one workout row")
    return rows


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
    .check {{ align-content: end; }}
    .check span {{ min-height: 20px; }}
    .check input {{ width: 22px; min-height: 22px; }}
    button.primary {{ color: white; background: var(--accent); border-color: var(--accent); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 8px 6px; text-align: left; vertical-align: top; }}
    pre {{ overflow-x: auto; white-space: pre; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }}
    .notice {{ border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }}
    .error {{ border-color: #b91c1c; color: #b91c1c; }}
    @media (max-width: 760px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .exercise {{ grid-column: span 2; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      td {{ border-bottom: 0; padding: 4px 0; }}
      tr {{ border-bottom: 1px solid var(--border); padding: 8px 0; }}
    }}
  </style>
  <script>
    function applyExerciseDefaults(select) {{
      const selected = select.options[select.selectedIndex];
      const row = select.closest('.grid');
      if (!selected || !row) return;
      const equipment = selected.dataset.equipment || '';
      const equipmentSelect = row.querySelector('select[name$="equipment"]');
      const weightInput = row.querySelector('input[name$="weight_kg"]');
      if (equipmentSelect && equipment) equipmentSelect.value = equipment;
      if (weightInput && equipment === 'bodyweight') weightInput.value = '';
    }}
    document.addEventListener('change', (event) => {{
      if (event.target.matches('select[data-exercise-select]')) {{
        applyExerciseDefaults(event.target);
      }}
    }});
  </script>
</head>
<body>
  <header><nav><a href="/log">Log</a><a href="/today">Today</a><a href="/prs">PRs</a></nav></header>
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


def _exercise_options(selected: str) -> str:
    parts = []
    seen: set[str] = set()
    for group, exercises in EXERCISE_GROUPS.items():
        options = []
        for exercise in exercises:
            seen.add(exercise)
            equipment = EXERCISE_DEFAULT_EQUIPMENT.get(exercise, "")
            is_selected = " selected" if exercise == selected else ""
            options.append(
                f'<option value="{_escape(exercise)}" data-equipment="{_escape(equipment)}"{is_selected}>'
                f"{_escape(exercise)}</option>"
            )
        parts.append(f'<optgroup label="{_escape(group)}">{"".join(options)}</optgroup>')
    if selected and selected not in seen:
        parts.insert(0, f'<option value="{_escape(selected)}" selected>{_escape(selected)}</option>')
    return '<option value=""></option>' + "".join(parts)


def _row_fields(prefix: str, *, workout_date: str, row: sqlite3.Row | None = None) -> str:
    values: dict[str, Any] = dict(row) if row is not None else {}
    date_value = values.get("workout_date", workout_date)
    exercise = values.get("exercise", "")
    variation = values.get("variation", "default")
    sets = values.get("sets", "")
    reps = values.get("reps", "")
    weight = values.get("weight_kg", "")
    equipment = values.get("equipment", "") or EXERCISE_DEFAULT_EQUIPMENT.get(str(exercise), "")
    checked = " checked" if values.get("per_hand", 0) else ""
    return f"""
<div class="grid">
  <label>Date<input type="date" name="{prefix}workout_date" value="{_escape(date_value)}"></label>
  <label class="exercise">Exercise
    <select name="{prefix}exercise" data-exercise-select>{_exercise_options(str(exercise))}</select>
  </label>
  <label>Variation<select name="{prefix}variation">{_options(VARIATION_CHOICES, str(variation))}</select></label>
  <label>Sets<input inputmode="numeric" name="{prefix}sets" value="{_escape(sets)}"></label>
  <label>Reps<input inputmode="numeric" name="{prefix}reps" value="{_escape(reps)}"></label>
  <label>Weight kg<input inputmode="decimal" name="{prefix}weight_kg" value="{_escape(weight)}"></label>
  <label>Equipment<select name="{prefix}equipment">{_options(EQUIPMENT_CHOICES, str(equipment))}</select></label>
  <label class="check"><span>Per hand</span><input type="checkbox" name="{prefix}per_hand" value="1"{checked}></label>
</div>"""


def _render_rows(rows: list[sqlite3.Row]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    body = []
    for row in rows:
        weight = "" if row["weight_kg"] is None else f'{row["weight_kg"]:g}'
        per_hand = "yes" if row["per_hand"] else ""
        variation = "" if row["variation"] == "default" else row["variation"]
        body.append(
            "<tr>"
            f"<td>{row['id']}</td><td>{_escape(row['workout_date'])}</td><td>{_escape(row['exercise'])}</td>"
            f"<td>{_escape(variation)}</td><td>{row['sets']}×{row['reps']}</td><td>{_escape(weight)}</td>"
            f"<td>{_escape(row['equipment'])}</td><td>{per_hand}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>ID</th><th>Date</th><th>Exercise</th><th>Var</th><th>Sets</th>"
        "<th>Kg</th><th>Equip</th><th>Each</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_log_page(*, saved: list[sqlite3.Row] | None = None, error: str = "") -> str:
    today = now_ist().date().isoformat()
    token = new_form_token()
    notice = f'<div class="notice error">{_escape(error)}</div>' if error else ""
    if saved is not None:
        notice = '<div class="notice">Saved after DB re-read.</div>' + _render_rows(saved)
    fieldsets = "\n".join(
        f"<fieldset><legend>Row {idx}</legend>{_row_fields(f'r{idx}_', workout_date=today)}</fieldset>"
        for idx in range(1, 6)
    )
    body = f"""
<h1>Log Workout</h1>
{notice}
<form method="post" action="/log">
  <input type="hidden" name="token" value="{_escape(token)}">
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


def render_prs_page(db_path: Path) -> str:
    report = format_prs_compact(db_path) if db_path.exists() else "No database yet."
    return _layout("PRs", f"<h1>PRs</h1><pre>{_escape(report)}</pre>")


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
        if parsed.path == "/prs":
            self._send_html(render_prs_page(self.db_path))
            return
        self._send_html(_layout("Not Found", "<h1>Not Found</h1>"), status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        data = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        if parsed.path == "/log":
            try:
                consume_form_token(data.get("token", [""])[-1])
                saved = insert_form_rows(self.db_path, _rows_from_post(data))
            except ValueError as exc:
                self._send_html(render_log_page(error=str(exc)), status=400)
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

    handler = type("ConfiguredWorkoutFormHandler", (WorkoutFormHandler,), {"db_path": Path(args.db)})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Workout form running at http://{args.host}:{args.port}/log")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

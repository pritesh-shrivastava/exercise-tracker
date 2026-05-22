"""PR report generation for the workout tracker."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

BODY_PART_ORDER = ["Chest", "Back", "Shoulders", "Arms", "Legs", "Core", "Other"]
BODY_PART_EMOJI = {
    "Chest": "🩻",
    "Back": "🧱",
    "Shoulders": "🧢",
    "Arms": "💪",
    "Legs": "🦵",
    "Core": "⚡",
    "Other": "📦",
}


@dataclass(frozen=True)
class PRRow:
    exercise: str
    variation: str
    details: str
    workout_date: str
    raw_text: str
    sets: int = 0
    reps: int = 0
    weight_kg: float | None = None
    equipment: str = ""
    per_hand: bool = False


def _body_part(exercise: str) -> str:
    name = exercise.lower()
    chest = ["bench press", "pec fly", "chest press", "chest fly", "push up", "pushup"]
    back = ["lat pull down", "lat pulldown", "row", "pullup", "pull up", "back extension"]
    back_exclude = ["upright row"]
    shoulders = [
        "shoulder press", "arnold press", "lateral raise", "front raise",
        "rear delt", "face pull", "upright row", "dumbbell shrug", "dumbbell shrugs",
        "shrug", "shrugs",
    ]
    legs = ["leg press", "leg extension", "hamstring curl",
            "goblet squat", "goblet squats", "sumo squat", "squat", "calf raise", "lunge", "lunges"]
    arms = ["bicep", "tricep", "curl on cable", "preacher curl", "pushdown", "extension", "curl"]
    arms_exclude = ["hamstring curl", "calf curl", "back extension"]
    if any(t in name for t in chest):
        return "Chest"
    if any(t in name for t in back) and "rear delt" not in name and not any(t in name for t in back_exclude):
        return "Back"
    if any(t in name for t in shoulders):
        return "Shoulders"
    if any(t in name for t in legs):
        return "Legs"
    if any(t in name for t in arms) and not any(t in name for t in arms_exclude):
        return "Arms"
    if any(t in name for t in ["crunch", "abs", "plank", "core", "leg raises", "leg raise", "situp", "situps"]):
        return "Core"
    return "Other"


def _load_rows(db_path: Path) -> list[PRRow]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT workout_date, exercise, COALESCE(variation, 'default') AS variation,
                   details, raw_text, COALESCE(sets, 0) AS sets, COALESCE(reps, 0) AS reps,
                   weight_kg, COALESCE(equipment, '') AS equipment,
                   COALESCE(per_hand, 0) AS per_hand
            FROM workouts WHERE workout_type = 'strength'
            ORDER BY workout_date, id
            """
        ).fetchall()
    return [PRRow(**dict(row)) for row in rows]


def _best_sets(rows: Iterable[PRRow]) -> dict[tuple[str, str], PRRow]:
    best: dict[tuple[str, str], tuple[tuple, PRRow]] = {}
    for row in rows:
        key = (row.exercise, row.variation or "flat")
        # Score: higher weight first, then higher reps, then higher sets, then latest date
        w = row.weight_kg if row.weight_kg is not None else -1.0
        score = (w, row.reps, row.sets, row.workout_date)
        if key not in best or score > best[key][0]:
            best[key] = (score, row)
    return {k: v[1] for k, v in best.items()}


def _fmt_date(d: str) -> str:
    try:
        pr_date = datetime.strptime(d, "%Y-%m-%d").date()
        age = (date.today() - pr_date).days
        dot = "+" if age <= 14 else "-"
        return f"{dot} {pr_date.strftime('%d %b %Y')}"
    except ValueError:
        return d


def format_prs_compact(db_path: Path) -> str:
    """One line per exercise: emoji  exercise  [variations]  sets×reps @ weight  date."""
    rows = _load_rows(db_path)
    if not rows:
        return "No strength workouts logged yet."

    prs = _best_sets(rows)
    grouped: dict[str, dict[str, list[tuple[str, PRRow]]]] = defaultdict(lambda: defaultdict(list))
    for (exercise, variation), row in prs.items():
        grouped[_body_part(exercise)][exercise].append((variation, row))

    seen = list(grouped.keys())
    order = [p for p in BODY_PART_ORDER if p in seen] + sorted(
        p for p in seen if p not in BODY_PART_ORDER
    )

    lines = []
    for body_part in order:
        emoji = BODY_PART_EMOJI.get(body_part, "•")
        for exercise in sorted(grouped[body_part]):
            _VAR_ORDER = {"default": 0, "flat": 1}
            variations = sorted(
                grouped[body_part][exercise],
                key=lambda item: (_VAR_ORDER.get(item[0], 2), item[0]),
            )
            # Pick best row (highest weight, then most recent)
            best_row = max(variations, key=lambda item: (
                item[1].weight_kg or -1, item[1].workout_date
            ))[1]
            non_default = [v for v, _ in variations if v not in ("default", "")]
            var_str = f"  [{', '.join(non_default)}]" if non_default else ""

            w = best_row.weight_kg
            if w is not None:
                if best_row.per_hand:
                    half = w / 2
                    per_hand_kg = int(half) if half == int(half) else half
                    total_str = str(int(w)) if w == int(w) else str(w)
                    weight_str = f"{total_str}kg ({per_hand_kg}ea.)"
                else:
                    weight_str = f"{int(w) if w == int(w) else w}kg"
                perf = f"{best_row.sets}×{best_row.reps} @ {weight_str}"
            else:
                perf = f"{best_row.sets}×{best_row.reps}"

            date_str = _fmt_date(best_row.workout_date)
            lines.append(f"{emoji}  {exercise:<38}{var_str:<28}{perf:<22}{date_str}")

    return "\n".join(lines)



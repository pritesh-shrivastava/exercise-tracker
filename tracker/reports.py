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
    "Chest": "💪",
    "Back": "🧱",
    "Shoulders": "🧢",
    "Arms": "🏹",
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
    back = ["lat pull down", "lat pulldown", "row", "pullup", "pull up"]
    shoulders = ["shoulder press", "arnold press", "lateral raise", "front raise", "rear delt"]
    legs = ["leg press", "leg extension", "leg ext", "leg curl", "hamstring curl",
            "goblet squat", "goblet squats", "sumo squat", "squat", "calf raise"]
    arms = ["bicep", "tricep", "curl on cable", "preacher curl", "pushdown", "extension", "curl"]
    arms_exclude = ["leg curl", "hamstring curl", "calf curl"]
    if any(t in name for t in chest):
        return "Chest"
    if any(t in name for t in back) and "rear delt" not in name:
        return "Back"
    if any(t in name for t in shoulders):
        return "Shoulders"
    if any(t in name for t in legs):
        return "Legs"
    if any(t in name for t in arms) and not any(t in name for t in arms_exclude):
        return "Arms"
    if any(t in name for t in ["crunch", "abs", "plank", "core"]):
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
        dot = "🟢" if age <= 14 else "🔴"
        return f"{dot} {pr_date.strftime('%d %b %Y')}"
    except ValueError:
        return d


def format_prs(db_path: Path) -> str:
    """Return the full PR report as a string suitable for print or Telegram."""
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

    lines = [""]
    for body_part in order:
        emoji = BODY_PART_EMOJI.get(body_part, "•")
        lines.append(f"{emoji} {body_part}")
        for exercise in sorted(grouped[body_part]):
            _VAR_ORDER = {"default": 0, "flat": 1}
            variations = sorted(
                grouped[body_part][exercise],
                key=lambda item: (_VAR_ORDER.get(item[0], 2), item[0]),
            )
            lines.append(f"- {exercise}")
            for variation, row in variations:
                date = _fmt_date(row.workout_date)
                display_details = row.details
                if row.per_hand and row.weight_kg:
                    per_hand_kg = int(row.weight_kg / 2) if (row.weight_kg / 2) == int(row.weight_kg / 2) else row.weight_kg / 2
                    # Rebuild details with total weight if details shows per-hand
                    total_str = str(int(row.weight_kg)) if row.weight_kg == int(row.weight_kg) else str(row.weight_kg)
                    display_details = f"{row.sets}x{row.reps} @ {total_str}"
                    display_details = f"{display_details} ({per_hand_kg} ea.)"
                if variation in ("default", ""):
                    lines.append(f"  • {display_details} ({date})")
                elif variation == "incline and decline":
                    lines.append(f"  • incline: {display_details} ({date})")
                    lines.append(f"  • decline: {display_details} ({date})")
                else:
                    lines.append(f"  • {variation}: {display_details} ({date})")
        lines.append("")

    return "\n".join(lines).strip()
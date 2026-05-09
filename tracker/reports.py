"""PR report generation for the workout tracker."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
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


def _parse_weight(details: str) -> float:
    if not details:
        return -1.0
    m = re.search(r"@\s*([0-9]+(?:\.[0-9]+)?(?:\s*\+\s*[0-9]+(?:\.[0-9]+)?)*)(?:\s*[a-z]+)?", details.lower())
    if not m:
        return -1.0
    parts = [p for p in re.split(r"\s*\+\s*", m.group(1)) if p]
    try:
        return float(sum(float(p) for p in parts))
    except ValueError:
        return -1.0


def _parse_reps_sets(details: str) -> tuple[int, int]:
    m = re.search(r"(\d+)x(\d+)", details or "")
    if not m:
        return (-1, -1)
    return int(m.group(1)), int(m.group(2))


def _body_part(exercise: str) -> str:
    name = exercise.lower()
    if any(t in name for t in ["bench press", "pec fly", "chest press", "chest fly", "push up", "pushup"]):
        return "Chest"
    if any(t in name for t in ["lat pull down", "lat pulldown", "row", "pullup", "pull up"]) and "rear delt" not in name:
        return "Back"
    if any(t in name for t in ["shoulder press", "arnold press", "lateral raise", "front raise", "rear delt"]):
        return "Shoulders"
    if any(t in name for t in ["leg press", "leg extension", "leg ext", "leg curl", "hamstring curl", "goblet squat", "goblet squats", "sumo squat", "squat", "calf raise"]):
        return "Legs"
    if any(t in name for t in ["bicep", "tricep", "curl on cable", "preacher curl", "pushdown", "extension", "curl"]) and not any(t in name for t in ["leg curl", "hamstring curl", "calf curl"]):
        return "Arms"
    if any(t in name for t in ["crunch", "abs", "plank", "core"]):
        return "Core"
    return "Other"


def _load_rows(db_path: Path) -> list[PRRow]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT workout_date, exercise, COALESCE(variation, 'default') AS variation, details, raw_text
            FROM workouts WHERE workout_type = 'strength'
            ORDER BY workout_date, id
            """
        ).fetchall()
    return [PRRow(**dict(row)) for row in rows]


def _best_sets(rows: Iterable[PRRow]) -> dict[tuple[str, str], PRRow]:
    best: dict[tuple[str, str], tuple[tuple, PRRow]] = {}
    for row in rows:
        key = (row.exercise, row.variation or "flat")
        score = (_parse_weight(row.details), *_parse_reps_sets(row.details), row.workout_date)
        if key not in best or score > best[key][0]:
            best[key] = (score, row)
    return {k: v[1] for k, v in best.items()}


def _fmt_date(d: str) -> str:
    from datetime import date, datetime
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
    order = [p for p in BODY_PART_ORDER if p in seen] + sorted(p for p in seen if p not in BODY_PART_ORDER)

    lines = [
        "🏋️ Workout PR Summary",
        f"- Body parts tracked: {len(grouped)}",
        f"- Exercises tracked: {len(prs)}",
        "",
    ]
    for body_part in order:
        emoji = BODY_PART_EMOJI.get(body_part, "•")
        lines.append(f"{emoji} {body_part}")
        for exercise in sorted(grouped[body_part]):
            variations = sorted(
                grouped[body_part][exercise],
                key=lambda item: (item[0] not in {"default", "flat"}, 0 if item[0] == "default" else 1 if item[0] == "flat" else 2, item[0]),
            )
            lines.append(f"- {exercise}")
            for variation, row in variations:
                details = row.details.replace("flat; ", "")
                date = _fmt_date(row.workout_date)
                if variation in ("default", ""):
                    lines.append(f"  • {details} ({date})")
                elif variation == "incline and decline":
                    lines.append(f"  • incline: {details} ({date})")
                    lines.append(f"  • decline: {details} ({date})")
                else:
                    lines.append(f"  • {variation}: {details} ({date})")
        lines.append("")

    return "\n".join(lines).strip()

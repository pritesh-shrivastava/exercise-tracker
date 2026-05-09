#!/usr/bin/env python3
"""Print workout PR summaries from the local SQLite database.

The script reports the best logged set for each exercise + variation,
grouped by body part for easier review.
It is intentionally dependency-free so the tracker stays portable.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"
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


def parse_weight(details: str) -> float:
    """Best-effort weight parser for details strings.

    Supports inputs like:
    - "3x15 @ 15kg"
    - "3x15 @ 7.5+7.5 dumbbell"
    - "3x10 @ 20"
    """

    if not details:
        return -1.0

    m = re.search(r"@\s*([0-9]+(?:\.[0-9]+)?(?:\s*\+\s*[0-9]+(?:\.[0-9]+)?)*)(?:\s*[a-z]+)?", details.lower())
    if not m:
        return -1.0

    expr = m.group(1)
    parts = [p for p in re.split(r"\s*\+\s*", expr) if p]
    try:
        return float(sum(float(p) for p in parts))
    except ValueError:
        return -1.0


def parse_reps_sets(details: str) -> tuple[int, int]:
    m = re.search(r"(\d+)x(\d+)", details or "")
    if not m:
        return (-1, -1)
    return int(m.group(1)), int(m.group(2))


def body_part_for_exercise(exercise: str) -> str:
    name = exercise.lower()

    if any(
        token in name
        for token in [
            "bench press",
            "pec fly",
            "chest press",
            "chest fly",
            "push up",
            "pushup",
        ]
    ):
        return "Chest"

    if any(
        token in name
        for token in [
            "lat pull down",
            "lat pulldown",
            "row",
            "pullup",
            "pull up",
        ]
    ) and "rear delt" not in name:
        return "Back"

    if any(
        token in name
        for token in [
            "shoulder press",
            "arnold press",
            "lateral raise",
            "front raise",
            "rear delt",
        ]
    ):
        return "Shoulders"

    if any(
        token in name
        for token in [
            "leg press",
            "leg extension",
            "leg ext",
            "leg curl",
            "hamstring curl",
            "goblet squat",
            "goblet squats",
            "sumo squat",
            "squat",
            "calf raise",
        ]
    ):
        return "Legs"

    if any(
        token in name
        for token in [
            "bicep",
            "tricep",
            "curl on cable",
            "preacher curl",
            "pushdown",
            "extension",
            "curl",
        ]
    ) and not any(token in name for token in ["leg curl", "hamstring curl", "calf curl"]):
        return "Arms"

    if any(token in name for token in ["crunch", "abs", "plank", "core"]):
        return "Core"

    return "Other"


def load_rows(db_path: Path) -> list[PRRow]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT workout_date, exercise, COALESCE(variation, 'default') AS variation, details, raw_text
            FROM workouts
            WHERE workout_type = 'strength'
            ORDER BY workout_date, id
            """
        ).fetchall()

    return [PRRow(**dict(row)) for row in rows]


def best_sets(rows: Iterable[PRRow]) -> dict[tuple[str, str], PRRow]:
    best: dict[tuple[str, str], tuple[tuple[float, int, int, str], PRRow]] = {}
    for row in rows:
        key = (row.exercise, row.variation or "flat")
        weight = parse_weight(row.details)
        sets, reps = parse_reps_sets(row.details)
        score = (weight, reps, sets, row.workout_date)
        if key not in best or score > best[key][0]:
            best[key] = (score, row)
    return {k: v[1] for k, v in best.items()}


def group_by_body_part(prs: dict[tuple[str, str], PRRow]) -> dict[str, dict[str, list[tuple[str, PRRow]]]]:
    grouped: dict[str, dict[str, list[tuple[str, PRRow]]]] = defaultdict(lambda: defaultdict(list))
    for (exercise, variation), row in prs.items():
        body_part = body_part_for_exercise(exercise)
        grouped[body_part][exercise].append((variation, row))
    return grouped


def sort_body_parts(names: Iterable[str]) -> list[str]:
    seen = list(names)
    ordered = [name for name in BODY_PART_ORDER if name in seen]
    ordered.extend(sorted(name for name in seen if name not in BODY_PART_ORDER))
    return ordered


def format_details(details: str) -> str:
    if not details:
        return ""
    text = details.replace("flat; ", "")
    text = text.replace(" @ ", " @ ")
    return text


def format_workout_date(workout_date: str) -> str:
    try:
        from datetime import datetime

        return datetime.strptime(workout_date, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return workout_date


def main() -> int:
    parser = argparse.ArgumentParser(description="Print workout PR summary from SQLite")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to workouts.sqlite")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"No database found at {db_path}")

    rows = load_rows(db_path)
    if not rows:
        print("No strength workouts logged yet.")
        return 0

    prs = best_sets(rows)
    grouped = group_by_body_part(prs)

    print("🏋️ *Workout PR Summary*")
    print(f"- Body parts tracked: {len(grouped)}")
    print(f"- Exercises tracked: {len(prs)}")
    print("")

    for body_part in sort_body_parts(grouped.keys()):
        emoji = BODY_PART_EMOJI.get(body_part, "•")
        print(f"## {emoji} {body_part}")
        for exercise in sorted(grouped[body_part]):
            variations = sorted(grouped[body_part][exercise], key=lambda item: (item[0] not in {"default", "flat"}, 0 if item[0] == "default" else 1 if item[0] == "flat" else 2, item[0]))
            print(f"- {exercise}")
            for variation, row in variations:
                detail_text = format_details(row.details)
                workout_date = format_workout_date(row.workout_date)
                if variation == "default" or not variation:
                    print(f"  - {detail_text} ({workout_date})")
                elif variation == "incline and decline":
                    print(f"  - incline: {detail_text} ({workout_date})")
                    print(f"  - decline: {detail_text} ({workout_date})")
                else:
                    print(f"  - {variation}: {detail_text} ({workout_date})")
        print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

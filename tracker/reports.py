"""PR report generation for the workout tracker."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

BODY_PART_ORDER = ["Chest", "Back", "Shoulders", "Biceps", "Triceps", "Legs", "Core", "Other"]
BODY_PART_EMOJI = {
    "Chest": "🩻",
    "Back": "🧱",
    "Shoulders": "🧢",
    "Biceps": "💪",
    "Triceps": "🔻",
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


def body_part(exercise: str) -> str:
    name = exercise.lower()
    chest = [
        "bench press", "incline press", "pec fly", "chest press", "chest fly",
        "push up", "pushup",
    ]
    back = ["lat pull down", "lat pulldown", "row", "pullup", "pull up", "back extension"]
    back_exclude = ["upright row"]
    shoulders = [
        "shoulder press", "arnold press", "lateral raise", "front raise",
        "rear delt", "face pull", "upright row", "dumbbell shrug", "dumbbell shrugs",
        "shrug", "shrugs",
    ]
    legs = ["leg press", "leg extension", "hamstring curl",
            "goblet squat", "goblet squats", "sumo squat", "squat", "calf raise",
            "lunge", "lunges", "glute kickback", "hip thrust", "kettlebell swing",
            "kettleball swing"]
    biceps = ["bicep", "curl on cable", "preacher curl", "hammer curl", "reverse curl", "curl"]
    biceps_exclude = ["hamstring curl", "calf curl"]
    triceps = ["tricep", "pushdown", "dip", "dips", "overhead extension", "extension"]
    triceps_exclude = ["back extension", "leg extension"]
    if any(t in name for t in chest):
        return "Chest"
    if any(t in name for t in back) and "rear delt" not in name and not any(t in name for t in back_exclude):
        return "Back"
    if any(t in name for t in shoulders):
        return "Shoulders"
    if any(t in name for t in legs):
        return "Legs"
    if any(t in name for t in biceps) and not any(t in name for t in biceps_exclude):
        return "Biceps"
    if any(t in name for t in triceps) and not any(t in name for t in triceps_exclude):
        return "Triceps"
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
        assisted = "assisted" in row.exercise.lower()
        # Assisted movements treat lower assistance weight as better.
        # For all other movements, higher weight remains better.
        if row.weight_kg is None:
            w = float("inf") if assisted else -1.0
        else:
            w = row.weight_kg
        score = ((-w) if assisted else w, row.reps, row.sets, _neg_date(row.workout_date))
        if key not in best or score > best[key][0]:
            best[key] = (score, row)
    return {k: v[1] for k, v in best.items()}


def _neg_date(d: str) -> int:
    """Return negated ordinal so earlier dates rank higher in numeric comparison."""
    try:
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        return -dt.toordinal()
    except ValueError:
        return 0


def _fmt_date(d: str) -> str:
    try:
        pr_date = datetime.strptime(d, "%Y-%m-%d").date()
        age = (date.today() - pr_date).days
        dot = "+" if age <= 14 else "-"
        return f"{dot} {pr_date.strftime('%d %b %Y')}"
    except ValueError:
        return d


def _fmt_performance(row: PRRow) -> str:
    if row.weight_kg is not None:
        w = row.weight_kg
        if row.per_hand:
            half = w / 2
            per_hand_kg = int(half) if half == int(half) else half
            total_str = str(int(w)) if w == int(w) else str(w)
            weight_str = f"{total_str}kg ({per_hand_kg}ea.)"
        else:
            weight_str = f"{int(w) if w == int(w) else w}kg"
        return f"{row.sets}×{row.reps} @ {weight_str}"
    return f"{row.sets}×{row.reps}"


def format_stale_pr_increment_candidates(
    db_path: Path,
    as_of: date | None = None,
    stale_days: int = 30,
    min_reps: int = 15,
) -> str:
    """Weighted PRs old enough and high-rep enough to consider increasing weight."""
    rows = _load_rows(db_path)
    if not rows:
        return ""

    today = as_of or date.today()
    candidates: list[PRRow] = []
    for row in _best_sets(rows).values():
        if row.weight_kg is None or row.reps < min_reps:
            continue
        try:
            pr_date = datetime.strptime(row.workout_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - pr_date).days > stale_days:
            candidates.append(row)

    if not candidates:
        return ""

    part_rank = {part: idx for idx, part in enumerate(BODY_PART_ORDER)}
    candidates.sort(key=lambda row: (
        part_rank.get(body_part(row.exercise), len(part_rank)),
        row.exercise,
        row.variation,
    ))

    lines = [
        f"Stale PRs ready for weight increase (>{stale_days}d, {min_reps}+ reps)",
        "",
    ]
    for row in candidates:
        part = body_part(row.exercise)
        emoji = BODY_PART_EMOJI.get(part, "•")
        variation = f" [{row.variation}]" if row.variation not in ("", "default") else ""
        pr_date_label = datetime.strptime(row.workout_date, "%Y-%m-%d").strftime("%d %b %Y")
        lines.append(f"{emoji}  {row.exercise}{variation} — {_fmt_performance(row)} — PR: {pr_date_label}")
    return "\n".join(lines)


def format_prs_compact(db_path: Path) -> str:
    """One line per exercise: emoji  exercise  [variations]  sets×reps @ weight  date."""
    rows = _load_rows(db_path)
    if not rows:
        return "No strength workouts logged yet."

    prs = _best_sets(rows)
    grouped: dict[str, dict[str, list[tuple[str, PRRow]]]] = defaultdict(lambda: defaultdict(list))
    for (exercise, variation), row in prs.items():
        grouped[body_part(exercise)][exercise].append((variation, row))

    seen = list(grouped.keys())
    order = [p for p in BODY_PART_ORDER if p in seen] + sorted(
        p for p in seen if p not in BODY_PART_ORDER
    )

    _VAR_ORDER = {"default": 0, "flat": 1}
    lines = []
    for part in order:
        emoji = BODY_PART_EMOJI.get(part, "•")
        for exercise in sorted(grouped[part]):
            variations = sorted(
                grouped[part][exercise],
                key=lambda item: (_VAR_ORDER.get(item[0], 2), item[0]),
            )
            # Variations with different PR weights get their own line; variations
            # that share the same weight stay clubbed on one line. (A bare
            # "Lat Pull Down" at 35kg and "[short grip, wide grip]" at 31kg are
            # distinct PRs and should not collapse into one.)
            by_weight: dict[float | None, list[tuple[str, PRRow]]] = defaultdict(list)
            for var, row in variations:
                by_weight[row.weight_kg].append((var, row))
            # Heaviest first; bodyweight (None) last.
            for weight in sorted(
                by_weight,
                key=lambda x: (x is not None, x if x is not None else 0.0),
                reverse=True,
            ):
                group = by_weight[weight]
                # Representative within the weight group: best reps, then sets, then earliest.
                row = max(group, key=lambda item: (
                    item[1].reps, item[1].sets, _neg_date(item[1].workout_date)
                ))[1]
                non_default = [v for v, _ in group if v not in ("default", "")]
                var_str = f"  [{', '.join(non_default)}]" if non_default else ""

                perf = _fmt_performance(row)
                date_str = _fmt_date(row.workout_date)
                lines.append(f"{emoji}  {exercise:<38}{var_str:<28}{perf:<22}{date_str}")

    return "\n".join(lines)

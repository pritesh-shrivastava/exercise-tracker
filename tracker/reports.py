"""PR report generation for the workout tracker."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
    body_part: str = ""


@dataclass(frozen=True)
class PRDisplayRow:
    part: str
    exercise: str
    variation: str
    performance: str
    pr_date: str


@dataclass(frozen=True)
class ProgressionPoint:
    workout_date: str
    performance: str
    weight_kg: float
    sets: int
    reps: int
    per_hand: bool


@dataclass(frozen=True)
class ProgressionSeries:
    part: str
    exercise: str
    variation: str
    points: list[ProgressionPoint]
    pr_points: list[ProgressionPoint]


@dataclass(frozen=True)
class BodyPartActivity:
    part: str
    sessions_14d: int
    entries_14d: int
    last_trained: str | None
    days_since: int | None


def body_part(exercise: str) -> str:
    name = exercise.lower()
    chest = [
        "bench press", "incline press", "pec fly", "chest press", "chest fly",
        "push up", "pushup",
    ]
    back = [
        "lat pull down", "lat pulldown", "pulldown", "row", "pullup", "pull up",
        "back extension", "deadlift",
    ]
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


def row_body_part(exercise: str, stored_body_part: str | None = None) -> str:
    """Return the saved body-part tag when valid, otherwise infer from exercise."""
    if stored_body_part in BODY_PART_ORDER:
        return stored_body_part
    return body_part(exercise)


def _load_rows(db_path: Path) -> list[PRRow]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {row[1] for row in conn.execute("PRAGMA table_info(workouts)")}
        body_part_select = (
            "COALESCE(body_part, '') AS body_part"
            if "body_part" in columns
            else "'' AS body_part"
        )
        rows = conn.execute(
            f"""
            SELECT workout_date, exercise, COALESCE(variation, 'default') AS variation,
                   details, raw_text, COALESCE(sets, 0) AS sets, COALESCE(reps, 0) AS reps,
                   weight_kg, COALESCE(equipment, '') AS equipment,
                   COALESCE(per_hand, 0) AS per_hand, {body_part_select}
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


def _activity_by_body_part(db_path: Path, as_of: date) -> list[BodyPartActivity]:
    start = as_of - timedelta(days=13)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {row[1] for row in conn.execute("PRAGMA table_info(workouts)")}
        body_part_select = (
            "COALESCE(body_part, '') AS body_part"
            if "body_part" in columns
            else "'' AS body_part"
        )
        rows = conn.execute(
            f"""
            SELECT workout_date, exercise, {body_part_select}
            FROM workouts
            WHERE workout_type = 'strength' AND workout_date <= ?
            ORDER BY workout_date, id
            """,
            (as_of.isoformat(),),
        ).fetchall()

    dates_by_part: dict[str, set[str]] = defaultdict(set)
    entries_by_part: dict[str, int] = defaultdict(int)
    last_by_part: dict[str, str] = {}
    for row in rows:
        part = row_body_part(row["exercise"], row["body_part"])
        workout_date = row["workout_date"]
        last_by_part[part] = max(last_by_part.get(part, ""), workout_date)
        try:
            dt = datetime.strptime(workout_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if start <= dt <= as_of:
            dates_by_part[part].add(workout_date)
            entries_by_part[part] += 1

    activity: list[BodyPartActivity] = []
    for part in BODY_PART_ORDER:
        last_trained = last_by_part.get(part)
        days_since: int | None = None
        if last_trained:
            try:
                days_since = (as_of - datetime.strptime(last_trained, "%Y-%m-%d").date()).days
            except ValueError:
                days_since = None
        activity.append(
            BodyPartActivity(
                part=part,
                sessions_14d=len(dates_by_part[part]),
                entries_14d=entries_by_part[part],
                last_trained=last_trained,
                days_since=days_since,
            )
        )
    return activity


def _next_focus(activity: Iterable[BodyPartActivity]) -> list[BodyPartActivity]:
    eligible = [row for row in activity if row.part != "Other"]
    never_trained = [row for row in eligible if row.days_since is None]
    previously_trained = [row for row in eligible if row.days_since is not None]
    stale = sorted(
        previously_trained,
        key=lambda row: (
            row.days_since if row.days_since is not None else 10_000,
            -row.sessions_14d,
            -row.entries_14d,
        ),
        reverse=True,
    )
    never_priority = {"Legs": 0, "Shoulders": 1, "Core": 2, "Biceps": 3, "Triceps": 4}
    never_trained.sort(key=lambda row: (never_priority.get(row.part, 99), BODY_PART_ORDER.index(row.part)))
    return never_trained[:2] + stale + never_trained[2:]


def format_training_advice(db_path: Path, as_of: date | None = None) -> str:
    """DB-backed advisory prompts for training focus."""
    if not db_path.exists():
        return "No database yet."

    rows = _load_rows(db_path)
    if not rows:
        return "No strength workouts logged yet."

    today = as_of or date.today()
    activity = _activity_by_body_part(db_path, today)
    focus = _next_focus(activity)[:4]
    recent_sessions = sum(row.sessions_14d for row in activity)
    recent_entries = sum(row.entries_14d for row in activity)

    lines = [
        "Training coach",
        f"- As of: {today.isoformat()}",
        f"- Last 14 days: {recent_sessions} body-part sessions, {recent_entries} strength entries",
        "",
        "Suggested next focus:",
    ]
    for row in focus:
        if row.last_trained is None:
            status = "no logged strength work yet"
        elif row.days_since == 0:
            status = "trained today"
        elif row.days_since == 1:
            status = "last trained yesterday"
        else:
            status = f"last trained {row.days_since} days ago"
        lines.append(f"- {row.part}: {status}; {row.sessions_14d} sessions / {row.entries_14d} entries in 14d")

    lines.extend(["", "Progression prompts:"])
    progression = format_stale_pr_increment_candidates(db_path, as_of=today)
    if progression:
        candidates = progression.splitlines()[2:5]
        lines.extend(f"- {candidate}" for candidate in candidates)
    else:
        lines.append("- No stale 15+ rep weighted PRs are currently flagged for a weight increase.")

    lines.extend(
        [
            "",
            "Use this as advisory only. Log or edit workouts through the private form "
            "so SQLite remains the source of truth.",
        ]
    )
    return "\n".join(lines)


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
        part_rank.get(row_body_part(row.exercise, row.body_part), len(part_rank)),
        row.exercise,
        row.variation,
    ))

    lines = [
        f"Stale PRs ready for weight increase (>{stale_days}d, {min_reps}+ reps)",
        "",
    ]
    for row in candidates:
        part = row_body_part(row.exercise, row.body_part)
        emoji = BODY_PART_EMOJI.get(part, "•")
        variation = f" [{row.variation}]" if row.variation not in ("", "default") else ""
        pr_date_label = datetime.strptime(row.workout_date, "%Y-%m-%d").strftime("%d %b %Y")
        lines.append(f"{emoji}  {row.exercise}{variation} — {_fmt_performance(row)} — PR: {pr_date_label}")
    return "\n".join(lines)


def format_prs_compact(db_path: Path) -> str:
    """One line per exercise: emoji  exercise  [variations]  sets×reps @ weight  date."""
    display_rows = pr_display_rows(db_path)
    if not display_rows:
        return "No strength workouts logged yet."

    lines = []
    for row in display_rows:
        emoji = BODY_PART_EMOJI.get(row.part, "•")
        var_str = f"  [{row.variation}]" if row.variation else ""
        lines.append(f"{emoji}  {row.exercise:<38}{var_str:<28}{row.performance:<22}{row.pr_date}")

    return "\n".join(lines)


def pr_display_rows(db_path: Path) -> list[PRDisplayRow]:
    """Structured PR display rows, grouped/sorted like compact output."""
    rows = _load_rows(db_path)
    if not rows:
        return []

    prs = _best_sets(rows)
    grouped: dict[str, dict[str, list[tuple[str, PRRow]]]] = defaultdict(lambda: defaultdict(list))
    for (exercise, variation), row in prs.items():
        grouped[row_body_part(exercise, row.body_part)][exercise].append((variation, row))

    seen = list(grouped.keys())
    order = [p for p in BODY_PART_ORDER if p in seen] + sorted(
        p for p in seen if p not in BODY_PART_ORDER
    )

    _VAR_ORDER = {"default": 0, "flat": 1}
    display_rows: list[PRDisplayRow] = []
    for part in order:
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
                variation = ", ".join(non_default)

                perf = _fmt_performance(row)
                date_str = _fmt_date(row.workout_date)
                display_rows.append(PRDisplayRow(part, exercise, variation, perf, date_str))

    return display_rows


def progression_series(db_path: Path, *, min_weighted_entries: int = 3) -> list[ProgressionSeries]:
    """Weighted history by exercise and variation, excluding sparse series."""
    rows = [row for row in _load_rows(db_path) if row.weight_kg is not None]
    if not rows:
        return []

    grouped: dict[tuple[str, str], list[PRRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.exercise, row.variation or "default")].append(row)

    series: list[ProgressionSeries] = []
    for (exercise, variation), group in grouped.items():
        if len(group) < min_weighted_entries:
            continue
        sorted_group = sorted(group, key=lambda row: (row.workout_date, row.exercise, row.variation))
        points = [
            ProgressionPoint(
                workout_date=row.workout_date,
                performance=_fmt_performance(row),
                weight_kg=row.weight_kg if row.weight_kg is not None else 0.0,
                sets=row.sets,
                reps=row.reps,
                per_hand=row.per_hand,
            )
            for row in sorted_group
        ]
        best_weight = float("-inf")
        pr_points: list[ProgressionPoint] = []
        for point in points:
            if point.weight_kg > best_weight:
                pr_points.append(point)
                best_weight = point.weight_kg
        part = row_body_part(exercise, sorted_group[-1].body_part)
        series.append(ProgressionSeries(part, exercise, variation, points, pr_points))

    part_rank = {part: idx for idx, part in enumerate(BODY_PART_ORDER)}
    series.sort(key=lambda item: (
        part_rank.get(item.part, len(part_rank)),
        item.exercise,
        item.variation,
        item.points[-1].workout_date,
    ))
    return series

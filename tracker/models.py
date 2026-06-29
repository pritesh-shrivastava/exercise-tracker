"""Shared workout row models and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class WorkoutRecord:
    workout_type: str
    exercise: str
    variation: str
    details: str
    raw_text: str
    sets: int = 0
    reps: int = 0
    weight_kg: float | None = None
    equipment: str = ""
    per_hand: bool = False
    body_part: str = ""


VALID_VARIATIONS = frozenset({"default", "flat", "incline", "decline", "short grip", "wide grip"})
EQUIPMENT_VALUES = frozenset({
    "dumbbells", "barbell", "machine", "cable", "bodyweight",
    "kettlebell", "smith machine", "band", "other", "",
})
BODY_PART_VALUES = frozenset({"Chest", "Back", "Shoulders", "Biceps", "Triceps", "Legs", "Core", "Other", ""})


def format_details(sets: int, reps: int, weight_kg: float | None) -> str:
    details = f"{sets}x{reps}"
    if weight_kg is None:
        return details
    weight = int(weight_kg) if weight_kg == int(weight_kg) else weight_kg
    return f"{details} @ {weight}kg"


def validate_record(rec: WorkoutRecord) -> None:
    if rec.workout_type != "strength":
        return

    if rec.sets <= 0 or rec.reps <= 0:
        raise ValueError(f"Invalid strength sets/reps: {rec}")
    if rec.weight_kg is not None and rec.weight_kg < 0:
        raise ValueError(f"Negative weight: {rec}")
    if rec.equipment not in EQUIPMENT_VALUES:
        raise ValueError(f"Invalid equipment: {rec.equipment!r}")
    if rec.body_part not in BODY_PART_VALUES:
        raise ValueError(f"Invalid body_part: {rec.body_part!r}")
    if rec.variation in EQUIPMENT_VALUES:
        raise ValueError(f"Invalid variation; Equipment leaked into variation: {rec}")
    if rec.variation not in VALID_VARIATIONS:
        raise ValueError(f"Invalid variation: {rec.variation!r}")
    if rec.per_hand and rec.equipment != "dumbbells":
        raise ValueError(f"per_hand set for non-dumbbell row: {rec}")
    if re.search(r"\bbody\s*(?:wt|weight)\b|\bbodyweight\b", rec.raw_text, re.I):
        if rec.equipment != "bodyweight":
            raise ValueError(f"Bodyweight text did not infer bodyweight: {rec}")
    expected = format_details(rec.sets, rec.reps, rec.weight_kg)
    if rec.details != expected:
        raise ValueError(f"Stale details: {rec.details!r} != {expected!r}")

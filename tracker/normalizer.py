"""Exercise name normalization for the workout tracker.

Keep raw_text intact, but normalize exercise names so stats and search stay clean.
"""

from __future__ import annotations

import re

_STRIP_RE = re.compile(r"[^a-z0-9+\s]")
_SPACE_RE = re.compile(r"\s+")
_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")

_CANONICAL: dict[str, str] = {
    "shoulder press": "Dumbbell Shoulder Press",
    "should press": "Dumbbell Shoulder Press",
    "dumbbell shoulder press": "Dumbbell Shoulder Press",
    "dumbbell tricep extension": "Dumbbell Overhead Tricep Extension",
    "standing dumbbell tricep extension": "Dumbbell Overhead Tricep Extension",
    "dumbbell overhead tricep extension": "Dumbbell Overhead Tricep Extension",
    "bicep curl": "Dumbbell Bicep Curl",
    "dumbbell bicep curl": "Dumbbell Bicep Curl",
    "bicep curl on cable": "Bicep Curl on Cable",
    "bicep preacher curl": "Bicep Preacher Curl",
    "reverse curl on cable": "Reverse Curl on Cable",
    "seated row": "Seated Row machine",
    "horizontal row": "Seated Row machine",
    "horizontal rows": "Seated Row machine",
    "seated horizontal row": "Seated Row machine",
    "seated row machine": "Seated Row machine",
    "horizontal leg press": "Horizontal Leg Press",
    "vertical chest press": "Vertical Chest Press Machine",
    "vertical chest press machine": "Vertical Chest Press Machine",
    "chest press vertical": "Chest Press Vertical",
    "assisted pullup": "Assisted Pull Up",
    "assisted pull up": "Assisted Pull Up",
    "pec fly": "Pec Fly",
    "arnold press": "Arnold Press",
    "lateral raise": "Lateral Raise",
    "front raise": "Front Raise",
    "leg extension": "Leg Extension",
    "leg ext": "Leg Extension",
    "leg curl": "Hamstring Curl",
    "hamstring curl": "Hamstring Curl",
    "leg press": "45 Degree Leg Press",
    "45 degree leg press": "45 Degree Leg Press",
    "sumo squat": "Sumo Squat",
    "abs crunch": "Seated Abs Crunch Machine",
    "seated abs crunch machine": "Seated Abs Crunch Machine",
    "dumbell": "Dumbbell",
    "dumbbell shrug": "Dumbbell Shrug",
    "dumbell shrug": "Dumbbell Shrug",
    "dumbbell shrugs": "Dumbbell Shrugs",
    "dumbell shrugs": "Dumbbell Shrugs",
    "face pull": "Face Pull",
    "cable rope upright row": "Cable Rope Upright Row",
    "bodyweight abs crunch": "Bodyweight Abs Crunch",
    "bodyweight crunch": "Bodyweight Crunch",
    "barbell shrug": "Barbell Shrug",
    "chest supported row": "Chest Supported Row",
}


def _clean(text: str) -> str:
    return _SPACE_RE.sub(" ", _STRIP_RE.sub(" ", text.lower())).strip()


def normalize_exercise(exercise: str, raw_text: str = "") -> str:
    exercise = _TRAILING_PAREN_RE.sub("", exercise).strip()
    ex = _clean(exercise)
    raw = _clean(raw_text)
    combined = f"{ex} {raw}".strip()

    # Normalize "dumbell" -> "dumbbell" in cleaned text
    combined = combined.replace("dumbell", "dumbbell")
    ex = ex.replace("dumbell", "dumbbell")

    if "bench" in combined and ("press" in combined or "presa" in combined):
        return "Barbell Bench Press" if "barbell" in combined else "Dumbbell Bench Press"

    # Typo/synonym fixes that require checking combined (exercise + raw text together)
    if "should press" in combined:
        return "Dumbbell Shoulder Press"
    if "tricep pulldown" in combined or "tricep pushdown" in combined:
        return "Tricep Pushdown"
    if "biceo curl" in combined:
        return "Dumbbell Bicep Curl"
    if "calf rause" in combined:
        return "Calf Raise"

    if "lat pull down" in combined or "lat pulldown" in combined:
        return "Lat Pull Down"

    if "rear delt" in combined or "rear fly" in combined:
        return "Rear Delt Fly"

    if ex in _CANONICAL:
        return _CANONICAL[ex]

    # Strip "dumbbell " prefix before canonical lookup
    if ex.startswith("dumbbell "):
        core = ex[9:]  # len("dumbbell ") = 9
        if core in _CANONICAL:
            return "Dumbbell " + _CANONICAL[core]

    return _SPACE_RE.sub(" ", exercise).strip().title()


def normalize(exercise: str, raw_text: str = "") -> str:
    return normalize_exercise(exercise, raw_text)

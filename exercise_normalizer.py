"""Exercise name normalization for the workout tracker.

Keep raw_text intact, but normalize exercise names so stats and search stay clean.
"""

from __future__ import annotations

import re


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+\s]", " ", text.lower())).strip()


def normalize_exercise(exercise: str, raw_text: str = "") -> str:
    ex = _clean(exercise)
    raw = _clean(raw_text)
    combined = f"{ex} {raw}".strip()

    # Specific typo and synonym fixes first.
    if "should press" in combined:
        return "Shoulder Press"
    if "tricep pulldown" in combined or "tricep pushdown" in combined:
        return "Tricep Pushdown"
    if "biceo curl" in combined:
        return "Bicep Curl"
    if "calf rause" in combined:
        return "Calf Raise"

    # Lat pull-down variants: keep grip if present, otherwise one canonical name.
    if "lat pull down" in combined or "lat pulldown" in combined:
        if "short grip" in combined:
            return "Lat Pull Down (Short Grip)"
        if "wide grip" in combined or re.search(r"\bwide\b", combined):
            return "Lat Pull Down (Wide Grip)"
        return "Lat Pull Down"

    # Rear-delt naming: keep one canonical name across rear fly / rear delt.
    if "rear delt" in combined or "rear fly" in combined:
        return "Rear Delt Fly"

    # Mild cleanup for common formatting issues.
    if ex == "shoulder press" or ex == "should press":
        return "Shoulder Press"
    if ex == "bicep curl":
        return "Bicep Curl"
    if ex == "bicep curl on cable":
        return "Bicep Curl on Cable"
    if ex == "bicep preacher curl":
        return "Bicep Preacher Curl"
    if ex == "reverse curl on cable":
        return "Reverse Curl on Cable"
    if ex == "seated row":
        return "Seated Row"
    if ex == "horizontal rows":
        return "Horizontal Row"
    if ex == "horizontal leg press":
        return "Horizontal Leg Press"
    if ex == "bench press incline":
        return "Bench Press Incline"
    if ex == "chest press vertical":
        return "Chest Press Vertical"
    if ex == "assisted pullup":
        return "Assisted Pullup"
    if ex == "pec fly":
        return "Pec Fly"
    if ex == "arnold press":
        return "Arnold Press"
    if ex == "lateral raise":
        return "Lateral Raise"
    if ex == "front raise":
        return "Front Raise"
    if ex == "leg extension":
        return "Leg Extension"
    if ex == "leg curl":
        return "Leg Curl"
    if ex == "leg press":
        return "Leg Press"
    if ex == "sumo squat":
        return "Sumo Squat"
    if ex == "hamstring curl":
        return "Hamstring Curl"
    if ex == "abs crunch":
        return "Abs Crunch"

    # Default: title-case the cleaned name.
    return re.sub(r"\s+", " ", exercise).strip().title()

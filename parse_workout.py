#!/usr/bin/env python3
"""Parse pasted workout text into a simple structured record.

This is intentionally lightweight so it stays portable across VPS moves.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, asdict

from exercise_normalizer import normalize_exercise


STRENGTH_RE = re.compile(
    r"(?P<exercise>.+?)\s+"
    r"(?P<sets>\d+)\s*x\s*(?P<reps>\d+)"
    r"(?:\s*(?:reps?)?\s*(?:@|with)?\s*(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)?)?",
    re.IGNORECASE,
)

CARDIO_RE = re.compile(
    r"(?:(?P<distance>\d+(?:\.\d+)?)\s*(?P<distance_unit>km|mi|m)\s+)?"
    r"(?:(?P<activity>run|walk|cycling|bike|row|cardio|elliptical|treadmill)\s+)?"
    r"(?P<duration>\d+(?:\.\d+)?)\s*(?P<duration_unit>min|mins|minutes|hr|hrs|hours)"
    r"(?:\s+in\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?))?",
    re.IGNORECASE,
)


@dataclass
class WorkoutRecord:
    workout_type: str
    exercise: str
    variation: str
    details: str
    raw_text: str


def detect_variations(exercise: str, text: str) -> list[str]:
    lowered_text = text.lower()
    lowered_exercise = exercise.lower()
    is_bench = "bench" in lowered_text or "bench" in lowered_exercise
    if not is_bench:
        return ["default"]
    if "flat" in lowered_text:
        return ["flat"]
    has_incline = "incline" in lowered_text
    has_decline = "decline" in lowered_text
    if has_incline and has_decline:
        return ["incline", "decline"]
    if has_incline:
        return ["incline"]
    if has_decline:
        return ["decline"]
    return ["flat"]


def classify_line(line: str) -> list[WorkoutRecord]:
    text = line.strip()
    if not text:
        return [WorkoutRecord("note", "", "flat", "", line)]

    m = STRENGTH_RE.search(text)
    if m:
        exercise = normalize_exercise(m.group("exercise"), text)
        variations = detect_variations(exercise, text)
        sets = m.group("sets")
        reps = m.group("reps")
        weight = m.group("weight")
        unit = (m.group("unit") or "").lower()
        details = f"{sets}x{reps}"
        if weight:
            details += f" @ {weight}{unit}"
        return [WorkoutRecord("strength", exercise, variation, details, line) for variation in variations]

    m = CARDIO_RE.search(text)
    if m:
        activity = (m.group("activity") or "cardio").lower()
        duration = m.group("duration")
        duration_unit = m.group("duration_unit")
        distance = m.group("distance")
        distance_unit = m.group("distance_unit")
        details = f"{duration} {duration_unit}"
        if distance:
            details += f", {distance} {distance_unit}"
        time = m.group("time")
        if time:
            details += f", in {time}"
        return [WorkoutRecord("cardio", activity.title(), "flat", details, line)]

    # fallback: keep raw line, mark as note
    return [WorkoutRecord("note", text[:80], "flat", "", line)]


def main() -> int:
    if len(sys.argv) > 1:
        text = "\n".join(sys.argv[1:])
    else:
        text = sys.stdin.read()

    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        records.extend(asdict(record) for record in classify_line(line))
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

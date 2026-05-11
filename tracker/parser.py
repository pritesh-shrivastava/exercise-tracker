"""Parse pasted workout text into a simple structured record.

This is intentionally lightweight so it stays portable across VPS moves.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass

from tracker.normalizer import normalize_exercise

# Matches: "N x M [@/with weight]" or "N sets x M reps [@/with weight]" or "weight N sets x M reps"
# Also handles "woth" typo for "with"
STRENGTH_RE = re.compile(
    r"(?P<exercise>.+?)\s+"
    r"(?P<sets>\d+)\s*x\s*(?P<reps>\d+)"
    r"(?:\s*(?:reps?)?\s*(?:@|with|woth)\s*(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)?)?",
    re.IGNORECASE,
)

# Matches continuation lines: bare "2 x 15 with 20 kg" (no exercise name)
CONTINUATION_RE = re.compile(
    r"^\s*(?P<sets>\d+)\s*x\s*(?P<reps>\d+)"
    r"(?:\s*(?:reps?)?\s*(?:@|with|woth)\s*(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)?)?\s*$",
    re.IGNORECASE,
)

# Matches: "exercise - weight kg N sets x M reps"
WEIGHT_FIRST_RE = re.compile(
    r"(?P<exercise>.+?)\s+"
    r"(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)?\s+"
    r"(?P<sets>\d+)\s*(?:sets?)?\s*x\s*(?P<reps>\d+)\s*(?:reps?)?",
    re.IGNORECASE,
)

# Matches multi-set within a line: "N x M with W, M set(s) of R rep(s) with W"
# Splits into separate parsed units on commas
MULTI_SET_SPLIT_RE = re.compile(
    r"(?P<sets>\d+)\s*x\s*(?P<reps>\d+)\s*(?:reps?)?\s*(?:@|with|woth)\s*(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)?",
    re.IGNORECASE,
)

# Pattern to detect a comma-separated multi-set line
MULTI_LINE_PATTERN = re.compile(
    r".+,\s*(?:\d+\s+set|set)\s",
    re.IGNORECASE,
)

# Matches "N set(s) of M rep(s) [@/with weight]" (no "x" separator)
MULTI_SET_OF_RE = re.compile(
    r"(?P<sets>\d+)\s+sets?\s+of\s+(?P<reps>\d+)\s*(?:reps?)?\s*(?:@|with|woth)\s*(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)?",
    re.IGNORECASE,
)

# Also matches plain "N M" formats like "1 set of 15 rep with 7.5 kg"
# where the number after "set(s) of" is the reps
MULTI_SET_COMMA_RE = re.compile(
    r",\s*(?:\d+\s+(?:sets?|set)\s+of\s+)?(?P<reps>\d+)\s*(?:reps?)?\s+(?:@|with|woth)\s+(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|lb|lbs)?",
    re.IGNORECASE,
)

CARDIO_RE = re.compile(
    r"(?:(?P<distance>\d+(?:\.\d+)?)\s*(?P<distance_unit>km|mi|m)\s+)?"
    r"(?:(?P<activity>run|walk|cycling|bike|row|cardio|elliptical|treadmill)\s+)?"
    r"(?P<duration>\d+(?:\.\d+)?)\s*(?P<duration_unit>min|mins|minutes|hr|hrs|hours)"
    r"(?:s?\s+in\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?))?",
    re.IGNORECASE,
)

# Strip trailing punctuation/whitespace from exercise names
_TRAILING_JUNK_RE = re.compile(r"[-–—,;\s]+$")

# Words that describe angle/variation, not the exercise itself
_ANGLE_WORDS = re.compile(
    r"\b(incline|decline|flat)\b",
    re.IGNORECASE,
)


_MACHINE_EXERCISES = {
    "chest press", "pec fly", "pec fly machine",
    "lat pull down", "pull down",
    "seated row", "horizontal row",
    "leg press", "horizontal leg press", "vertical leg press",
    "leg curl", "leg extension", "leg ext",
    "hamstring curl", "calf raise",
    "tricep pushdown",
    "bicep preacher curl", "preacher curl",
    "face pull",
    "assisted pullup", "assisted pull up",
    "chest supported row",
    "chest press vertical",
    "rear delt fly",
}

_MACHINE_NAMES = frozenset(_MACHINE_EXERCISES)


def _is_machine_exercise(exercise: str, raw_text: str) -> bool:
    """Check if an exercise name matches a known machine exercise."""
    combined = f"{exercise} {raw_text}".lower()
    return any(
        re.search(rf"\b{re.escape(m)}\b", combined) for m in _MACHINE_NAMES
    )


def infer_equipment(exercise: str, raw_text: str) -> str:
    """Infer equipment type from exercise name and raw text."""
    combined = f"{exercise} {raw_text}".lower()
    if "bodyweight" in combined or combined.strip().startswith("bodyweight"):
        return "bodyweight"
    if "barbell" in combined:
        return "barbell"
    if any(x in combined for x in ["dumbbell", "dumbell", "dumbbell "]):
        return "dumbbells"
    if "kettlebell" in combined or "kettle bell" in combined:
        return "kettlebell"
    if "cable" in combined:
        return "cable"
    if "machine" in combined:
        return "machine"
    if "smith" in combined:
        return "smith machine"
    if _is_machine_exercise(exercise, raw_text):
        return "machine"
    if "band" in combined:
        return "band"
    return "other"


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


def _strip_trailing_junk(name: str) -> str:
    return _TRAILING_JUNK_RE.sub("", name).strip()


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


def _clean_exercise_name(raw_name: str) -> str:
    """Clean an exercise name by stripping angle words and trailing junk."""
    name = _TRAILING_JUNK_RE.sub("", raw_name).strip()
    # Remove angle words (incline, decline, flat) and "and" conjunctions
    # between them from the exercise name
    parts = _ANGLE_WORDS.split(name)
    cleaned = parts[0].strip() if parts else name
    # Also strip trailing "and" or "&"
    cleaned = re.sub(r"\s+(and|&)\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _build_record(exercise: str, text: str, sets_str: str, reps_str: str,
                  weight_str: str | None, unit_str: str | None) -> list[WorkoutRecord]:
    """Build one or more records, splitting if detect_variations returns multiple."""
    exercise = _clean_exercise_name(exercise)
    normalized = normalize_exercise(exercise, text)
    variations = detect_variations(normalized, text)
    unit_s = (unit_str or "").lower()

    sets = int(sets_str)
    reps = int(reps_str)
    equipment = infer_equipment(normalized, text)
    per_hand = False
    weight_kg: float | None = None
    details = f"{sets}x{reps}"

    if weight_str:
        # Handle "X + Y" notation — explicitly per-hand
        parts = [p.strip() for p in weight_str.split("+") if p.strip()]
        try:
            per_hand_weight = sum(float(p) for p in parts)
        except ValueError:
            per_hand_weight = 0.0

        if len(parts) >= 2 or equipment == "dumbbells":
            # "5 + 5 kg" → per_hand=5, total=10
            # "10 kg dumbbell" (single number) → assume per_hand convention
            per_hand = equipment == "dumbbells"
            weight_kg = per_hand_weight * (2 if per_hand else 1)
        else:
            weight_kg = per_hand_weight

    if weight_kg is not None:
        # Format: show int if whole number, float otherwise
        wt_str = str(int(weight_kg)) if weight_kg == int(weight_kg) else str(weight_kg)
        details += f" @ {wt_str}{unit_s}"

    records = []
    for variation in variations:
        records.append(WorkoutRecord(
            "strength", normalized, variation, details, text,
            sets, reps, weight_kg, equipment, per_hand,
        ))
    return records


def classify_line(line: str, *, previous_exercise: str = "") -> list[WorkoutRecord]:
    """Parse a single line into one or more WorkoutRecord instances.

    Args:
        line: The raw text line to parse.
        previous_exercise: The exercise name from the previous line, used for
                           continuation lines (bare sets/reps).

    Returns:
        A list of WorkoutRecord instances.
    """
    text = line.strip()
    if not text:
        return [WorkoutRecord("note", "", "flat", "", line, equipment="other")]

    # --- Continuation line: bare "N x M [@ weight]" with no exercise name ---
    cm = CONTINUATION_RE.match(text)
    if cm and previous_exercise:
        return _build_record(
            previous_exercise, text,
            cm.group("sets"), cm.group("reps"),
            cm.group("weight"), cm.group("unit"),
        )

    # --- Weight-first format: "Exercise - 20 kg 3 sets x 15 reps" ---
    wm = WEIGHT_FIRST_RE.match(text)
    if wm:
        exercise = _strip_trailing_junk(wm.group("exercise"))
        return _build_record(
            exercise, text,
            wm.group("sets"), wm.group("reps"),
            wm.group("weight"), wm.group("unit"),
        )

    # --- Multi-set comma-separated format ---
    # e.g. "Dumbell Shoulder press - 2 x 15 with 5 + 5 kg, 1 set of 15 rep with 7.5 kg"
    if MULTI_LINE_PATTERN.match(text):
        # Extract the exercise prefix (everything before the first sets x reps pattern)
        first_match = STRENGTH_RE.search(text)
        if first_match:
            exercise = _strip_trailing_junk(first_match.group("exercise"))
            # Find all set/rep/weight groups in the text
            all_sets = []
            # First match the standard "N x M" patterns via MULTI_SET_SPLIT_RE
            all_sets.extend(MULTI_SET_SPLIT_RE.findall(text))
            # Then match "N set(s) of M rep(s)" patterns
            all_sets.extend(MULTI_SET_OF_RE.findall(text))
            # Also match comma-separated continuation formats
            for cm in MULTI_SET_COMMA_RE.finditer(text):
                # Check if this comma group also matched one of the other patterns
                already = any(
                    str(cm.group("reps")) == s[1] and str(cm.group("weight")) == s[2]
                    for s in all_sets
                )
                if already:
                    continue
                all_sets.append((str(first_match.group("sets")),  # placeholder sets
                                 cm.group("reps"), cm.group("weight"), cm.group("unit")))
            records = []
            for sets, reps, weight, unit in all_sets:
                records.extend(_build_record(exercise, text, sets, reps, weight, unit))
            if records:
                return records

    # --- Standard strength format ---
    m = STRENGTH_RE.search(text)
    if m:
        return _build_record(
            m.group("exercise"), text,
            m.group("sets"), m.group("reps"),
            m.group("weight"), m.group("unit"),
        )

    # --- Cardio ---
    m2 = CARDIO_RE.search(text)
    if m2:
        activity = (m2.group("activity") or "cardio").lower()
        duration = m2.group("duration")
        duration_unit = m2.group("duration_unit")
        distance = m2.group("distance")
        distance_unit = m2.group("distance_unit")
        details = f"{duration} {duration_unit}"
        if distance:
            details += f", {distance} {distance_unit}"
        time = m2.group("time")
        if time:
            details += f", in {time}"
        return [WorkoutRecord("cardio", activity.title(), "flat", details, line, equipment="other")]

    # fallback: keep raw line, mark as note
    return [WorkoutRecord("note", text[:80], "flat", "", line, equipment="other")]


def classify_lines(text: str) -> list[WorkoutRecord]:
    """Parse multi-line workout text, handling continuation lines.

    Continuation lines (bare "N x M [@ weight]" without an exercise name)
    inherit the exercise name from the previous strength line.
    """
    records = []
    last_exercise = ""
    for line in text.splitlines():
        recs = classify_line(line, previous_exercise=last_exercise)
        records.extend(recs)
        # Track last exercise name for continuation lines
        for r in recs:
            if r.workout_type == "strength" and r.exercise:
                last_exercise = r.exercise
    return records


def main() -> int:
    if len(sys.argv) > 1:
        text = "\n".join(sys.argv[1:])
    else:
        text = sys.stdin.read()

    records = [asdict(record) for record in classify_lines(text)]
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

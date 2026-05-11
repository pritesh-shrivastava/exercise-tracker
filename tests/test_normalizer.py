"""Tests for tracker.normalizer.normalize_exercise."""

import pytest

from tracker.normalizer import normalize_exercise

# --- Bench press ---

def test_bench_press_dumbbell():
    assert normalize_exercise("bench", "bench press 3x5 @ 70kg") == "Dumbbell Bench Press"

def test_bench_press_barbell():
    assert normalize_exercise("bench", "barbell bench press 3x5 @ 70kg") == "Barbell Bench Press"

def test_bench_press_from_exercise_name():
    assert normalize_exercise("bench press", "") == "Dumbbell Bench Press"

def test_bench_press_incline_still_bench():
    # incline bench still has "press" via raw_text → dumbbell bench press
    assert normalize_exercise("bench incline", "bench incline press 3x12 @ 15kg") == "Dumbbell Bench Press"

def test_bench_no_press_falls_through():
    # "bench" without "press" in combined → title-case fallback
    result = normalize_exercise("bench", "bench 3x5 @ 70kg")
    assert result == "Bench"


# --- Typo fixes ---

def test_typo_should_press():
    assert normalize_exercise("should press", "") == "Dumbbell Shoulder Press"

def test_typo_should_press_in_raw():
    assert normalize_exercise("shoulder", "should press 3x10") == "Dumbbell Shoulder Press"

def test_typo_tricep_pulldown():
    assert normalize_exercise("tricep pulldown", "") == "Tricep Pushdown"

def test_typo_tricep_pushdown():
    assert normalize_exercise("tricep pushdown", "") == "Tricep Pushdown"

def test_typo_biceo_curl():
    assert normalize_exercise("biceo curl", "") == "Bicep Curl"

def test_typo_calf_rause():
    assert normalize_exercise("calf rause", "") == "Calf Raise"


# --- Lat pull-down variants ---

def test_lat_pull_down_plain():
    assert normalize_exercise("lat pull down", "") == "Lat Pull Down"

def test_lat_pulldown_no_space():
    assert normalize_exercise("lat pulldown", "") == "Lat Pull Down"

def test_lat_pull_down_short_grip():
    assert normalize_exercise("lat pull down", "lat pull down short grip 3x10") == "Lat Pull Down"

def test_lat_pull_down_wide_grip_explicit():
    assert normalize_exercise("lat pull down", "lat pull down wide grip 3x10") == "Lat Pull Down"

def test_lat_pull_down_wide_word():
    assert normalize_exercise("lat pull down", "lat pull down wide 3x10") == "Lat Pull Down"


# --- Rear delt ---

def test_rear_delt_fly():
    assert normalize_exercise("rear delt", "") == "Rear Delt Fly"

def test_rear_fly():
    assert normalize_exercise("rear fly", "") == "Rear Delt Fly"

def test_rear_delt_in_raw():
    assert normalize_exercise("rear", "rear delt fly 3x15") == "Rear Delt Fly"


# --- Canonical dict lookups ---

@pytest.mark.parametrize("exercise,expected", [
    ("shoulder press", "Dumbbell Shoulder Press"),
    ("bicep curl", "Bicep Curl"),
    ("bicep curl on cable", "Bicep Curl on Cable"),
    ("bicep preacher curl", "Bicep Preacher Curl"),
    ("reverse curl on cable", "Reverse Curl on Cable"),
    ("seated row", "Seated Horizontal Row"),
    ("horizontal rows", "Seated Horizontal Row"),
    ("horizontal leg press", "Horizontal Leg Press"),
    ("chest press vertical", "Chest Press Vertical"),
    ("assisted pullup", "Assisted Pullup"),
    ("pec fly", "Pec Fly"),
    ("arnold press", "Arnold Press"),
    ("lateral raise", "Lateral Raise"),
    ("front raise", "Front Raise"),
    ("leg extension", "Leg Extension"),
    ("leg curl", "Hamstring Curl"),
    ("leg press", "45 Degree Leg Press"),
    ("sumo squat", "Sumo Squat"),
    ("hamstring curl", "Hamstring Curl"),
    ("abs crunch", "Seated Abs Crunch Machine"),
])
def test_canonical(exercise, expected):
    assert normalize_exercise(exercise, "") == expected


# --- Title-case fallback ---

def test_fallback_title_case():
    assert normalize_exercise("goblet squat", "") == "Goblet Squat"

def test_fallback_extra_spaces():
    # extra spaces in input are collapsed to one
    assert normalize_exercise("calf  raise", "") == "Calf Raise"

def test_fallback_unknown_exercise():
    assert normalize_exercise("some weird exercise", "") == "Some Weird Exercise"


# --- Case insensitivity ---

def test_case_insensitive_input():
    assert normalize_exercise("BICEP CURL", "") == "Bicep Curl"

def test_case_insensitive_raw():
    assert normalize_exercise("lat", "LAT PULL DOWN 3x10") == "Lat Pull Down"

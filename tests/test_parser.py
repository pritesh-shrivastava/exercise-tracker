"""Tests for tracker.parser.classify_line."""

import pytest

from tracker.parser import WorkoutRecord, classify_line, classify_lines, validate_record


def test_strength_basic():
    recs = classify_line("squats 3x5 @ 100kg")
    assert len(recs) == 1
    r = recs[0]
    assert r.workout_type == "strength"
    assert r.exercise == "Squats"
    assert r.variation == "default"
    assert r.details == "3x5 @ 100kg"


def test_strength_no_weight():
    recs = classify_line("pullups 3x8")
    assert len(recs) == 1
    assert recs[0].workout_type == "strength"
    assert recs[0].details == "3x8"


def test_bench_flat():
    recs = classify_line("bench 5x5 @ 70kg")
    assert len(recs) == 1
    assert recs[0].variation == "flat"


def test_bench_incline():
    recs = classify_line("bench incline 3x12 @ 15kg")
    assert len(recs) == 1
    assert recs[0].variation == "incline"


def test_bench_decline():
    recs = classify_line("bench decline 3x12 @ 15kg")
    assert len(recs) == 1
    assert recs[0].variation == "decline"


def test_barbell_incline_press_preserves_incline():
    recs = classify_line("Barbell incline press - 3 x 12 - 0 kg")
    assert len(recs) == 1
    assert recs[0].exercise == "Barbell Incline Press"


def test_barbell_zero_weight_is_untracked():
    recs = classify_line("Barbell incline press - 3 x 12 - 0 kg")
    assert len(recs) == 1
    assert recs[0].weight_kg is None
    assert recs[0].details == "3x12"


def test_barbell_empty_bar_weight_is_untracked():
    recs = classify_line("Barbell bench press - 3 x 12 - empty bar")
    assert len(recs) == 1
    assert recs[0].weight_kg is None
    assert recs[0].details == "3x12"


def test_bench_incline_and_decline_splits():
    recs = classify_line("bench incline and decline 3x15 @ 15kg")
    assert len(recs) == 2
    variations = {r.variation for r in recs}
    assert variations == {"incline", "decline"}


def test_bench_incline_and_decline_same_details():
    recs = classify_line("bench incline and decline 3x15 @ 15kg")
    assert recs[0].details == recs[1].details


def test_cardio_duration_only():
    recs = classify_line("20 min zone 2 cardio")
    assert len(recs) == 1
    r = recs[0]
    assert r.workout_type == "cardio"
    assert "20" in r.details


def test_cardio_with_distance():
    # Parser requires a duration unit (min/hr) — "5 km run 28 min" works,
    # "5 km run in 28:30" (no unit) falls through to note.
    recs = classify_line("5 km run 28 min")
    assert len(recs) == 1
    r = recs[0]
    assert r.workout_type == "cardio"
    assert "5" in r.details
    assert "28" in r.details


def test_unknown_line_stored_as_note():
    recs = classify_line("felt tired today")
    assert len(recs) == 1
    assert recs[0].workout_type == "note"


def test_empty_line_is_skipped():
    recs = classify_line("")
    assert len(recs) == 0


def test_raw_text_preserved():
    line = "bench incline 3x12 @ 15kg"
    recs = classify_line(line)
    assert recs[0].raw_text == line


def test_bodywt_infers_bodyweight():
    recs = classify_lines("bodywt squats 3x20")
    for r in recs:
        assert r.exercise == "Bodyweight Squat"
        assert r.equipment == "bodyweight"


def test_body_weight_infers_bodyweight():
    recs = classify_lines("Body weight squats - 3 x 20")
    assert len(recs) == 1
    r = recs[0]
    assert r.exercise == "Bodyweight Squat"
    assert r.equipment == "bodyweight"


def test_kettleball_normalizes_to_kettlebell_and_equipment():
    recs = classify_lines("Kettleball swing - 3 x 15 - 12 kg")
    assert len(recs) == 1
    r = recs[0]
    assert r.exercise == "Kettlebell Swing"
    assert r.equipment == "kettlebell"


def test_bodyweight_suffix_calf_raise_normalizes_to_prefix():
    recs = classify_lines("Calf raise bodyweight - 3 x 15")
    assert len(recs) == 1
    r = recs[0]
    assert r.exercise == "Bodyweight Calf Raise"
    assert r.equipment == "bodyweight"


def test_goblet_single_not_doubled():
    recs = classify_lines("Goblet Squat 2x15 @ 10 kg")
    assert len(recs) == 1
    r = recs[0]
    assert r.weight_kg == 10.0
    assert r.per_hand is False


def test_dumbbell_single_gets_per_hand():
    recs = classify_lines("Dumbbell Shoulder Press 3x10 @ 10 kg")
    assert len(recs) == 1
    r = recs[0]
    assert r.weight_kg == 10.0
    assert r.per_hand is True


def test_dumbbell_plus_gets_per_hand():
    recs = classify_lines("Dumbbell Curl 3x10 @ 5 + 5 kg")
    assert len(recs) == 1
    r = recs[0]
    assert r.weight_kg == 10.0
    assert r.per_hand is True


def test_continuation_inherits_equipment():
    recs = classify_lines("Leg Extension machine 2x15 @ 36kg\n1x15 @ 43kg")
    assert len(recs) == 2
    assert [r.equipment for r in recs] == ["machine", "machine"]


def test_hanstring_typo_infers_machine():
    recs = classify_lines("Hanstring curl - 3 x 15 - 23 kg")
    assert len(recs) == 1
    assert recs[0].exercise == "Hamstring Curl"
    assert recs[0].equipment == "machine"


def test_equipment_never_becomes_variation():
    for raw in ["Seated Row machine 3x12 @ 40kg", "Calf Raise machine 3x15 @ 20kg"]:
        recs = classify_lines(raw)
        for r in recs:
            assert r.variation == "default"


def test_validate_record_passes_good():
    r = WorkoutRecord(
        "strength",
        "Test",
        "default",
        "3x10 @ 50kg",
        "test 3x10 @ 50kg",
        sets=3,
        reps=10,
        weight_kg=50.0,
        equipment="machine",
        per_hand=False,
    )
    validate_record(r)


def test_validate_record_rejects_bad_variation():
    r = WorkoutRecord("strength", "Test", "machine", "3x10", "test", sets=3, reps=10, equipment="machine")
    with pytest.raises(ValueError, match="Invalid variation"):
        validate_record(r)


def test_validate_record_rejects_equipment_leak():
    r = WorkoutRecord("strength", "Test", "dumbbells", "3x10", "test", sets=3, reps=10, equipment="dumbbells")
    with pytest.raises(ValueError, match="Equipment leaked"):
        validate_record(r)


def test_validate_record_rejects_per_hand_non_dumbbell():
    r = WorkoutRecord(
        "strength",
        "Test",
        "default",
        "3x10",
        "test",
        sets=3,
        reps=10,
        weight_kg=20.0,
        equipment="machine",
        per_hand=True,
    )
    with pytest.raises(ValueError, match="per_hand"):
        validate_record(r)

"""Tests for tracker.parser.classify_line."""

from tracker.parser import classify_line


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


def test_empty_line_is_note():
    recs = classify_line("")
    assert len(recs) == 1
    assert recs[0].workout_type == "note"


def test_raw_text_preserved():
    line = "bench incline 3x12 @ 15kg"
    recs = classify_line(line)
    assert recs[0].raw_text == line

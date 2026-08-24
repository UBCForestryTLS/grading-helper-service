from src.services.notices import (
    AI_GRADE_AND_FEEDBACK_NOTICE,
    INSTRUCTOR_FEEDBACK_NOTICE,
    INSTRUCTOR_GRADE_AND_FEEDBACK_NOTICE,
    INSTRUCTOR_GRADE_NOTICE,
    generate_ai_notice,
)


def test_no_overrides_returns_ai_notice():
    result = generate_ai_notice(
        ai_grade=80.0,
        ai_feedback="Good work.",
        instructor_grade=None,
        instructor_feedback=None,
    )

    assert result == AI_GRADE_AND_FEEDBACK_NOTICE


def test_grade_override_returns_instructor_grade_notice():
    result = generate_ai_notice(
        ai_grade=80.0,
        ai_feedback="Good work.",
        instructor_grade=85.0,
        instructor_feedback=None,
    )

    assert result == INSTRUCTOR_GRADE_NOTICE


def test_grade_and_feedback_override_returns_combined_notice():
    result = generate_ai_notice(
        ai_grade=80.0,
        ai_feedback="Good work.",
        instructor_grade=85.0,
        instructor_feedback="Excellent work.",
    )

    assert result == INSTRUCTOR_GRADE_AND_FEEDBACK_NOTICE


def test_feedback_only_override_returns_instructor_feedback_notice():
    result = generate_ai_notice(
        ai_grade=80.0,
        ai_feedback="Good work.",
        instructor_grade=None,
        instructor_feedback="Excellent work.",
    )

    assert result == INSTRUCTOR_FEEDBACK_NOTICE


def test_same_grade_value_still_counts_as_grade_override():
    result = generate_ai_notice(
        ai_grade=80.0,
        ai_feedback="Good work.",
        instructor_grade=80.0,
        instructor_feedback=None,
    )

    assert result == INSTRUCTOR_GRADE_NOTICE


def test_empty_instructor_feedback_does_not_count_as_override():
    result = generate_ai_notice(
        ai_grade=80.0,
        ai_feedback="Good work.",
        instructor_grade=None,
        instructor_feedback="",
    )

    assert result == AI_GRADE_AND_FEEDBACK_NOTICE


def test_whitespace_instructor_feedback_does_not_count_as_override():
    result = generate_ai_notice(
        ai_grade=80.0,
        ai_feedback="Good work.",
        instructor_grade=None,
        instructor_feedback="   ",
    )

    assert result == AI_GRADE_AND_FEEDBACK_NOTICE

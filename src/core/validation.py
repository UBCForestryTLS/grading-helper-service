# src/core/validation.py


def validate_grade(grade: float, points_possible: float) -> str | None:
    """Returns an error message if invalid, None if valid."""
    if grade < 0:
        return "Grade cannot be negative."
    if grade > points_possible:  # although some times proffs give extra points...
        return f"Grade cannot exceed {points_possible} points."
    return None

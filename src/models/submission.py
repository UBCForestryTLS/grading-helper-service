"""Pydantic models for individual grading submissions."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


class Submission(BaseModel):
    """A single submission to be graded — one student answer to one question."""

    submission_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    question_id: int
    question_name: str
    question_type: str
    question_text: str
    points_possible: float
    student_answer: str
    canvas_points: float
    correct_answers: list[str]
    canvas_user_id: str = ""
    quiz_submission_id: int = 0
    attempt: int = 1
    ai_grade: float | None = None
    ai_feedback: str | None = None
    ai_graded_at: datetime | None = None
    instructor_grade: float | None = None
    instructor_feedback: str | None = None
    overridden_by: str | None = None
    overridden_at: datetime | None = None

    @computed_field
    @property
    def effective_grade(self) -> float | None:
        if self.instructor_grade:
            return self.instructor_grade

        return self.ai_grade

    @computed_field
    @property
    def effective_feedback(self) -> str | None:
        if self.instructor_feedback:
            return self.instructor_feedback

        return self.ai_feedback

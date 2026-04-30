"""Pydantic models for parsing Canvas quiz JSON exports."""

from pydantic import BaseModel


class CanvasAnswer(BaseModel):
    """A single answer option for a Canvas question."""

    id: int
    text: str
    weight: float
    comments: str = ""
    blank_id: str | None = None


class CanvasSubmission(BaseModel):
    """A single student submission for a Canvas question."""

    answer: str
    points: float


class CanvasQuestion(BaseModel):
    """A Canvas quiz question with its answers and student submissions."""

    id: int
    quiz_id: int
    question_name: str
    question_type: str
    question_text: str
    points_possible: float
    answers: list[CanvasAnswer]
    submissions: list[CanvasSubmission]


class CanvasQuizExport(BaseModel):
    """Top-level model for a Canvas quiz JSON export.

    Canvas exports organize questions by type. This model captures the two
    question types we support and provides a unified `all_questions` accessor.
    """

    short_answer_question: list[CanvasQuestion] = []
    fill_in_multiple_blanks_question: list[CanvasQuestion] = []

    @property
    def all_questions(self) -> list[CanvasQuestion]:
        return self.short_answer_question + self.fill_in_multiple_blanks_question

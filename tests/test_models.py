"""Tests for Pydantic data models."""

from uuid import UUID

import pytest

from src.models.canvas import (
    CanvasAnswer,
    CanvasQuestion,
    CanvasQuizExport,
    CanvasSubmission,
)
from src.models.grading_job import GradingJob, GradingJobCreate, JobStatus
from src.models.submission import Submission


class TestCanvasModels:
    def test_canvas_answer_basic(self):
        answer = CanvasAnswer(id=1, text="Answer text", weight=100)
        assert answer.id == 1
        assert answer.text == "Answer text"
        assert answer.weight == 100
        assert answer.comments == ""
        assert answer.blank_id is None

    def test_canvas_answer_with_blank_id(self):
        answer = CanvasAnswer(id=1, text="tree", weight=100, blank_id="blank1")
        assert answer.blank_id == "blank1"

    def test_canvas_submission(self):
        sub = CanvasSubmission(answer="My answer", points=5.0)
        assert sub.answer == "My answer"
        assert sub.points == 5.0

    def test_canvas_question(self):
        q = CanvasQuestion(
            id=101,
            quiz_id=50,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What is X?",
            points_possible=10.0,
            answers=[CanvasAnswer(id=1, text="X", weight=100)],
            submissions=[CanvasSubmission(answer="X", points=10.0)],
        )
        assert q.id == 101
        assert len(q.answers) == 1
        assert len(q.submissions) == 1

    def test_canvas_quiz_export_from_dict(self, sample_canvas_data):
        export = CanvasQuizExport.model_validate(sample_canvas_data)
        assert len(export.short_answer_question) == 1
        assert len(export.fill_in_multiple_blanks_question) == 0

    def test_canvas_quiz_export_all_questions(self, sample_canvas_data):
        export = CanvasQuizExport.model_validate(sample_canvas_data)
        assert len(export.all_questions) == 1
        assert export.all_questions[0].question_name == "Q1"

    def test_canvas_quiz_export_empty(self):
        export = CanvasQuizExport.model_validate({})
        assert len(export.all_questions) == 0

    def test_canvas_quiz_export_invalid_data(self):
        with pytest.raises(Exception):
            CanvasQuizExport.model_validate(
                {"short_answer_question": [{"bad": "data"}]}
            )


class TestGradingJobModels:
    def test_grading_job_defaults(self):
        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Test Job")
        assert isinstance(job.job_id, UUID)
        assert job.status == JobStatus.PENDING
        assert job.total_questions == 0
        assert job.total_submissions == 0
        assert job.error_message is None

    def test_grading_job_with_values(self):
        job = GradingJob(
            course_id="C100",
            quiz_id="Q50",
            job_name="Test Job",
            status=JobStatus.COMPLETED,
            total_questions=5,
            total_submissions=25,
        )
        assert job.status == JobStatus.COMPLETED
        assert job.total_questions == 5
        assert job.total_submissions == 25

    def test_job_status_enum(self):
        assert JobStatus.PENDING == "PENDING"
        assert JobStatus.PROCESSING == "PROCESSING"
        assert JobStatus.COMPLETED == "COMPLETED"
        assert JobStatus.FAILED == "FAILED"

    def test_grading_job_create(self):
        create = GradingJobCreate(
            course_id="C100",
            quiz_id="Q50",
            job_name="Test Job",
            canvas_data={"short_answer_question": []},
        )
        assert create.course_id == "C100"
        assert create.canvas_data == {"short_answer_question": []}


class TestSubmissionModel:
    def test_submission_defaults(self):
        sub = Submission(
            job_id=UUID("12345678-1234-5678-1234-567812345678"),
            question_id=101,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What is X?",
            points_possible=5.0,
            student_answer="My answer",
            canvas_points=5.0,
            correct_answers=["X", "Y"],
        )
        assert isinstance(sub.submission_id, UUID)
        assert sub.ai_grade is None
        assert sub.ai_feedback is None
        assert sub.ai_graded_at is None

    def test_submission_with_ai_fields(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        sub = Submission(
            job_id=UUID("12345678-1234-5678-1234-567812345678"),
            question_id=101,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What is X?",
            points_possible=5.0,
            student_answer="My answer",
            canvas_points=5.0,
            correct_answers=["X"],
            ai_grade=4.5,
            ai_feedback="Good answer",
            ai_graded_at=now,
        )
        assert sub.ai_grade == 4.5
        assert sub.ai_feedback == "Good answer"
        assert sub.ai_graded_at == now

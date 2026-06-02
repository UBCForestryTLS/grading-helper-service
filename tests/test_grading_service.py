"""Tests for the GradingService."""

import json
from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

from src.models.grading_job import GradingJob, JobStatus
from src.models.submission import Submission
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository
from src.services.grading import GradingService


def _make_submission(job_id=None, **kwargs):
    defaults = dict(
        job_id=job_id or uuid4(),
        question_id=101,
        question_name="Q1",
        question_type="short_answer_question",
        question_text="What is photosynthesis?",
        points_possible=5.0,
        student_answer="Plants use sunlight to make food",
        canvas_points=5.0,
        correct_answers=["The process by which plants convert light to energy"],
    )
    defaults.update(kwargs)
    return Submission(**defaults)


def _bedrock_response(grade, feedback):
    body = json.dumps(
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"grade": grade, "feedback": feedback}),
                }
            ]
        }
    )
    stream = BytesIO(body.encode())
    return {"body": stream}


class TestGradeJob:
    def test_grade_job_success(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)

        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Test")
        job_repo.create(job)

        sub = _make_submission(job_id=job.job_id)
        sub_repo.batch_create([sub])

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = _bedrock_response(4.0, "Good answer")

        service = GradingService(
            job_repo=job_repo, sub_repo=sub_repo, bedrock_client=mock_bedrock
        )
        service.grade_job(job.job_id)

        updated_job = job_repo.get(job.job_id)
        assert updated_job.status == JobStatus.COMPLETED

        subs = sub_repo.list_by_job(job.job_id)
        assert len(subs) == 1
        assert subs[0].ai_grade == 4.0
        assert subs[0].ai_feedback == "Good answer"
        assert subs[0].ai_graded_at is not None

    def test_grade_job_empty_submissions(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)

        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Empty")
        job_repo.create(job)

        mock_bedrock = MagicMock()
        service = GradingService(
            job_repo=job_repo, sub_repo=sub_repo, bedrock_client=mock_bedrock
        )
        service.grade_job(job.job_id)

        updated_job = job_repo.get(job.job_id)
        assert updated_job.status == JobStatus.COMPLETED
        mock_bedrock.invoke_model.assert_not_called()

    def test_grade_job_partial_failure(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)

        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Partial")
        job_repo.create(job)

        sub1 = _make_submission(job_id=job.job_id, student_answer="Good answer")
        sub2 = _make_submission(job_id=job.job_id, student_answer="Bad answer")
        sub_repo.batch_create([sub1, sub2])

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _bedrock_response(5.0, "Perfect")
            raise RuntimeError("Bedrock error")

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = side_effect

        service = GradingService(
            job_repo=job_repo, sub_repo=sub_repo, bedrock_client=mock_bedrock
        )
        service.grade_job(job.job_id)

        updated_job = job_repo.get(job.job_id)
        assert updated_job.status == JobStatus.FAILED
        assert "Bedrock error" in updated_job.error_message

    def test_cancel_pending_job(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)

        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="To Cancel")
        job_repo.create(job)

        result = job_repo.cancel(job.job_id)

        assert result is not None
        assert result.status == JobStatus.CANCELLED
        fetched = job_repo.get(job.job_id)
        assert fetched.status == JobStatus.CANCELLED

    def test_cancel_processing_job(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)

        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Processing Cancel")
        job_repo.create(job)
        job_repo.update_status(job.job_id, JobStatus.PROCESSING)

        result = job_repo.cancel(job.job_id)

        assert result is not None
        assert result.status == JobStatus.CANCELLED

    def test_cancel_completed_job_returns_none(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)

        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Already Done")
        job_repo.create(job)
        job_repo.update_status(job.job_id, JobStatus.COMPLETED)

        result = job_repo.cancel(job.job_id)

        assert result is None
        fetched = job_repo.get(job.job_id)
        assert fetched.status == JobStatus.COMPLETED

    def test_cancel_nonexistent_job_returns_none(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)

        result = job_repo.cancel(uuid4())

        assert result is None

    def test_cancel_stops_grading_loop(self, dynamodb_table):
        """Cancelling mid-flight causes grade_job to exit without marking COMPLETED."""
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)

        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Cancel Mid Grade")
        job_repo.create(job)

        sub1 = _make_submission(job_id=job.job_id)
        sub2 = _make_submission(job_id=job.job_id)
        sub_repo.batch_create([sub1, sub2])

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                job_repo.cancel(job.job_id)
                return _bedrock_response(3.0, "OK")
            return _bedrock_response(5.0, "Great")

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = side_effect

        service = GradingService(
            job_repo=job_repo, sub_repo=sub_repo, bedrock_client=mock_bedrock
        )
        service.grade_job(job.job_id)

        updated_job = job_repo.get(job.job_id)
        assert updated_job.status == JobStatus.CANCELLED


class TestBuildPrompt:
    def test_build_prompt_contains_question_info(self):
        service = GradingService()
        sub = _make_submission()
        prompt = service._build_prompt(sub)

        assert "What is photosynthesis?" in prompt
        assert "short_answer_question" in prompt
        assert "5.0" in prompt
        assert "Plants use sunlight to make food" in prompt
        assert "The process by which plants convert light to energy" in prompt

    def test_build_prompt_no_correct_answers(self):
        service = GradingService()
        sub = _make_submission(correct_answers=[])
        prompt = service._build_prompt(sub)

        assert "None provided" in prompt


class TestParseResponse:
    def test_parse_response_valid(self):
        service = GradingService()
        response = {"content": [{"text": '{"grade": 4.5, "feedback": "Well done"}'}]}
        grade, feedback = service._parse_response(response, 5.0)
        assert grade == 4.5
        assert feedback == "Well done"

    def test_parse_response_markdown_wrapped(self):
        service = GradingService()
        response = {
            "content": [
                {"text": '```json\n{"grade": 3.0, "feedback": "Partial credit"}\n```'}
            ]
        }
        grade, feedback = service._parse_response(response, 5.0)
        assert grade == 3.0
        assert feedback == "Partial credit"

    def test_parse_response_clamps_grade(self):
        service = GradingService()
        response = {"content": [{"text": '{"grade": 10.0, "feedback": "Overgraded"}'}]}
        grade, feedback = service._parse_response(response, 5.0)
        assert grade == 5.0

    def test_parse_response_clamps_negative(self):
        service = GradingService()
        response = {"content": [{"text": '{"grade": -1.0, "feedback": "Negative"}'}]}
        grade, feedback = service._parse_response(response, 5.0)
        assert grade == 0.0

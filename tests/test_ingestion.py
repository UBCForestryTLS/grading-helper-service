"""Tests for the ingestion service."""

import pytest

from src.models.grading_job import JobStatus
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository
from src.services.ingestion import IngestionService


class TestIngestionService:
    def test_ingest_creates_job(self, dynamodb_table, sample_canvas_data):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest("C100", "Q50", "Test Job", sample_canvas_data)

        assert job.course_id == "C100"
        assert job.quiz_id == "Q50"
        assert job.job_name == "Test Job"
        assert job.status == JobStatus.PENDING
        assert job.total_questions == 1
        assert job.total_submissions == 2

    def test_ingest_persists_job(self, dynamodb_table, sample_canvas_data):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest("C100", "Q50", "Test Job", sample_canvas_data)

        persisted = job_repo.get(job.job_id)
        assert persisted is not None
        assert persisted.job_id == job.job_id

    def test_ingest_creates_submissions(self, dynamodb_table, sample_canvas_data):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest("C100", "Q50", "Test Job", sample_canvas_data)

        subs = sub_repo.list_by_job(job.job_id)
        assert len(subs) == 2
        answers = {s.student_answer for s in subs}
        assert "Plants use sunlight to make food" in answers
        assert "I don't know" in answers

    def test_ingest_extracts_correct_answers(self, dynamodb_table, sample_canvas_data):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest("C100", "Q50", "Test Job", sample_canvas_data)

        subs = sub_repo.list_by_job(job.job_id)
        for sub in subs:
            assert len(sub.correct_answers) == 2
            assert (
                "The process by which plants convert light to energy"
                in sub.correct_answers
            )
            assert "Converting sunlight into food" in sub.correct_answers

    def test_ingest_preserves_question_metadata(
        self, dynamodb_table, sample_canvas_data
    ):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest("C100", "Q50", "Test Job", sample_canvas_data)

        subs = sub_repo.list_by_job(job.job_id)
        for sub in subs:
            assert sub.question_id == 101
            assert sub.question_name == "Q1"
            assert sub.question_type == "short_answer_question"
            assert sub.points_possible == 5.0

    def test_ingest_empty_export(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest("C100", "Q50", "Empty Job", {})

        assert job.total_questions == 0
        assert job.total_submissions == 0
        subs = sub_repo.list_by_job(job.job_id)
        assert subs == []

    def test_ingest_invalid_data_raises(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        with pytest.raises(Exception):
            service.ingest(
                "C100",
                "Q50",
                "Bad Job",
                {"short_answer_question": [{"bad": "data"}]},
            )

    def test_ingest_multiple_question_types(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        data = {
            "short_answer_question": [
                {
                    "id": 101,
                    "quiz_id": 50,
                    "question_name": "Q1",
                    "question_type": "short_answer_question",
                    "question_text": "What is X?",
                    "points_possible": 5.0,
                    "answers": [{"id": 1, "text": "X", "weight": 100}],
                    "submissions": [{"answer": "X", "points": 5.0}],
                }
            ],
            "fill_in_multiple_blanks_question": [
                {
                    "id": 102,
                    "quiz_id": 50,
                    "question_name": "Q2",
                    "question_type": "fill_in_multiple_blanks_question",
                    "question_text": "Fill in [blank1]",
                    "points_possible": 3.0,
                    "answers": [
                        {"id": 2, "text": "tree", "weight": 100, "blank_id": "blank1"},
                    ],
                    "submissions": [{"answer": "tree", "points": 3.0}],
                }
            ],
        }

        job = service.ingest("C100", "Q50", "Multi-type Job", data)
        assert job.total_questions == 2
        assert job.total_submissions == 2

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

    def test_ingest_empty_export_raises(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        with pytest.raises(ValueError, match="No gradable submissions found"):
            service.ingest("C100", "Q50", "Empty Job", {})

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


class TestIngestionServiceFromCanvasAPI:
    """Tests for IngestionService.ingest_from_canvas_api()."""

    QUESTIONS = [
        {
            "id": 101,
            "question_name": "Q1",
            "question_type": "short_answer_question",
            "question_text": "What is photosynthesis?",
            "points_possible": 5.0,
            "answers": [
                {
                    "id": 1,
                    "answer_text": "Process of converting light to energy",
                    "answer_weight": 100,
                },
                {
                    "id": 2,
                    "answer_text": "Making food from sunlight",
                    "answer_weight": 100,
                },
            ],
        }
    ]

    QUIZ_SUBMISSIONS = [
        {"id": 201, "user_id": 501, "attempt": 1, "workflow_state": "complete"},
        {"id": 202, "user_id": 502, "attempt": 1, "workflow_state": "complete"},
    ]

    ANSWERS_BY_USER = {
        "501": [{"question_id": 101, "answer": "Plants use sunlight to make food"}],
        "502": [{"question_id": 101, "answer": "I don't know"}],
    }

    def test_creates_job_with_correct_counts(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "API Job",
            self.QUESTIONS,
            self.QUIZ_SUBMISSIONS,
            self.ANSWERS_BY_USER,
        )

        assert job.course_id == "C100"
        assert job.quiz_id == "Q50"
        assert job.total_questions == 1
        assert job.total_submissions == 2

    def test_stores_canvas_user_id_on_submissions(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "API Job",
            self.QUESTIONS,
            self.QUIZ_SUBMISSIONS,
            self.ANSWERS_BY_USER,
        )

        subs = sub_repo.list_by_job(job.job_id)
        user_ids = {s.canvas_user_id for s in subs}
        assert "501" in user_ids
        assert "502" in user_ids

    def test_maps_student_answers_to_questions(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "API Job",
            self.QUESTIONS,
            self.QUIZ_SUBMISSIONS,
            self.ANSWERS_BY_USER,
        )

        subs = sub_repo.list_by_job(job.job_id)
        answers = {s.student_answer for s in subs}
        assert "Plants use sunlight to make food" in answers
        assert "I don't know" in answers

    def test_extracts_correct_answers_from_answer_weight(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "API Job",
            self.QUESTIONS,
            self.QUIZ_SUBMISSIONS,
            self.ANSWERS_BY_USER,
        )

        subs = sub_repo.list_by_job(job.job_id)
        for sub in subs:
            assert "Process of converting light to energy" in sub.correct_answers
            assert "Making food from sunlight" in sub.correct_answers

    def test_skips_non_gradable_question_types(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        questions_with_mc = self.QUESTIONS + [
            {
                "id": 999,
                "question_name": "MC",
                "question_type": "multiple_choice_question",
                "question_text": "Pick one",
                "points_possible": 2.0,
                "answers": [],
            }
        ]
        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "API Job",
            questions_with_mc,
            self.QUIZ_SUBMISSIONS,
            self.ANSWERS_BY_USER,
        )

        assert job.total_questions == 1  # only short_answer_question counted

    def test_includes_essay_questions(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        essay_questions = [
            {
                "id": 201,
                "question_name": "Essay Q1",
                "question_type": "essay_question",
                "question_text": "Explain photosynthesis.",
                "points_possible": 4.0,
                "answers": [],  # essay questions have no model answers
            }
        ]
        quiz_submissions = [
            {"id": 301, "user_id": 601, "attempt": 1, "workflow_state": "complete"}
        ]
        answers_by_user = {
            "601": [{"question_id": 201, "answer": "Plants convert light to energy."}]
        }

        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "Essay Job",
            essay_questions,
            quiz_submissions,
            answers_by_user,
        )

        assert job.total_questions == 1
        subs = sub_repo.list_by_job(job.job_id)
        assert len(subs) == 1
        assert subs[0].question_type == "essay_question"
        assert subs[0].correct_answers == []
        assert subs[0].student_answer == "Plants convert light to energy."

    def test_stores_quiz_submission_id_and_attempt(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        quiz_submissions = [
            {"id": 201, "user_id": 501, "attempt": 2, "workflow_state": "complete"}
        ]
        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "API Job",
            self.QUESTIONS,
            quiz_submissions,
            {"501": [{"question_id": 101, "answer": "Sunlight conversion"}]},
        )

        subs = sub_repo.list_by_job(job.job_id)
        assert subs[0].quiz_submission_id == 201
        assert subs[0].attempt == 2

    def test_quiz_submission_id_defaults_to_zero_when_missing(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        # QUIZ_SUBMISSIONS has no "attempt" key — should default to 1
        job = service.ingest_from_canvas_api(
            "C100",
            "Q50",
            "API Job",
            self.QUESTIONS,
            self.QUIZ_SUBMISSIONS,
            self.ANSWERS_BY_USER,
        )

        subs = sub_repo.list_by_job(job.job_id)
        for sub in subs:
            assert sub.quiz_submission_id in {201, 202}
            assert sub.attempt == 1

    def test_empty_submissions_raises(self, dynamodb_table):
        job_repo = GradingJobRepository(table=dynamodb_table)
        sub_repo = SubmissionRepository(table=dynamodb_table)
        service = IngestionService(job_repo=job_repo, sub_repo=sub_repo)

        with pytest.raises(ValueError, match="No gradable submissions found"):
            service.ingest_from_canvas_api(
                "C100", "Q50", "Empty Job", self.QUESTIONS, [], {}
            )

"""Tests for DynamoDB repository layer."""

from uuid import uuid4

from src.models.grading_job import GradingJob, JobStatus
from src.models.submission import Submission
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository


class TestGradingJobRepository:
    def test_create_and_get(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Test Job")
        repo.create(job)

        result = repo.get(job.job_id)
        assert result is not None
        assert result.job_id == job.job_id
        assert result.course_id == "C100"
        assert result.quiz_id == "Q50"
        assert result.job_name == "Test Job"
        assert result.status == JobStatus.PENDING

    def test_get_nonexistent(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        result = repo.get(uuid4())
        assert result is None

    def test_list_by_course(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        job1 = GradingJob(course_id="C100", quiz_id="Q1", job_name="Job 1")
        job2 = GradingJob(course_id="C100", quiz_id="Q2", job_name="Job 2")
        job3 = GradingJob(course_id="C200", quiz_id="Q3", job_name="Job 3")
        repo.create(job1)
        repo.create(job2)
        repo.create(job3)

        results = repo.list_by_course("C100")
        assert len(results) == 2
        job_ids = {j.job_id for j in results}
        assert job1.job_id in job_ids
        assert job2.job_id in job_ids

    def test_list_by_course_empty(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        results = repo.list_by_course("NONEXISTENT")
        assert results == []

    def test_list_by_status(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        job1 = GradingJob(
            course_id="C100",
            quiz_id="Q1",
            job_name="Job 1",
            status=JobStatus.PENDING,
        )
        job2 = GradingJob(
            course_id="C100",
            quiz_id="Q2",
            job_name="Job 2",
            status=JobStatus.COMPLETED,
        )
        repo.create(job1)
        repo.create(job2)

        pending = repo.list_by_status(JobStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].job_id == job1.job_id

        completed = repo.list_by_status(JobStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].job_id == job2.job_id

    def test_update_status(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Test Job")
        repo.create(job)

        updated = repo.update_status(job.job_id, JobStatus.PROCESSING)
        assert updated is not None
        assert updated.status == JobStatus.PROCESSING

        # Verify GSI2 was updated
        processing = repo.list_by_status(JobStatus.PROCESSING)
        assert len(processing) == 1
        pending = repo.list_by_status(JobStatus.PENDING)
        assert len(pending) == 0

    def test_update_status_with_error(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Test Job")
        repo.create(job)

        updated = repo.update_status(
            job.job_id, JobStatus.FAILED, error_message="Something went wrong"
        )
        assert updated is not None
        assert updated.status == JobStatus.FAILED
        assert updated.error_message == "Something went wrong"

    def test_roundtrip_preserves_all_fields(self, dynamodb_table):
        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(
            course_id="C100",
            quiz_id="Q50",
            job_name="Test Job",
            total_questions=5,
            total_submissions=25,
        )
        repo.create(job)

        result = repo.get(job.job_id)
        assert result.total_questions == 5
        assert result.total_submissions == 25
        assert result.created_at == job.created_at
        assert result.updated_at == job.updated_at


class TestSubmissionRepository:
    def test_batch_create_and_list(self, dynamodb_table):
        repo = SubmissionRepository(table=dynamodb_table)
        job_id = uuid4()
        subs = [
            Submission(
                job_id=job_id,
                question_id=101,
                question_name="Q1",
                question_type="short_answer_question",
                question_text="What is X?",
                points_possible=5.0,
                student_answer=f"Answer {i}",
                canvas_points=float(i),
                correct_answers=["X"],
            )
            for i in range(3)
        ]
        repo.batch_create(subs)

        results = repo.list_by_job(job_id)
        assert len(results) == 3
        answers = {r.student_answer for r in results}
        assert answers == {"Answer 0", "Answer 1", "Answer 2"}

    def test_list_by_job_empty(self, dynamodb_table):
        repo = SubmissionRepository(table=dynamodb_table)
        results = repo.list_by_job(uuid4())
        assert results == []

    def test_get_single_submission(self, dynamodb_table):
        repo = SubmissionRepository(table=dynamodb_table)
        job_id = uuid4()
        sub = Submission(
            job_id=job_id,
            question_id=101,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What is X?",
            points_possible=5.0,
            student_answer="My answer",
            canvas_points=5.0,
            correct_answers=["X", "Y"],
        )
        repo.batch_create([sub])

        result = repo.get(job_id, sub.submission_id)
        assert result is not None
        assert result.submission_id == sub.submission_id
        assert result.student_answer == "My answer"
        assert result.points_possible == 5.0
        assert result.canvas_points == 5.0
        assert result.correct_answers == ["X", "Y"]

    def test_get_nonexistent(self, dynamodb_table):
        repo = SubmissionRepository(table=dynamodb_table)
        result = repo.get(uuid4(), uuid4())
        assert result is None

    def test_submissions_isolated_by_job(self, dynamodb_table):
        repo = SubmissionRepository(table=dynamodb_table)
        job1_id = uuid4()
        job2_id = uuid4()

        subs1 = [
            Submission(
                job_id=job1_id,
                question_id=101,
                question_name="Q1",
                question_type="short_answer_question",
                question_text="What is X?",
                points_possible=5.0,
                student_answer="Job1 answer",
                canvas_points=5.0,
                correct_answers=["X"],
            )
        ]
        subs2 = [
            Submission(
                job_id=job2_id,
                question_id=102,
                question_name="Q2",
                question_type="short_answer_question",
                question_text="What is Y?",
                points_possible=10.0,
                student_answer="Job2 answer",
                canvas_points=10.0,
                correct_answers=["Y"],
            )
        ]
        repo.batch_create(subs1)
        repo.batch_create(subs2)

        results1 = repo.list_by_job(job1_id)
        assert len(results1) == 1
        assert results1[0].student_answer == "Job1 answer"

        results2 = repo.list_by_job(job2_id)
        assert len(results2) == 1
        assert results2[0].student_answer == "Job2 answer"

    def test_update_ai_grade(self, dynamodb_table):
        repo = SubmissionRepository(table=dynamodb_table)
        job_id = uuid4()
        sub = Submission(
            job_id=job_id,
            question_id=101,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What is X?",
            points_possible=5.0,
            student_answer="My answer",
            canvas_points=3.0,
            correct_answers=["X"],
        )
        repo.batch_create([sub])

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        repo.update_ai_grade(
            job_id=job_id,
            submission_id=sub.submission_id,
            ai_grade=4.5,
            ai_feedback="Good work",
            ai_graded_at=now,
        )

        result = repo.get(job_id, sub.submission_id)
        assert result.ai_grade == 4.5
        assert result.ai_feedback == "Good work"
        assert result.ai_graded_at is not None

    def test_update_ai_grade_preserves_fields(self, dynamodb_table):
        repo = SubmissionRepository(table=dynamodb_table)
        job_id = uuid4()
        sub = Submission(
            job_id=job_id,
            question_id=101,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What is X?",
            points_possible=5.0,
            student_answer="My answer",
            canvas_points=3.0,
            correct_answers=["X", "Y"],
        )
        repo.batch_create([sub])

        from datetime import datetime, timezone

        repo.update_ai_grade(
            job_id=job_id,
            submission_id=sub.submission_id,
            ai_grade=4.0,
            ai_feedback="Nice",
            ai_graded_at=datetime.now(timezone.utc),
        )

        result = repo.get(job_id, sub.submission_id)
        assert result.student_answer == "My answer"
        assert result.points_possible == 5.0
        assert result.canvas_points == 3.0
        assert result.correct_answers == ["X", "Y"]
        assert result.question_text == "What is X?"

    def test_float_roundtrip(self, dynamodb_table):
        """Verify floats survive the DynamoDB string conversion roundtrip."""
        repo = SubmissionRepository(table=dynamodb_table)
        job_id = uuid4()
        sub = Submission(
            job_id=job_id,
            question_id=101,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What is X?",
            points_possible=3.14,
            student_answer="Answer",
            canvas_points=2.71,
            correct_answers=["X"],
        )
        repo.batch_create([sub])

        result = repo.get(job_id, sub.submission_id)
        assert result.points_possible == 3.14
        assert result.canvas_points == 2.71

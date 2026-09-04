"""Tests for the jobs API endpoints (session auth required)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture
def client(dynamodb_table, session_token):
    """FastAPI test client with mocked DynamoDB and LTI session auth configured."""
    with patch("src.core.aws.get_dynamodb_table", return_value=dynamodb_table):
        yield TestClient(create_app())


class TestAuthRequired:
    def test_create_job_requires_auth(
        self, client, sample_canvas_data, instructor_launch
    ):
        response = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
        )
        assert response.status_code == 401

    def test_list_jobs_requires_auth(self, client):
        response = client.get("/jobs")
        assert response.status_code == 401

    def test_get_job_requires_auth(self, client):
        response = client.get("/jobs/12345678-1234-5678-1234-567812345678")
        assert response.status_code == 401

    def test_grade_job_requires_auth(self, client):
        response = client.post("/jobs/12345678-1234-5678-1234-567812345678/grade")
        assert response.status_code == 401

    def test_list_submissions_requires_auth(self, client):
        response = client.get("/jobs/12345678-1234-5678-1234-567812345678/submissions")
        assert response.status_code == 401


class TestCreateJob:
    def test_create_job_returns_201(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        response = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["course_id"] == "C100"
        assert data["quiz_id"] == "Q50"
        assert data["job_name"] == "Test Job"
        assert data["status"] == "PENDING"
        assert data["total_questions"] == 1
        assert data["total_submissions"] == 2
        assert "job_id" in data

    def test_create_job_wrong_course_returns_403(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        response = client.post(
            "/jobs",
            json={
                "course_id": "DIFFERENT",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 403

    def test_create_job_invalid_canvas_data(
        self, client, session_token, instructor_launch
    ):
        response = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Bad Job",
                "canvas_data": {"short_answer_question": [{"bad": "data"}]},
            },
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 422

    def test_create_job_missing_fields(self, client, session_token, instructor_launch):
        response = client.post(
            "/jobs",
            json={"course_id": "C100"},
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 422


class TestGetJob:
    def test_get_job(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        create_resp = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers={"Authorization": f"Bearer {session_token}"},
        )
        job_id = create_resp.json()["job_id"]

        response = client.get(
            f"/jobs/{job_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == job_id

    def test_get_job_not_found(self, client, session_token, instructor_launch):
        response = client.get(
            "/jobs/12345678-1234-5678-1234-567812345678",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_get_job_wrong_course_returns_403(
        self,
        client,
        session_token,
        dynamodb_table,
        sample_canvas_data,
        instructor_launch,
    ):
        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="OTHER_COURSE", quiz_id="Q50", job_name="Other Job")
        repo.create(job)

        response = client.get(
            f"/jobs/{job.job_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 403


class TestListJobs:
    def test_list_by_session_course(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        auth = {"Authorization": f"Bearer {session_token}"}
        client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Job 1",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q51",
                "job_name": "Job 2",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )

        response = client.get("/jobs", headers=auth)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_by_status(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        auth = {"Authorization": f"Bearer {session_token}"}
        client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Job 1",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )

        response = client.get("/jobs", params={"status": "PENDING"}, headers=auth)
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_empty_results(self, client, session_token, instructor_launch):
        # No jobs created — should return empty list for the session course
        response = client.get(
            "/jobs",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_jobs_excludes_other_courses(
        self,
        client,
        session_token,
        dynamodb_table,
        sample_canvas_data,
        instructor_launch,
    ):
        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        other_job = GradingJob(
            course_id="OTHER", quiz_id="Q99", job_name="Other Course Job"
        )
        repo.create(other_job)

        auth = {"Authorization": f"Bearer {session_token}"}
        client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )

        response = client.get("/jobs", headers=auth)
        ids = {j["job_id"] for j in response.json()}
        assert str(other_job.job_id) not in ids


class TestGradeJob:
    def test_grade_job_success(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        auth = {"Authorization": f"Bearer {session_token}"}
        create_resp = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create_resp.json()["job_id"]

        with patch("src.api.routes.jobs._get_grading_service") as mock_get_service:
            mock_service = mock_get_service.return_value
            mock_service.grade_job.return_value = None
            response = client.post(f"/jobs/{job_id}/grade", headers=auth)

        assert response.status_code == 200
        mock_service.grade_job.assert_called_once()

    def test_grade_job_not_found(self, client, session_token, instructor_launch):
        response = client.post(
            "/jobs/12345678-1234-5678-1234-567812345678/grade",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_grade_job_not_pending(
        self,
        client,
        session_token,
        dynamodb_table,
        sample_canvas_data,
        instructor_launch,
    ):
        from src.models.grading_job import GradingJob, JobStatus
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(
            course_id="C100",
            quiz_id="Q50",
            job_name="Done Job",
            status=JobStatus.COMPLETED,
        )
        repo.create(job)

        response = client.post(
            f"/jobs/{job.job_id}/grade",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 409

    def test_grade_job_wrong_course_returns_403(
        self, client, session_token, dynamodb_table, instructor_launch
    ):
        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="OTHER", quiz_id="Q50", job_name="Other Job")
        repo.create(job)

        response = client.post(
            f"/jobs/{job.job_id}/grade",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 403


class TestListSubmissions:
    def test_list_submissions(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        auth = {"Authorization": f"Bearer {session_token}"}
        create_resp = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create_resp.json()["job_id"]

        response = client.get(f"/jobs/{job_id}/submissions", headers=auth)
        assert response.status_code == 200
        subs = response.json()
        assert len(subs) == 2
        answers = {s["student_answer"] for s in subs}
        assert "Plants use sunlight to make food" in answers
        assert "I don't know" in answers

    def test_list_submissions_job_not_found(
        self, client, session_token, instructor_launch
    ):
        response = client.get(
            "/jobs/12345678-1234-5678-1234-567812345678/submissions",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_list_submissions_wrong_course_returns_403(
        self, client, session_token, dynamodb_table, instructor_launch
    ):
        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="OTHER", quiz_id="Q50", job_name="Other Job")
        repo.create(job)

        response = client.get(
            f"/jobs/{job.job_id}/submissions",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 403


class TestCancelJob:
    def test_cancel_job_success(
        self, client, session_token, sample_canvas_data, instructor_launch
    ):
        auth = {"Authorization": f"Bearer {session_token}"}
        create_resp = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create_resp.json()["job_id"]

        response = client.post(f"/jobs/{job_id}/cancel", headers=auth)
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_cancel_job_not_found(self, client, session_token, instructor_launch):
        response = client.post(
            "/jobs/12345678-1234-5678-1234-567812345678/cancel",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_cancel_job_wrong_course_returns_403(
        self, client, session_token, dynamodb_table, instructor_launch
    ):
        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="OTHER", quiz_id="Q50", job_name="Other Job")
        repo.create(job)

        response = client.post(
            f"/jobs/{job.job_id}/cancel",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 403

    def test_cancel_job_already_completed_returns_409(
        self, client, session_token, dynamodb_table, instructor_launch
    ):
        from src.models.grading_job import GradingJob, JobStatus
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(
            course_id="C100",
            quiz_id="Q50",
            job_name="Done Job",
            status=JobStatus.COMPLETED,
        )
        repo.create(job)

        response = client.post(
            f"/jobs/{job.job_id}/cancel",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 409

    def test_cancel_job_from_processing_returns_200(
        self, client, session_token, dynamodb_table, instructor_launch
    ):
        from src.models.grading_job import GradingJob, JobStatus
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Processing Job")
        repo.create(job)
        repo.update_status(job.job_id, JobStatus.PROCESSING)

        response = client.post(
            f"/jobs/{job.job_id}/cancel",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"


class TestSubmissionOverride:
    def test_override_submission_updates_grade(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID

        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        auth = {"Authorization": f"Bearer {session_token}"}

        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )

        job_id = create.json()["job_id"]

        GradingJobRepository(table=dynamodb_table).update_status(
            UUID(job_id),
            JobStatus.COMPLETED,
        )

        submission = client.get(
            f"/jobs/{job_id}/submissions",
            headers=auth,
        ).json()[0]

        submission_id = submission["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={
                "grade": 5,
                "feedback": "Great answer",
            },
            headers=auth,
        )

        assert response.status_code == 200

        repo = SubmissionRepository(table=dynamodb_table)

        updated = repo.get(
            UUID(job_id),
            UUID(submission_id),
        )

        assert updated.instructor_grade == 5
        assert updated.instructor_feedback == "Great answer"

    def test_override_submission_success(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID

        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository

        auth = {"Authorization": f"Bearer {session_token}"}

        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )

        job_id = create.json()["job_id"]

        repo = GradingJobRepository(table=dynamodb_table)
        repo.update_status(UUID(job_id), JobStatus.COMPLETED)

        subs = client.get(
            f"/jobs/{job_id}/submissions",
            headers=auth,
        ).json()

        submission_id = subs[0]["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={
                "grade": 4,
                "feedback": "Excellent work.",
            },
            headers=auth,
        )
        assert response.status_code == 200

        data = response.json()

        assert data["instructor_grade"] == 4
        assert data["instructor_feedback"] == "Excellent work."

        assert data["effective_grade"] == 4
        assert data["effective_feedback"] == "Excellent work."

        assert data["overridden_by"] != ""
        assert data["overridden_at"] is not None

    def test_override_submission_out_of_range(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID

        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository

        auth = {"Authorization": f"Bearer {session_token}"}

        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )

        job_id = create.json()["job_id"]

        repo = GradingJobRepository(table=dynamodb_table)
        repo.update_status(UUID(job_id), JobStatus.COMPLETED)

        subs = client.get(
            f"/jobs/{job_id}/submissions",
            headers=auth,
        ).json()

        submission_id = subs[0]["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={"grade": 9999},
            headers=auth,
        )

        assert response.status_code == 422

    def test_override_submission_job_not_completed(
        self,
        client,
        session_token,
        sample_canvas_data,
        instructor_launch,
    ):
        auth = {"Authorization": f"Bearer {session_token}"}

        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )

        job_id = create.json()["job_id"]

        subs = client.get(
            f"/jobs/{job_id}/submissions",
            headers=auth,
        ).json()

        submission_id = subs[0]["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={"grade": 5},
            headers=auth,
        )

        assert response.status_code == 409

    def test_override_submission_wrong_course(
        self,
        client,
        session_token,
        dynamodb_table,
        instructor_launch,
    ):
        from src.models.grading_job import GradingJob, JobStatus
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        job_repo = GradingJobRepository(table=dynamodb_table)

        job = GradingJob(
            course_id="OTHER",
            quiz_id="Q50",
            job_name="Other Job",
            status=JobStatus.COMPLETED,
        )
        job_repo.create(job)

        sub = Submission(
            job_id=job.job_id,
            question_id=1,
            question_name="Q1",
            question_type="essay_question",
            question_text="Question",
            points_possible=10,
            student_answer="Answer",
            canvas_points=0,
            correct_answers=[],
        )

        SubmissionRepository(table=dynamodb_table).batch_create([sub])

        response = client.patch(
            f"/jobs/{job.job_id}/submissions/{sub.submission_id}",
            json={"grade": 8},
            headers={"Authorization": f"Bearer {session_token}"},
        )

        assert response.status_code == 403

    def test_override_submission_revert(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID
        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        auth = {"Authorization": f"Bearer {session_token}"}

        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create.json()["job_id"]
        GradingJobRepository(table=dynamodb_table).update_status(
            UUID(job_id), JobStatus.COMPLETED
        )

        resp = client.get(f"/jobs/{job_id}/submissions", headers=auth)
        print("STATUS:", resp.status_code, "BODY:", resp.json())
        subs = resp.json()
        submission_id = subs[0]["submission_id"]

        subs = client.get(f"/jobs/{job_id}/submissions", headers=auth).json()
        submission_id = subs[0]["submission_id"]

        # First set an override
        client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={"grade": 4.5, "feedback": "Good"},
            headers=auth,
        )

        repo = SubmissionRepository(table=dynamodb_table)
        stored = repo.get(UUID(job_id), UUID(submission_id))
        assert stored.instructor_grade == 4.5
        assert stored.instructor_feedback == "Good"

        # Then revert it
        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={"revert": True},
            headers=auth,
        )
        assert response.status_code == 200

        updated = repo.get(UUID(job_id), UUID(submission_id))
        assert updated.instructor_grade is None
        assert updated.instructor_feedback is None
        assert updated.overridden_by is None

    def test_override_submission_nothing_to_update(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID
        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository

        auth = {"Authorization": f"Bearer {session_token}"}

        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create.json()["job_id"]
        GradingJobRepository(table=dynamodb_table).update_status(
            UUID(job_id), JobStatus.COMPLETED
        )

        subs = client.get(f"/jobs/{job_id}/submissions", headers=auth).json()
        submission_id = subs[0]["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={},
            headers=auth,
        )
        assert response.status_code == 422

    def test_override_submission_not_found(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID, uuid4
        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository

        auth = {"Authorization": f"Bearer {session_token}"}

        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create.json()["job_id"]
        GradingJobRepository(table=dynamodb_table).update_status(
            UUID(job_id), JobStatus.COMPLETED
        )

        response = client.patch(
            f"/jobs/{job_id}/submissions/{uuid4()}",
            json={"grade": 5},
            headers=auth,
        )
        assert response.status_code == 404

    def test_override_submission_allowed_on_completed_with_errors(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID
        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository

        auth = {"Authorization": f"Bearer {session_token}"}
        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create.json()["job_id"]

        GradingJobRepository(table=dynamodb_table).update_status(
            UUID(job_id), JobStatus.COMPLETED_WITH_ERRORS, success_count=1, fail_count=1
        )

        subs = client.get(f"/jobs/{job_id}/submissions", headers=auth).json()
        submission_id = subs[0]["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={"grade": 1, "revert": True},
            headers=auth,
        )
        assert response.status_code == 422

    def test_override_negative_grade_returns_422(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID
        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository

        auth = {"Authorization": f"Bearer {session_token}"}
        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create.json()["job_id"]
        GradingJobRepository(table=dynamodb_table).update_status(
            UUID(job_id), JobStatus.COMPLETED
        )
        subs = client.get(f"/jobs/{job_id}/submissions", headers=auth).json()
        submission_id = subs[0]["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={"grade": -1},
            headers=auth,
        )
        assert response.status_code == 422

    def test_override_empty_feedback_returns_422(
        self,
        client,
        session_token,
        sample_canvas_data,
        dynamodb_table,
        instructor_launch,
    ):
        from uuid import UUID
        from src.models.grading_job import JobStatus
        from src.repositories.grading_job import GradingJobRepository

        auth = {"Authorization": f"Bearer {session_token}"}
        create = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
            headers=auth,
        )
        job_id = create.json()["job_id"]
        GradingJobRepository(table=dynamodb_table).update_status(
            UUID(job_id), JobStatus.COMPLETED
        )
        subs = client.get(f"/jobs/{job_id}/submissions", headers=auth).json()
        submission_id = subs[0]["submission_id"]

        response = client.patch(
            f"/jobs/{job_id}/submissions/{submission_id}",
            json={"feedback": "   "},
            headers=auth,
        )
        assert response.status_code == 422


class TestRetryFailedJob:
    def test_retry_requires_completed_with_errors(
        self, client, session_token, instructor_launch, dynamodb_table
    ):
        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(course_id="C100", quiz_id="Q50", job_name="Pending Job")
        repo.create(job)

        response = client.post(
            f"/jobs/{job.job_id}/retry-failed",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 409

    def test_retry_not_found(self, client, session_token, instructor_launch):
        response = client.post(
            "/jobs/12345678-1234-5678-1234-567812345678/retry-failed",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_retry_wrong_course_returns_403(
        self, client, session_token, dynamodb_table, instructor_launch
    ):
        from src.models.grading_job import GradingJob, JobStatus
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(
            course_id="OTHER",
            quiz_id="Q50",
            job_name="Other Job",
            status=JobStatus.COMPLETED_WITH_ERRORS,
        )
        repo.create(job)

        response = client.post(
            f"/jobs/{job.job_id}/retry-failed",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 403

    def test_retry_calls_service(
        self, client, session_token, dynamodb_table, instructor_launch
    ):
        from src.models.grading_job import GradingJob, JobStatus
        from src.repositories.grading_job import GradingJobRepository

        repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(
            course_id="C100",
            quiz_id="Q50",
            job_name="Partial Job",
            status=JobStatus.COMPLETED_WITH_ERRORS,
        )
        repo.create(job)

        with patch("src.api.routes.jobs._get_grading_service") as mock_get_service:
            mock_service = mock_get_service.return_value
            mock_service.retry_failed.return_value = None
            response = client.post(
                f"/jobs/{job.job_id}/retry-failed",
                headers={"Authorization": f"Bearer {session_token}"},
            )

        assert response.status_code == 200
        mock_service.retry_failed.assert_called_once()

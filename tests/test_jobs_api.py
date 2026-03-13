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
    def test_create_job_requires_auth(self, client, sample_canvas_data):
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
    def test_create_job_returns_201(self, client, session_token, sample_canvas_data):
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
        self, client, session_token, sample_canvas_data
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

    def test_create_job_invalid_canvas_data(self, client, session_token):
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

    def test_create_job_missing_fields(self, client, session_token):
        response = client.post(
            "/jobs",
            json={"course_id": "C100"},
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 422


class TestGetJob:
    def test_get_job(self, client, session_token, sample_canvas_data):
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

    def test_get_job_not_found(self, client, session_token):
        response = client.get(
            "/jobs/12345678-1234-5678-1234-567812345678",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_get_job_wrong_course_returns_403(
        self, client, session_token, dynamodb_table, sample_canvas_data
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
    def test_list_by_session_course(self, client, session_token, sample_canvas_data):
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

    def test_list_by_status(self, client, session_token, sample_canvas_data):
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

    def test_list_empty_results(self, client, session_token):
        # No jobs created — should return empty list for the session course
        response = client.get(
            "/jobs",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 200
        assert response.json() == []


class TestGradeJob:
    def test_grade_job_success(self, client, session_token, sample_canvas_data):
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

    def test_grade_job_not_found(self, client, session_token):
        response = client.post(
            "/jobs/12345678-1234-5678-1234-567812345678/grade",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_grade_job_not_pending(
        self, client, session_token, dynamodb_table, sample_canvas_data
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
        self, client, session_token, dynamodb_table
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
    def test_list_submissions(self, client, session_token, sample_canvas_data):
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

    def test_list_submissions_job_not_found(self, client, session_token):
        response = client.get(
            "/jobs/12345678-1234-5678-1234-567812345678/submissions",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 404

    def test_list_submissions_wrong_course_returns_403(
        self, client, session_token, dynamodb_table
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

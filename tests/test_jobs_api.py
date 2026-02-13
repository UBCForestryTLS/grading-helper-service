"""Tests for the jobs API endpoints."""

from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from src.api.app import create_app


@pytest.fixture
def mock_table(aws_credentials):
    """Create a moto DynamoDB table and patch get_dynamodb_table to return it."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ca-central-1")
        table = dynamodb.create_table(
            TableName="GradingTable",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="GradingTable")
        with patch("src.core.aws.get_dynamodb_table", return_value=table):
            yield table


@pytest.fixture
def client(mock_table):
    """FastAPI test client with mocked DynamoDB."""
    return TestClient(create_app())


class TestCreateJob:
    def test_create_job_returns_201(self, client, sample_canvas_data):
        response = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
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

    def test_create_job_invalid_canvas_data(self, client):
        response = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Bad Job",
                "canvas_data": {"short_answer_question": [{"bad": "data"}]},
            },
        )
        assert response.status_code == 422

    def test_create_job_missing_fields(self, client):
        response = client.post("/jobs", json={"course_id": "C100"})
        assert response.status_code == 422


class TestGetJob:
    def test_get_job(self, client, sample_canvas_data):
        create_resp = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
        )
        job_id = create_resp.json()["job_id"]

        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["job_id"] == job_id

    def test_get_job_not_found(self, client):
        response = client.get("/jobs/12345678-1234-5678-1234-567812345678")
        assert response.status_code == 404


class TestListJobs:
    def test_list_by_course(self, client, sample_canvas_data):
        client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Job 1",
                "canvas_data": sample_canvas_data,
            },
        )
        client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q51",
                "job_name": "Job 2",
                "canvas_data": sample_canvas_data,
            },
        )

        response = client.get("/jobs", params={"course_id": "C100"})
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_by_status(self, client, sample_canvas_data):
        client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Job 1",
                "canvas_data": sample_canvas_data,
            },
        )

        response = client.get("/jobs", params={"status": "PENDING"})
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_no_filter_returns_400(self, client):
        response = client.get("/jobs")
        assert response.status_code == 400

    def test_list_empty_results(self, client):
        response = client.get("/jobs", params={"course_id": "NONEXISTENT"})
        assert response.status_code == 200
        assert response.json() == []


class TestListSubmissions:
    def test_list_submissions(self, client, sample_canvas_data):
        create_resp = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test Job",
                "canvas_data": sample_canvas_data,
            },
        )
        job_id = create_resp.json()["job_id"]

        response = client.get(f"/jobs/{job_id}/submissions")
        assert response.status_code == 200
        subs = response.json()
        assert len(subs) == 2
        answers = {s["student_answer"] for s in subs}
        assert "Plants use sunlight to make food" in answers
        assert "I don't know" in answers

    def test_list_submissions_job_not_found(self, client):
        response = client.get("/jobs/12345678-1234-5678-1234-567812345678/submissions")
        assert response.status_code == 404

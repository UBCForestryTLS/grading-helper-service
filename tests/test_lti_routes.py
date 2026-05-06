"""Integration tests for LTI endpoints."""

import time
from unittest.mock import Mock, patch

import boto3
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from moto import mock_aws

from src.api.app import create_app
from src.auth.session import _get_public_key
from src.lti.key_manager import get_private_key, get_public_jwk


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
def client(mock_table, lti_env_vars):
    """FastAPI test client with mocked DynamoDB and LTI config."""
    get_private_key.cache_clear()
    get_public_jwk.cache_clear()
    _get_public_key.cache_clear()
    client = TestClient(create_app())
    yield client
    get_private_key.cache_clear()
    get_public_jwk.cache_clear()
    _get_public_key.cache_clear()


class TestJWKS:
    def test_jwks_endpoint_returns_keys(self, client):
        response = client.get("/.well-known/jwks.json")
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert len(data["keys"]) == 1
        assert data["keys"][0]["kty"] == "RSA"
        assert data["keys"][0]["alg"] == "RS256"
        assert data["keys"][0]["use"] == "sig"


class TestLTIConfig:
    def test_config_returns_valid_json(self, client):
        response = client.get("/lti/config")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "UBC Forestry Grading Helper"
        assert "/lti/login" in data["oidc_initiation_url"]
        assert "/lti/launch" in data["target_link_uri"]
        assert "/.well-known/jwks.json" in data["public_jwk_url"]
        assert len(data["scopes"]) > 0
        assert "extensions" in data
        assert "custom_fields" in data


class TestOIDCLogin:
    def test_login_redirects(self, client):
        response = client.get(
            "/lti/login",
            params={
                "iss": "https://canvas.test.instructure.com",
                "login_hint": "user123",
                "target_link_uri": "https://test.execute-api.ca-central-1.amazonaws.com/dev/lti/launch",
                "client_id": "10000000000001",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        location = response.headers["location"]
        assert "canvas.test.instructure.com" in location
        assert "state=" in location
        assert "nonce=" in location
        assert "response_type=id_token" in location

    def test_login_unknown_iss_returns_400(self, client):
        response = client.get(
            "/lti/login",
            params={
                "iss": "https://unknown.example.com",
                "login_hint": "user123",
            },
        )
        assert response.status_code == 400

    def test_login_missing_iss_returns_400(self, client):
        response = client.get(
            "/lti/login",
            params={"login_hint": "user123"},
        )
        assert response.status_code == 400

    def test_login_wrong_client_id_returns_400(self, client):
        response = client.get(
            "/lti/login",
            params={
                "iss": "https://canvas.test.instructure.com",
                "login_hint": "user123",
                "client_id": "wrong-client-id",
            },
        )
        assert response.status_code == 400


class TestLTILaunch:
    def test_launch_missing_params_returns_400(self, client):
        response = client.post("/lti/launch", data={})
        assert response.status_code == 400

    def test_launch_invalid_state_returns_400(self, client):
        response = client.post(
            "/lti/launch",
            data={"id_token": "fake.jwt.token", "state": "nonexistent"},
        )
        assert response.status_code == 400

    def test_launch_valid_flow(self, client, mock_table):
        """Full login-to-launch flow with a real JWT."""
        # Step 1: OIDC login to get state
        login_resp = client.get(
            "/lti/login",
            params={
                "iss": "https://canvas.test.instructure.com",
                "login_hint": "user123",
                "target_link_uri": "https://test.execute-api.ca-central-1.amazonaws.com/dev/lti/launch",
            },
            follow_redirects=False,
        )
        location = login_resp.headers["location"]
        # Extract state and nonce from redirect URL
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(location).query)
        state = query["state"][0]
        nonce = query["nonce"][0]

        # Step 2: Create a signed JWT (simulating Canvas)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = {
            "iss": "https://canvas.test.instructure.com",
            "aud": "10000000000001",
            "sub": "user-456",
            "nonce": nonce,
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "name": "Test User",
            "email": "test@ubc.ca",
            "https://purl.imsglobal.org/spec/lti/claim/context": {
                "id": "course-123",
                "label": "FRST101",
                "title": "Intro to Forestry",
            },
            "https://purl.imsglobal.org/spec/lti/claim/roles": [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"
            ],
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "1:test-deployment",
        }
        id_token = pyjwt.encode(claims, private_key, algorithm="RS256")

        # Step 3: Mock JWKS client to return our test key
        mock_jwks_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = private_key.public_key()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch(
            "src.lti.jwt_validation.get_jwks_client",
            return_value=mock_jwks_client,
        ):
            response = client.post(
                "/lti/launch",
                data={"id_token": id_token, "state": state},
            )

        assert response.status_code == 200
        # New response is the instructor UI (not the old placeholder page)
        assert "Test User" in response.text
        assert "Intro to Forestry" in response.text
        assert "Instructor" in response.text
        # Session token is embedded in the UI
        assert "session-token" in response.text

    def test_launch_invalid_flow_student_user(self, client, mock_table):
        """Full login-to-launch flow with a real JWT."""
        # Step 1: OIDC login to get state
        login_resp = client.get(
            "/lti/login",
            params={
                "iss": "https://canvas.test.instructure.com",
                "login_hint": "user123",
                "target_link_uri": "https://test.execute-api.ca-central-1.amazonaws.com/dev/lti/launch",
            },
            follow_redirects=False,
        )
        location = login_resp.headers["location"]
        # Extract state and nonce from redirect URL
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(location).query)
        state = query["state"][0]
        nonce = query["nonce"][0]

        # Step 2: Create a signed JWT (simulating Canvas)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = {
            "iss": "https://canvas.test.instructure.com",
            "aud": "10000000000001",
            "sub": "user-456",
            "nonce": nonce,
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "name": "Test User",
            "email": "test@ubc.ca",
            "https://purl.imsglobal.org/spec/lti/claim/context": {
                "id": "course-123",
                "label": "FRST101",
                "title": "Intro to Forestry",
            },
            "https://purl.imsglobal.org/spec/lti/claim/roles": [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
            ],
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "1:test-deployment",
        }
        id_token = pyjwt.encode(claims, private_key, algorithm="RS256")

        # Step 3: Mock JWKS client to return our test key
        mock_jwks_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = private_key.public_key()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch(
            "src.lti.jwt_validation.get_jwks_client",
            return_value=mock_jwks_client,
        ):
            response = client.post(
                "/lti/launch",
                data={"id_token": id_token, "state": state},
            )

        assert response.status_code == 403
        # New response is the instructor UI (not the old placeholder page)
        assert "Access Restricted" in response.text
        assert "Intro to Forestry" not in response.text
        assert "Test User" not in response.text
        assert "session-token" not in response.text

    def test_launch_valid_flow_TA_user(self, client, mock_table):
        """Full login-to-launch flow with a real JWT."""
        # Step 1: OIDC login to get state
        login_resp = client.get(
            "/lti/login",
            params={
                "iss": "https://canvas.test.instructure.com",
                "login_hint": "user123",
                "target_link_uri": "https://test.execute-api.ca-central-1.amazonaws.com/dev/lti/launch",
            },
            follow_redirects=False,
        )
        location = login_resp.headers["location"]
        # Extract state and nonce from redirect URL
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(location).query)
        state = query["state"][0]
        nonce = query["nonce"][0]

        # Step 2: Create a signed JWT (simulating Canvas)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = {
            "iss": "https://canvas.test.instructure.com",
            "aud": "10000000000001",
            "sub": "user-456",
            "nonce": nonce,
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "name": "Test User",
            "email": "test@ubc.ca",
            "https://purl.imsglobal.org/spec/lti/claim/context": {
                "id": "course-123",
                "label": "FRST101",
                "title": "Intro to Forestry",
            },
            "https://purl.imsglobal.org/spec/lti/claim/roles": [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#TeachingAssistant"
            ],
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "1:test-deployment",
        }
        id_token = pyjwt.encode(claims, private_key, algorithm="RS256")

        # Step 3: Mock JWKS client to return our test key
        mock_jwks_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = private_key.public_key()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch(
            "src.lti.jwt_validation.get_jwks_client",
            return_value=mock_jwks_client,
        ):
            response = client.post(
                "/lti/launch",
                data={"id_token": id_token, "state": state},
            )

        assert response.status_code == 200
        # New response is the instructor UI (not the old placeholder page)
        assert "Test User" in response.text
        assert "Intro to Forestry" in response.text
        assert "TeachingAssistant" in response.text
        # Session token is embedded in the UI
        assert "session-token" in response.text

    def test_launch_valid_flow_admin_user(self, client, mock_table):
        """Full login-to-launch flow with a real JWT."""
        # Step 1: OIDC login to get state
        login_resp = client.get(
            "/lti/login",
            params={
                "iss": "https://canvas.test.instructure.com",
                "login_hint": "user123",
                "target_link_uri": "https://test.execute-api.ca-central-1.amazonaws.com/dev/lti/launch",
            },
            follow_redirects=False,
        )
        location = login_resp.headers["location"]
        # Extract state and nonce from redirect URL
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(location).query)
        state = query["state"][0]
        nonce = query["nonce"][0]

        # Step 2: Create a signed JWT (simulating Canvas)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = {
            "iss": "https://canvas.test.instructure.com",
            "aud": "10000000000001",
            "sub": "user-456",
            "nonce": nonce,
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "name": "Test User",
            "email": "test@ubc.ca",
            "https://purl.imsglobal.org/spec/lti/claim/context": {
                "id": "course-123",
                "label": "FRST101",
                "title": "Intro to Forestry",
            },
            "https://purl.imsglobal.org/spec/lti/claim/roles": [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Administrator"
            ],
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "1:test-deployment",
        }
        id_token = pyjwt.encode(claims, private_key, algorithm="RS256")

        # Step 3: Mock JWKS client to return our test key
        mock_jwks_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = private_key.public_key()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch(
            "src.lti.jwt_validation.get_jwks_client",
            return_value=mock_jwks_client,
        ):
            response = client.post(
                "/lti/launch",
                data={"id_token": id_token, "state": state},
            )

        assert response.status_code == 200
        # New response is the instructor UI (not the old placeholder page)
        assert "Test User" in response.text
        assert "Intro to Forestry" in response.text
        assert "Administrator" in response.text
        # Session token is embedded in the UI
        assert "session-token" in response.text


class TestPassback:
    def test_passback_uses_rest_path_when_job_has_quiz_id(
        self, client, mock_table, session_token
    ):
        from uuid import uuid4
        from unittest.mock import patch

        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        job_id = uuid4()
        GradingJobRepository(table=mock_table).create(
            GradingJob(
                job_id=job_id,
                course_id="C100",
                quiz_id="Q50",
                job_name="Test Quiz",
            )
        )

        with (
            patch("src.lti.oauth.get_canvas_token", return_value="canvas-tok"),
            patch(
                "src.lti.ags.passback_quiz_grades_via_rest",
                return_value={"submitted": 1, "errors": []},
            ) as mock_rest,
        ):
            response = client.post(
                f"/lti/passback/{job_id}",
                json={"launch_id": "some-launch-id"},
                headers={"Authorization": f"Bearer {session_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["submitted"] == 1
        assert data["errors"] == []
        mock_rest.assert_called_once()
        call_kwargs = mock_rest.call_args[1]
        assert call_kwargs["quiz_id"] == "Q50"
        assert call_kwargs["course_id"] == "C100"
        assert call_kwargs["canvas_token"] == "canvas-tok"

    def test_passback_returns_401_when_no_canvas_token(
        self, client, mock_table, session_token
    ):
        from uuid import uuid4
        from unittest.mock import patch

        from src.models.grading_job import GradingJob
        from src.repositories.grading_job import GradingJobRepository

        job_id = uuid4()
        GradingJobRepository(table=mock_table).create(
            GradingJob(
                job_id=job_id,
                course_id="C100",
                quiz_id="Q50",
                job_name="Test Quiz",
            )
        )

        with patch("src.lti.oauth.get_canvas_token", return_value=None):
            response = client.post(
                f"/lti/passback/{job_id}",
                json={"launch_id": "some-launch-id"},
                headers={"Authorization": f"Bearer {session_token}"},
            )

        assert response.status_code == 401
        assert "Re-authorize" in response.json()["detail"]

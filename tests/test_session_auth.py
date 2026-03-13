"""Tests for RS256 JWT session auth system."""

import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from src.api.app import create_app


class TestCreateSessionToken:
    def test_create_and_decode_roundtrip(self, lti_env_vars):
        from src.auth.session import _get_public_key, create_session_token

        token = create_session_token(
            launch_id="launch-abc",
            course_id="COURSE-123",
            canvas_user_id="user-456",
        )
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT format

        public_key = _get_public_key()
        payload = pyjwt.decode(
            token, public_key, algorithms=["RS256"], issuer="grading-helper"
        )
        assert payload["launch_id"] == "launch-abc"
        assert payload["course_id"] == "COURSE-123"
        assert payload["sub"] == "user-456"
        assert payload["iss"] == "grading-helper"
        assert payload["exp"] > int(time.time())

    def test_token_expires_in_one_hour(self, lti_env_vars):
        from src.auth.session import create_session_token, _get_public_key

        token = create_session_token("l1", "c1", "u1")
        public_key = _get_public_key()
        payload = pyjwt.decode(
            token, public_key, algorithms=["RS256"], issuer="grading-helper"
        )
        ttl = payload["exp"] - payload["iat"]
        assert 3590 <= ttl <= 3610  # ~3600s


class TestRequireSession:
    @pytest.fixture
    def client(self, dynamodb_table, session_token):
        from unittest.mock import patch

        with patch("src.core.aws.get_dynamodb_table", return_value=dynamodb_table):
            yield TestClient(create_app())

    def test_valid_token_grants_access(self, client, session_token, sample_canvas_data):
        response = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test",
                "canvas_data": sample_canvas_data,
            },
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 201

    def test_missing_auth_header_returns_401(self, client, sample_canvas_data):
        response = client.post(
            "/jobs",
            json={
                "course_id": "C100",
                "quiz_id": "Q50",
                "job_name": "Test",
                "canvas_data": sample_canvas_data,
            },
        )
        assert response.status_code == 401

    def test_expired_token_returns_401(self, client, lti_env_vars):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from src.lti.key_manager import get_private_key

        private_key = load_pem_private_key(get_private_key().encode(), password=None)
        expired_payload = {
            "sub": "user-1",
            "course_id": "C100",
            "launch_id": "l1",
            "iss": "grading-helper",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,  # already expired
        }
        expired_token = pyjwt.encode(expired_payload, private_key, algorithm="RS256")

        response = client.get(
            "/jobs",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_wrong_signature_returns_401(self, client):
        # Sign with a different key
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload = {
            "sub": "user-1",
            "course_id": "C100",
            "launch_id": "l1",
            "iss": "grading-helper",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        bad_token = pyjwt.encode(payload, other_key, algorithm="RS256")

        response = client.get(
            "/jobs",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert response.status_code == 401

    def test_malformed_token_returns_401(self, client):
        response = client.get(
            "/jobs",
            headers={"Authorization": "Bearer not.a.valid.jwt"},
        )
        assert response.status_code == 401

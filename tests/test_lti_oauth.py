"""Tests for Canvas OAuth2 helper functions."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lti.oauth import build_auth_url, get_canvas_token, store_canvas_token


class TestBuildAuthUrl:
    def test_builds_correct_url(self):
        url = build_auth_url(
            canvas_url="https://ubcstaging.instructure.com",
            client_id="12345",
            redirect_uri="https://tool.example.com/lti/oauth/callback",
            state="my-launch-id",
        )
        assert url.startswith("https://ubcstaging.instructure.com/login/oauth2/auth?")
        assert "client_id=12345" in url
        assert "response_type=code" in url
        assert "state=my-launch-id" in url
        assert "redirect_uri=" in url

    def test_strips_trailing_slash_from_canvas_url(self):
        url = build_auth_url(
            canvas_url="https://canvas.example.com/",
            client_id="99",
            redirect_uri="https://tool.example.com/callback",
            state="state-abc",
        )
        assert "//" not in url.split("?")[0].replace("https://", "")


class TestStoreAndGetToken:
    def test_store_and_retrieve_token(self, dynamodb_table):
        expires_at = int(time.time()) + 3600

        store_canvas_token(
            course_id="COURSE-123",
            canvas_user_id="user-456",
            access_token="test-access-token",
            expires_at=expires_at,
            table=dynamodb_table,
        )

        result = get_canvas_token(
            course_id="COURSE-123",
            canvas_user_id="user-456",
            table=dynamodb_table,
        )
        assert result == "test-access-token"

    def test_get_returns_none_for_missing(self, dynamodb_table):
        result = get_canvas_token(
            course_id="NONEXISTENT",
            canvas_user_id="user-999",
            table=dynamodb_table,
        )
        assert result is None

    def test_store_overwrites_existing_token(self, dynamodb_table):
        expires_at = int(time.time()) + 3600

        store_canvas_token(
            course_id="C1",
            canvas_user_id="U1",
            access_token="old-token",
            expires_at=expires_at,
            table=dynamodb_table,
        )
        store_canvas_token(
            course_id="C1",
            canvas_user_id="U1",
            access_token="new-token",
            expires_at=expires_at,
            table=dynamodb_table,
        )

        result = get_canvas_token(
            course_id="C1",
            canvas_user_id="U1",
            table=dynamodb_table,
        )
        assert result == "new-token"

    def test_tokens_are_scoped_per_user_and_course(self, dynamodb_table):
        expires_at = int(time.time()) + 3600

        store_canvas_token(
            course_id="C1",
            canvas_user_id="U1",
            access_token="token-u1-c1",
            expires_at=expires_at,
            table=dynamodb_table,
        )
        store_canvas_token(
            course_id="C2",
            canvas_user_id="U1",
            access_token="token-u1-c2",
            expires_at=expires_at,
            table=dynamodb_table,
        )

        assert get_canvas_token("C1", "U1", dynamodb_table) == "token-u1-c1"
        assert get_canvas_token("C2", "U1", dynamodb_table) == "token-u1-c2"


class TestExchangeCodeForToken:
    @pytest.mark.anyio
    async def test_exchange_success(self):
        from src.lti.oauth import exchange_code_for_token

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "canvas-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.lti.oauth.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await exchange_code_for_token(
                canvas_url="https://canvas.example.com",
                client_id="12345",
                client_secret="secret",
                code="auth-code-123",
                redirect_uri="https://tool.example.com/callback",
            )

        assert result["access_token"] == "canvas-access-token"
        assert result["expires_in"] == 3600

"""Unit tests for LTI state store, key manager, and JWT validation."""

import time
from unittest.mock import Mock, patch

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa

from src.lti.jwt_validation import validate_launch_token
from src.lti.key_manager import get_private_key, get_public_jwk
from src.lti.state import LTIStateStore


class TestLTIStateStore:
    def test_create_and_validate(self, dynamodb_table):
        store = LTIStateStore(table=dynamodb_table)
        state, nonce = store.create("https://canvas.test")

        result = store.validate(state)
        assert result is not None
        assert result["nonce"] == nonce
        assert result["platform_id"] == "https://canvas.test"

    def test_validate_unknown_state_returns_none(self, dynamodb_table):
        store = LTIStateStore(table=dynamodb_table)
        assert store.validate("nonexistent") is None

    def test_validate_deletes_state(self, dynamodb_table):
        """State is single-use — second validation returns None."""
        store = LTIStateStore(table=dynamodb_table)
        state, _ = store.create("https://canvas.test")

        store.validate(state)
        assert store.validate(state) is None

    def test_ttl_is_set(self, dynamodb_table):
        store = LTIStateStore(table=dynamodb_table)
        state, _ = store.create("https://canvas.test")

        response = dynamodb_table.get_item(
            Key={"pk": f"LTI_STATE#{state}", "sk": "STATE"}
        )
        item = response["Item"]
        assert "ttl" in item
        assert int(item["ttl"]) > int(time.time())


class TestKeyManager:
    def test_get_public_jwk_returns_valid_jwk(self, lti_env_vars):
        get_private_key.cache_clear()
        get_public_jwk.cache_clear()

        jwk = get_public_jwk()
        assert jwk["kty"] == "RSA"
        assert jwk["alg"] == "RS256"
        assert jwk["use"] == "sig"
        assert jwk["kid"] == "grading-helper-1"
        assert "n" in jwk
        assert "e" in jwk

        get_private_key.cache_clear()
        get_public_jwk.cache_clear()


class TestValidateLaunchToken:
    def _make_token(self, private_key, claims_override=None):
        """Create a signed JWT with LTI claims."""
        claims = {
            "iss": "https://canvas.test",
            "aud": "client-123",
            "sub": "user-456",
            "nonce": "test-nonce",
            "exp": int(time.time()) + 300,
            "iat": int(time.time()),
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "deploy-1",
        }
        if claims_override:
            claims.update(claims_override)
        return pyjwt.encode(claims, private_key, algorithm="RS256")

    def _mock_jwks_client(self, public_key):
        """Create a mock PyJWKClient that returns the given public key."""
        mock_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = public_key
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        return mock_client

    def test_valid_token(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = self._make_token(private_key)

        with patch("src.lti.jwt_validation.get_jwks_client") as mock_get:
            mock_get.return_value = self._mock_jwks_client(private_key.public_key())
            claims = validate_launch_token(
                id_token=token,
                jwks_url="https://canvas.test/jwks",
                client_id="client-123",
                issuer="https://canvas.test",
                nonce="test-nonce",
                deployment_id="deploy-1",
            )
        assert claims["sub"] == "user-456"

    def test_wrong_nonce_raises(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = self._make_token(private_key)

        with patch("src.lti.jwt_validation.get_jwks_client") as mock_get:
            mock_get.return_value = self._mock_jwks_client(private_key.public_key())
            try:
                validate_launch_token(
                    id_token=token,
                    jwks_url="https://canvas.test/jwks",
                    client_id="client-123",
                    issuer="https://canvas.test",
                    nonce="wrong-nonce",
                    deployment_id="deploy-1",
                )
                assert False, "Should have raised"
            except pyjwt.InvalidTokenError:
                pass

    def test_wrong_audience_raises(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = self._make_token(private_key)

        with patch("src.lti.jwt_validation.get_jwks_client") as mock_get:
            mock_get.return_value = self._mock_jwks_client(private_key.public_key())
            try:
                validate_launch_token(
                    id_token=token,
                    jwks_url="https://canvas.test/jwks",
                    client_id="wrong-client",
                    issuer="https://canvas.test",
                    nonce="test-nonce",
                    deployment_id="deploy-1",
                )
                assert False, "Should have raised"
            except pyjwt.InvalidTokenError:
                pass

    def test_wrong_deployment_id_raises(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = self._make_token(private_key)

        with patch("src.lti.jwt_validation.get_jwks_client") as mock_get:
            mock_get.return_value = self._mock_jwks_client(private_key.public_key())
            try:
                validate_launch_token(
                    id_token=token,
                    jwks_url="https://canvas.test/jwks",
                    client_id="client-123",
                    issuer="https://canvas.test",
                    nonce="test-nonce",
                    deployment_id="wrong-deploy",
                )
                assert False, "Should have raised"
            except pyjwt.InvalidTokenError:
                pass

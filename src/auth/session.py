"""RS256 JWT session tokens for instructor authentication."""

import functools
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.lti.key_manager import get_private_key


class SessionUser(BaseModel):
    """Decoded session token payload."""

    launch_id: str
    course_id: str
    canvas_user_id: str


@functools.lru_cache
def _get_public_key():
    """Load RSA public key from private key for JWT verification."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(get_private_key().encode(), password=None)
    return private_key.public_key()


def create_session_token(launch_id: str, course_id: str, canvas_user_id: str) -> str:
    """Create a signed RS256 JWT session token valid for 1 hour."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key_pem = get_private_key()
    private_key = load_pem_private_key(private_key_pem.encode(), password=None)

    now = int(time.time())
    payload = {
        "sub": canvas_user_id,
        "course_id": course_id,
        "launch_id": launch_id,
        "iss": "grading-helper",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


_bearer = HTTPBearer(auto_error=False)


def require_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> SessionUser:
    """FastAPI dependency: validates Bearer token, returns SessionUser.

    Raises 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    try:
        public_key = _get_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer="grading-helper",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session token: {e}")

    try:
        return SessionUser(
            launch_id=payload["launch_id"],
            course_id=payload["course_id"],
            canvas_user_id=payload["sub"],
        )
    except KeyError as e:
        raise HTTPException(
            status_code=401, detail=f"Invalid session token: missing claim {e}"
        )

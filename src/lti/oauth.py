"""Canvas OAuth2 Authorization Code flow helpers."""

from urllib.parse import urlencode

import httpx

from src.core.aws import get_dynamodb_table


CANVAS_API_SCOPES = [
    "url:GET|/api/v1/courses/:course_id/quizzes",
    "url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/questions",
    "url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions",
    "url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submissions",
    "url:PUT|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id",
]


def build_auth_url(
    canvas_url: str, client_id: str, redirect_uri: str, state: str
) -> str:
    """Build Canvas OAuth2 authorization URL."""
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(CANVAS_API_SCOPES),
            "state": state,
        }
    )
    return f"{canvas_url.rstrip('/')}/login/oauth2/auth?{params}"


async def exchange_code_for_token(
    canvas_url: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict:
    """Exchange authorization code for Canvas OAuth2 access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{canvas_url.rstrip('/')}/login/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


def store_canvas_token(
    course_id: str,
    canvas_user_id: str,
    access_token: str,
    expires_at: int,
    table=None,
) -> None:
    """Store Canvas OAuth access token in DynamoDB with TTL."""
    if table is None:
        table = get_dynamodb_table()
    table.put_item(
        Item={
            "pk": f"CANVAS_TOKEN#{canvas_user_id}",
            "sk": f"COURSE#{course_id}",
            "access_token": access_token,
            "ttl": expires_at,
        }
    )


def delete_canvas_token(
    course_id: str,
    canvas_user_id: str,
    table=None,
) -> None:
    """Delete a stored Canvas OAuth token (e.g. when Canvas returns 401)."""
    if table is None:
        table = get_dynamodb_table()
    table.delete_item(
        Key={
            "pk": f"CANVAS_TOKEN#{canvas_user_id}",
            "sk": f"COURSE#{course_id}",
        }
    )


def get_canvas_token(
    course_id: str,
    canvas_user_id: str,
    table=None,
) -> str | None:
    """Look up stored Canvas OAuth access token from DynamoDB.

    Returns access_token string or None if expired or not found.
    DynamoDB TTL deletion is eventually consistent, so we check expiry ourselves.
    """
    import time

    if table is None:
        table = get_dynamodb_table()
    response = table.get_item(
        Key={
            "pk": f"CANVAS_TOKEN#{canvas_user_id}",
            "sk": f"COURSE#{course_id}",
        }
    )
    item = response.get("Item")
    if item is None:
        return None
    # Check expiry — ttl is epoch seconds
    ttl = item.get("ttl")
    if ttl and int(ttl) < int(time.time()):
        return None
    return item.get("access_token")

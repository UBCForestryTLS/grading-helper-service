"""LTI Advantage Services (AGS) grade passback to Canvas."""

import time
from datetime import datetime, timezone
from uuid import UUID

import httpx
import jwt

from src.lti.key_manager import get_private_key


def get_ags_token(client_id: str, auth_token_url: str) -> str:
    """Obtain an AGS access token via LTI client credentials JWT assertion.

    Signs a JWT with the tool's private key and exchanges it for an access token
    at the platform's OAuth2 token endpoint.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(get_private_key().encode(), password=None)

    now = int(time.time())
    assertion_payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": auth_token_url,
        "iat": now,
        "exp": now + 300,
        "jti": f"ags-{now}",
    }

    client_assertion = jwt.encode(
        assertion_payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "grading-helper-1"},
    )

    scope = " ".join(
        [
            "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
            "https://purl.imsglobal.org/spec/lti-ags/scope/score",
        ]
    )

    response = httpx.post(
        auth_token_url,
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": (
                "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
            ),
            "client_assertion": client_assertion,
            "scope": scope,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def submit_score(
    lineitem_url: str,
    token: str,
    user_id: str,
    score: float,
    max_score: float,
    comment: str | None = None,
) -> dict:
    """POST a score to a Canvas AGS lineitem scores endpoint.

    Uses Content-Type: application/vnd.ims.lis.v1.score+json as required by
    the IMS LTI AGS specification.
    """
    payload: dict = {
        "userId": user_id,
        "scoreGiven": score,
        "scoreMaximum": max_score,
        "activityProgress": "Completed",
        "gradingProgress": "FullyGraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if comment:
        payload["comment"] = comment

    response = httpx.post(
        f"{lineitem_url}/scores",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.ims.lis.v1.score+json",
        },
    )
    response.raise_for_status()
    return response.json()


def passback_job_grades(
    job_id: str,
    launch_id: str,
    submission_repo=None,
    launch_store=None,
    table=None,
) -> dict:
    """Push AI grades for all graded submissions in a job back to Canvas via AGS.

    Returns {"submitted": N, "errors": [...]} with counts and any per-submission errors.
    """
    from src.core.config import get_settings
    from src.lti.launch_store import LaunchStore
    from src.repositories.submission import SubmissionRepository

    if submission_repo is None:
        submission_repo = SubmissionRepository(table=table)
    if launch_store is None:
        launch_store = LaunchStore(table=table)

    launch = launch_store.get(launch_id)
    if launch is None:
        return {"submitted": 0, "errors": [f"Launch {launch_id} not found"]}

    lineitem_url = launch.get("ags_lineitem_url", "")
    if not lineitem_url:
        return {"submitted": 0, "errors": ["No AGS lineitem URL in launch context"]}

    settings = get_settings()
    try:
        token = get_ags_token(
            client_id=settings.lti_client_id,
            auth_token_url=settings.lti_auth_token_url,
        )
    except Exception as e:
        return {"submitted": 0, "errors": [f"Failed to get AGS token: {e}"]}

    submissions = submission_repo.list_by_job(UUID(job_id))
    submitted = 0
    errors: list[str] = []

    for sub in submissions:
        if sub.ai_grade is None:
            continue
        try:
            submit_score(
                lineitem_url=lineitem_url,
                token=token,
                user_id=sub.canvas_user_id or str(sub.submission_id),
                score=sub.ai_grade,
                max_score=sub.points_possible,
                comment=sub.ai_feedback,
            )
            submitted += 1
        except Exception as e:
            errors.append(f"Submission {sub.submission_id}: {e}")

    return {"submitted": submitted, "errors": errors}

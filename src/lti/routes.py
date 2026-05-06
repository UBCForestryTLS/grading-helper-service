"""LTI 1.3 endpoints: OIDC login, launch, JWKS, tool configuration, and Canvas integration."""

import logging
from html import escape
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from src.auth.session import SessionUser, create_session_token, require_session
from src.core.config import get_settings
from src.lti.jwt_validation import validate_launch_token
from src.lti.key_manager import get_public_jwk
from src.lti.launch_store import LaunchStore
from src.lti.state import LTIStateStore
from src.lti.ui import render_instructor_ui

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lti", tags=["lti"])
jwks_router = APIRouter(tags=["lti"])


@router.get("/login")
@router.post("/login")
async def lti_login(request: Request):
    """OIDC login initiation.

    Canvas sends iss, login_hint, target_link_uri, client_id, lti_message_hint.
    We generate state+nonce, store in DynamoDB, redirect to Canvas auth URL.
    """
    params = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        params.update(form)

    settings = get_settings()

    iss = params.get("iss", "")
    if iss != settings.lti_iss:
        raise HTTPException(status_code=400, detail=f"Unknown issuer: {iss}")

    if params.get("client_id") and params["client_id"] != settings.lti_client_id:
        raise HTTPException(status_code=400, detail="Unknown client_id")

    state_store = LTIStateStore()
    state, nonce = state_store.create(iss)

    redirect_params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "prompt": "none",
        "client_id": settings.lti_client_id,
        "redirect_uri": params.get(
            "target_link_uri", f"{settings.base_url}/lti/launch"
        ),
        "login_hint": params.get("login_hint", ""),
        "state": state,
        "nonce": nonce,
    }
    if params.get("lti_message_hint"):
        redirect_params["lti_message_hint"] = params["lti_message_hint"]

    redirect_url = f"{settings.lti_auth_login_url}?{urlencode(redirect_params)}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/launch")
async def lti_launch(request: Request):
    """LTI launch callback. Validates JWT, stores launch context, renders instructor UI."""
    form = await request.form()
    id_token = form.get("id_token")
    state = form.get("state")

    if not id_token or not state:
        raise HTTPException(status_code=400, detail="Missing id_token or state")

    settings = get_settings()
    state_store = LTIStateStore()

    state_data = state_store.validate(state)
    if state_data is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    try:
        claims = validate_launch_token(
            id_token=id_token,
            jwks_url=settings.lti_key_set_url,
            client_id=settings.lti_client_id,
            issuer=settings.lti_iss,
            nonce=state_data["nonce"],
            deployment_id=settings.lti_deployment_id,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid launch token: {e}")

    # Store launch context and create session token
    context = claims.get("https://purl.imsglobal.org/spec/lti/claim/context", {})
    custom = claims.get("https://purl.imsglobal.org/spec/lti/claim/custom", {})
    roles_raw = claims.get("https://purl.imsglobal.org/spec/lti/claim/roles", [])
    # Prefer Canvas numeric IDs from custom claims; fall back to opaque LTI IDs
    course_id = str(custom.get("canvas_course_id", context.get("id", "")))
    canvas_user_id = str(custom.get("canvas_user_id", claims.get("sub", "")))

    launch_store = LaunchStore()
    launch_id = launch_store.create(claims)
    session_token = create_session_token(launch_id, course_id, canvas_user_id)

    allowed_roles = ["Instructor", "TeachingAssistant", "Administrator"]

    # Build roles list, only allowing expected roles
    roles = []
    for r in roles_raw:
        role_name = r.split("#")[-1]
        if role_name in allowed_roles:
            roles.append(escape(role_name))
        else:
            raise ValueError(f"Unexpected role in launch token: {r}")

    html = render_instructor_ui(
        launch_id=launch_id,
        session_token=session_token,
        base_url=settings.base_url,
        user_name=claims.get("name", ""),
        course_title=context.get("title", ""),
        roles=roles,
    )
    return HTMLResponse(content=html)


@router.get("/config")
def lti_config():
    """Canvas LTI tool configuration JSON for admin registration."""
    settings = get_settings()
    base = settings.base_url

    return JSONResponse(
        content={
            "title": "UBC Forestry Grading Helper",
            "description": "AI-powered grading assistant for short-answer questions",
            "oidc_initiation_url": f"{base}/lti/login",
            "target_link_uri": f"{base}/lti/launch",
            "public_jwk_url": f"{base}/.well-known/jwks.json",
            "scopes": [
                # AGS — grade passback (type-agnostic)
                "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
                "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly",
                "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly",
                "https://purl.imsglobal.org/spec/lti-ags/scope/score",
                # NRPS — course roster
                "https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly",
            ],
            "extensions": [
                {
                    "platform": "canvas.instructure.com",
                    "privacy_level": "public",
                    "settings": {
                        "placements": [
                            {
                                "placement": "course_navigation",
                                "message_type": "LtiResourceLinkRequest",
                                "target_link_uri": f"{base}/lti/launch",
                            },
                        ],
                    },
                }
            ],
            "custom_fields": {
                "canvas_course_id": "$Canvas.course.id",
                "canvas_user_id": "$Canvas.user.id",
            },
        }
    )


# --- Canvas integration routes ---


def _extract_answers(submission_data: list[dict]) -> list[dict]:
    """Extract student answers from Canvas submission_data.

    Canvas stores answers differently per question type:
    - essay_question / short_answer_question: answer text in "text" field
    - fill_in_multiple_blanks_question: answer in "answer_for_<blank>" fields, "text" is empty
    """
    answers = []
    for item in submission_data:
        question_id = item.get("question_id")
        # Primary answer field
        answer = item.get("text", "")

        # For fill_in_multiple_blanks, text is empty — collect answer_for_* fields
        if not answer:
            blank_answers = []
            for key, value in item.items():
                if key.startswith("answer_for_") and value:
                    blank_answers.append(str(value))
            if blank_answers:
                answer = "; ".join(blank_answers)

        answers.append({"question_id": question_id, "answer": answer})
    return answers


class LTIJobCreate(BaseModel):
    """Request body for creating a grading job via LTI."""

    launch_id: str
    quiz_id: str
    quiz_title: str = ""


class PassbackRequest(BaseModel):
    """Request body for AGS grade passback."""

    launch_id: str


@router.get("/quizzes")
def list_lti_quizzes(
    launch_id: str = Query(...),
    session: SessionUser = Depends(require_session),
):
    """List quizzes for the course from Canvas REST API.

    Requires a valid Canvas OAuth token stored for this user/course.
    Returns 401 if not yet authorized via OAuth.
    """
    from httpx import HTTPStatusError

    from src.lti.canvas_api import CanvasAPIClient
    from src.lti.oauth import delete_canvas_token, get_canvas_token

    settings = get_settings()
    if not settings.api_canvas_url:
        raise HTTPException(status_code=503, detail="Canvas API URL not configured")

    token = get_canvas_token(
        course_id=session.course_id,
        canvas_user_id=session.canvas_user_id,
    )
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Canvas OAuth token not found. Please authorize via /lti/oauth/authorize.",
        )

    logger.info(
        "list_lti_quizzes: user=%s, course=%s, token_prefix=%s",
        session.canvas_user_id,
        session.course_id,
        token[:10] + "..." if token else "None",
    )

    try:
        with CanvasAPIClient(settings.api_canvas_url, token) as client:
            return client.list_quizzes(session.course_id)
    except HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.warning(
                "Canvas 401: user=%s, course=%s, response=%s",
                session.canvas_user_id,
                session.course_id,
                e.response.text[:500],
            )
            delete_canvas_token(session.course_id, session.canvas_user_id)
            raise HTTPException(
                status_code=401,
                detail=f"Canvas rejected token: {e.response.text[:200]}",
            )
        raise


@router.post("/jobs")
def lti_create_job(
    body: LTIJobCreate,
    session: SessionUser = Depends(require_session),
):
    """Create a grading job by fetching quiz data from Canvas and ingesting it."""
    from httpx import HTTPStatusError

    from src.lti.canvas_api import CanvasAPIClient
    from src.lti.oauth import delete_canvas_token, get_canvas_token
    from src.services.ingestion import IngestionService

    settings = get_settings()
    if not settings.api_canvas_url:
        raise HTTPException(status_code=503, detail="Canvas API URL not configured")

    token = get_canvas_token(
        course_id=session.course_id,
        canvas_user_id=session.canvas_user_id,
    )
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Canvas OAuth token not found. Please authorize first.",
        )

    job_name = body.quiz_title or f"Quiz {body.quiz_id}"
    try:
        with CanvasAPIClient(settings.api_canvas_url, token) as canvas_client:
            # Use list_quizzes and filter instead of get_quiz, because the
            # individual quiz scope (quizzes/:id) isn't on the API key — only
            # the list scope (quizzes) is.
            quizzes = canvas_client.list_quizzes(session.course_id)
            quiz = next(
                (q for q in quizzes if str(q.get("id")) == str(body.quiz_id)),
                None,
            )
            if not quiz:
                raise HTTPException(
                    status_code=404, detail=f"Quiz {body.quiz_id} not found"
                )
            assignment_id = quiz.get("assignment_id")
            logger.info(
                "lti_create_job: quiz=%s, assignment_id=%s, quiz_type=%s, "
                "course_id=%s, canvas_user_id=%s",
                body.quiz_id,
                assignment_id,
                quiz.get("quiz_type"),
                session.course_id,
                session.canvas_user_id,
            )

            questions = canvas_client.get_quiz_questions(
                session.course_id, body.quiz_id
            )
            quiz_submissions = canvas_client.get_quiz_submissions(
                session.course_id, body.quiz_id
            )

            # Get student answers via Assignments API (submission_history).
            # Requires "Allow Include Parameters" enabled on the Canvas API
            # Developer Key — without it, Canvas silently ignores include[].
            answers_by_user: dict[str, list[dict]] = {}
            if assignment_id:
                assignment_subs = canvas_client.get_assignment_submissions(
                    session.course_id, str(assignment_id)
                )

                # Build answers keyed by user_id from submission_data
                for sub in assignment_subs:
                    user_id = str(sub.get("user_id", ""))
                    for attempt in sub.get("submission_history", []):
                        sd = attempt.get("submission_data")
                        if sd:
                            answers_by_user[user_id] = _extract_answers(sd)

            if not answers_by_user and quiz_submissions:
                logger.warning(
                    "No student answers found for %d quiz submissions. "
                    "Ensure 'Allow Include Parameters' is enabled on the "
                    "Canvas API Developer Key.",
                    len(quiz_submissions),
                )
    except HTTPStatusError as e:
        if e.response.status_code == 401:
            delete_canvas_token(session.course_id, session.canvas_user_id)
            raise HTTPException(
                status_code=401,
                detail="Canvas token expired or revoked. Please re-authorize.",
            )
        logger.exception("Canvas API error")
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch quiz data from Canvas: {e}"
        )
    except Exception as e:
        logger.exception("Failed to fetch quiz data from Canvas")
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch quiz data from Canvas: {e}"
        )

    service = IngestionService()
    try:
        job = service.ingest_from_canvas_api(
            course_id=session.course_id,
            quiz_id=body.quiz_id,
            job_name=job_name,
            questions=questions,
            quiz_submissions=quiz_submissions,
            answers_by_user=answers_by_user,
            assignment_id=str(assignment_id or ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return job


@router.post("/passback/{job_id}")
def lti_passback(
    job_id: str,
    body: PassbackRequest,
    session: SessionUser = Depends(require_session),
):
    """Push AI grades for a completed job back to Canvas.

    For quiz-based jobs: uses Canvas REST API to update per-question scores on the
    existing quiz submission (preserves MC grades, no new gradebook column).
    Fallback: AGS passback for non-quiz jobs.
    """
    from uuid import UUID

    from src.lti.ags import passback_job_grades, passback_quiz_grades_via_rest
    from src.lti.oauth import get_canvas_token
    from src.repositories.grading_job import GradingJobRepository

    job = GradingJobRepository().get(UUID(job_id))
    if job and job.quiz_id:
        token = get_canvas_token(
            course_id=session.course_id,
            canvas_user_id=session.canvas_user_id,
        )
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Canvas token not found. Re-authorize first.",
            )
        settings = get_settings()
        result = passback_quiz_grades_via_rest(
            job_id=job_id,
            quiz_id=job.quiz_id,
            course_id=session.course_id,
            canvas_token=token,
            canvas_url=settings.api_canvas_url,
        )
    else:
        result = passback_job_grades(
            job_id=job_id,
            launch_id=body.launch_id,
        )
    return result


@router.get("/oauth/authorize")
async def oauth_authorize(launch_id: str = Query(...)):
    """Redirect instructor to Canvas OAuth2 authorization page."""
    from src.lti.oauth import build_auth_url

    settings = get_settings()
    if not settings.api_canvas_url or not settings.api_client_id:
        raise HTTPException(status_code=503, detail="Canvas OAuth not configured")

    redirect_uri = f"{settings.base_url}/lti/oauth/callback"
    auth_url = build_auth_url(
        canvas_url=settings.api_canvas_url,
        client_id=settings.api_client_id,
        redirect_uri=redirect_uri,
        state=launch_id,
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
):
    """Handle Canvas OAuth2 callback: exchange code for token and store it."""
    from src.lti.launch_store import LaunchStore
    from src.lti.oauth import exchange_code_for_token, store_canvas_token

    if error:
        raise HTTPException(
            status_code=400, detail=f"OAuth authorization failed: {error}"
        )
    if not code or not state:
        raise HTTPException(
            status_code=400, detail="Missing code or state in OAuth callback"
        )

    settings = get_settings()
    launch_id = state

    launch = LaunchStore().get(launch_id)
    if launch is None:
        raise HTTPException(
            status_code=400, detail="Invalid OAuth state (launch not found)"
        )

    redirect_uri = f"{settings.base_url}/lti/oauth/callback"
    try:
        token_data = await exchange_code_for_token(
            canvas_url=settings.api_canvas_url,
            client_id=settings.api_client_id,
            client_secret=settings.api_client_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Failed to exchange OAuth code: {e}"
        )

    import time

    logger.info(
        "OAuth token exchange success: user=%s, course=%s, expires_in=%s, token_prefix=%s",
        launch["canvas_user_id"],
        launch["course_id"],
        token_data.get("expires_in"),
        token_data.get("access_token", "")[:10] + "...",
    )

    expires_at = int(time.time()) + token_data.get("expires_in", 3600)
    store_canvas_token(
        course_id=launch["course_id"],
        canvas_user_id=launch["canvas_user_id"],
        access_token=token_data["access_token"],
        expires_at=expires_at,
    )

    # Return a simple confirmation page; the instructor can reload the tool
    html = """<!DOCTYPE html>
<html><head><title>Authorized</title></head>
<body>
  <h2>Canvas access authorized successfully.</h2>
  <p>You can now close this page and reload the grading tool.</p>
</body>
</html>"""
    return HTMLResponse(content=html)


@jwks_router.get("/.well-known/jwks.json")
def jwks():
    """Serve the tool's public JWKS for Canvas to verify our signed messages."""
    return JSONResponse(content={"keys": [get_public_jwk()]})

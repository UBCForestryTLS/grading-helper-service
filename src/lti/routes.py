"""LTI 1.3 endpoints: OIDC login, launch, JWKS, and tool configuration."""

from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.core.config import get_settings
from src.lti.jwt_validation import validate_launch_token
from src.lti.key_manager import get_public_jwk
from src.lti.state import LTIStateStore

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
    """LTI launch callback. Validates the JWT id_token from Canvas."""
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

    return _render_launch_page(claims)


def _render_launch_page(claims: dict) -> HTMLResponse:
    context = claims.get("https://purl.imsglobal.org/spec/lti/claim/context", {})
    roles = claims.get("https://purl.imsglobal.org/spec/lti/claim/roles", [])
    name = escape(claims.get("name", "Unknown User"))
    email = escape(claims.get("email", ""))
    course_title = escape(context.get("title", "Unknown Course"))
    course_label = escape(context.get("label", ""))
    role_labels = [escape(r.split("/")[-1]) for r in roles]

    html = f"""<!DOCTYPE html>
<html>
<head><title>Grading Helper</title></head>
<body>
    <h1>Grading Helper Service</h1>
    <p>User: {name} ({email})</p>
    <p>Course: {course_title} ({course_label})</p>
    <p>Roles: {", ".join(role_labels)}</p>
    <p><em>Full UI coming soon.</em></p>
</body>
</html>"""
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
                "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
                "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly",
                "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly",
                "https://purl.imsglobal.org/spec/lti-ags/scope/score",
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


@jwks_router.get("/.well-known/jwks.json")
def jwks():
    """Serve the tool's public JWKS for Canvas to verify our signed messages."""
    return JSONResponse(content={"keys": [get_public_jwk()]})

# API Reference

This page documents all HTTP endpoints exposed by the Grading Helper Service. The API is built with FastAPI and runs behind API Gateway with a `/{stage}` prefix (e.g., `/dev/health`). Mangum strips this prefix before routing.

## Authentication

Most endpoints require an RS256 JWT Bearer token in the `Authorization` header. These tokens are created during the LTI launch and are valid for 1 hour.

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

The token contains `launch_id`, `course_id`, and `canvas_user_id`. The `require_session` FastAPI dependency validates the token and returns a `SessionUser` object. All `/jobs` endpoints and most `/lti` endpoints use this dependency.

```mermaid
sequenceDiagram
    participant Client as Instructor SPA
    participant APIGW as API Gateway
    participant Lambda as Lambda (FastAPI)

    Client->>APIGW: GET /jobs<br/>Authorization: Bearer {token}
    APIGW->>Lambda: Strip /dev prefix, forward
    Lambda->>Lambda: require_session dependency<br/>Decode RS256 JWT, check exp/iss
    alt Token valid
        Lambda->>Lambda: Route handler executes<br/>with SessionUser context
        Lambda-->>Client: 200 OK + JSON response
    else Token invalid/expired
        Lambda-->>Client: 401 Unauthorized
    end
```

## Health

### `GET /health`

No authentication required. Returns the service status and current stage.

**Response:**
```json
{
  "status": "healthy",
  "stage": "dev"
}
```

---

## Jobs

All jobs endpoints require a valid session token. Jobs are scoped to the session's `course_id` — accessing a job from a different course returns 403.

### `POST /jobs`

Create a new grading job from Canvas quiz export data.

- **Auth:** Required
- **Status:** 201 Created
- **Course check:** `body.course_id` must match `session.course_id` (403 if mismatch)

**Request body:**
```json
{
  "course_id": "12345",
  "quiz_id": "67890",
  "job_name": "Midterm Quiz Grading",
  "canvas_data": {
    "short_answer_question": [...],
    "fill_in_multiple_blanks_question": [...]
  }
}
```

**Response:** `GradingJob` object (see [Data Models](../data-models/index.md))

```json
{
  "job_id": "a1b2c3d4-...",
  "course_id": "12345",
  "quiz_id": "67890",
  "job_name": "Midterm Quiz Grading",
  "status": "PENDING",
  "total_questions": 5,
  "total_submissions": 120,
  "created_at": "2026-03-10T15:30:00+00:00",
  "updated_at": "2026-03-10T15:30:00+00:00",
  "error_message": null
}
```

### `GET /jobs`

List all grading jobs for the session's course. Optionally filter by status.

- **Auth:** Required
- **Query params:** `?status=PENDING` (optional, one of `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`)

**Response:** Array of `GradingJob` objects

### `GET /jobs/{job_id}`

Get a single grading job by ID.

- **Auth:** Required
- **Errors:** 404 if job not found, 403 if job belongs to a different course

**Response:** `GradingJob` object

### `POST /jobs/{job_id}/grade`

Start AI grading for all submissions in a job. Uses Bedrock Claude Haiku 4.5 with up to 10 concurrent requests.

- **Auth:** Required
- **Errors:** 404 if job not found, 403 if wrong course, 409 if job is not in `PENDING` status
- The job status transitions: `PENDING` -> `PROCESSING` -> `COMPLETED` (or `FAILED`)

**Response:** Updated `GradingJob` object

### `GET /jobs/{job_id}/submissions`

List all submissions for a grading job, including AI grades and feedback if grading is complete.

- **Auth:** Required
- **Errors:** 404 if job not found, 403 if wrong course

**Response:** Array of `Submission` objects

```json
[
  {
    "submission_id": "e5f6g7h8-...",
    "job_id": "a1b2c3d4-...",
    "question_id": 1001,
    "question_name": "Q1",
    "question_type": "short_answer_question",
    "question_text": "What is photosynthesis?",
    "points_possible": 5.0,
    "student_answer": "The process by which plants convert sunlight...",
    "canvas_points": 0.0,
    "correct_answers": ["The process of converting light energy..."],
    "canvas_user_id": "42",
    "ai_grade": 4.5,
    "ai_feedback": "Good understanding of the core concept...",
    "ai_graded_at": "2026-03-10T15:35:00+00:00"
  }
]
```

---

## LTI Endpoints

These endpoints handle the LTI 1.3 integration with Canvas. Most are called by Canvas during the launch flow or by the instructor SPA after launch.

### `GET/POST /lti/login`

OIDC login initiation. Canvas sends `iss`, `login_hint`, `target_link_uri`, `client_id`.

- **Auth:** None (Canvas-initiated)
- **Response:** 302 redirect to Canvas auth URL

### `POST /lti/launch`

LTI launch callback. Receives the signed `id_token` and `state` via form POST.

- **Auth:** None (validates JWT internally)
- **Response:** 200 HTML (instructor SPA with embedded session token)
- **Errors:** 400 (missing params or invalid state), 401 (invalid JWT)

### `GET /lti/config`

Returns the LTI tool configuration JSON for Canvas admin registration.

- **Auth:** None (public)
- **Response:** JSON with OIDC URLs, scopes, placements, custom fields

### `GET /.well-known/jwks.json`

Serves the tool's RSA public key in JWKS format.

- **Auth:** None (public)
- **Response:** `{"keys": [{"kty": "RSA", "alg": "RS256", ...}]}`

### `GET /lti/quizzes`

List quizzes for the session's course from the Canvas REST API.

- **Auth:** Required (session token)
- **Query params:** `launch_id` (required)
- **Errors:** 401 (no Canvas OAuth token — redirect to `/lti/oauth/authorize`), 503 (Canvas URL not configured)

### `POST /lti/jobs`

Create a grading job by fetching quiz data directly from Canvas.

- **Auth:** Required (session token)
- **Request body:**
```json
{
  "launch_id": "abc123",
  "quiz_id": "67890",
  "quiz_title": "Midterm Quiz"
}
```
- **Errors:** 401 (no Canvas token), 502 (Canvas API failure), 503 (not configured)

### `POST /lti/passback/{job_id}`

Push AI grades for a completed job back to Canvas via AGS.

- **Auth:** Required (session token)
- **Request body:**
```json
{
  "launch_id": "abc123"
}
```
- **Response:**
```json
{
  "submitted": 118,
  "errors": ["Submission xyz: 403 Forbidden"]
}
```

### `GET /lti/oauth/authorize`

Redirect the instructor to Canvas OAuth2 authorization page.

- **Auth:** None
- **Query params:** `launch_id` (required)
- **Response:** 302 redirect to Canvas
- **Errors:** 503 (OAuth not configured)

### `GET /lti/oauth/callback`

Handle Canvas OAuth2 callback — exchange code for token and store it.

- **Auth:** None (Canvas-initiated)
- **Query params:** `code`, `state` (launch_id), optionally `error`
- **Response:** 200 HTML confirmation page
- **Errors:** 400 (missing params, invalid launch), 502 (token exchange failed)

---

## Error Codes

| Code | Meaning | When |
|------|---------|------|
| 400 | Bad Request | Missing/invalid parameters, bad LTI state, OAuth errors |
| 401 | Unauthorized | Missing or invalid session token, no Canvas OAuth token |
| 403 | Forbidden | Job/resource belongs to a different course than the session |
| 404 | Not Found | Job or resource does not exist |
| 409 | Conflict | Trying to grade a job that is not in PENDING status |
| 422 | Unprocessable Entity | Request body validation failed (Pydantic) |
| 502 | Bad Gateway | Canvas API or OAuth token exchange failed |
| 503 | Service Unavailable | Canvas API URL or OAuth not configured |

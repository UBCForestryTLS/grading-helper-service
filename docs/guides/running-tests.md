# Running Tests Guide

This guide covers running the test suite, understanding the test fixtures, and writing new tests.

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific file
uv run pytest tests/test_jobs_api.py -v

# Run a specific test by name
uv run pytest tests/ -v -k "test_create_job_success"

# Run with stdout visible (useful for debugging)
uv run pytest tests/ -v -s
```

## Test Stack

| Tool | Purpose |
|------|---------|
| **pytest** | Test runner and framework |
| **moto** | In-process AWS service mocking (DynamoDB, S3, SSM) |
| **httpx** | ASGI test client for FastAPI (replaces requests for async apps) |

No real AWS calls are ever made during testing. All AWS services are fully mocked by moto.

## Key Fixtures

All fixtures are defined in `tests/conftest.py`.

### `aws_credentials` (session scope)

Sets dummy AWS environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`). This ensures boto3 never accidentally connects to real AWS.

### `dynamodb_table` (function scope)

Creates a moto-mocked DynamoDB table that matches the schema defined in `template.yaml` — same key schema, same GSIs, same TTL attribute. Returns the table resource object.

Use this fixture when testing repository classes:

```python
def test_create_and_get_job(dynamodb_table):
    repo = GradingJobRepository(table=dynamodb_table)
    job = GradingJob(course_id="C1", quiz_id="Q1", job_name="Test")
    repo.create(job)
    result = repo.get(job.job_id)
    assert result.job_name == "Test"
```

### `lti_env_vars` (function scope)

Generates a real RSA key pair (2048-bit), sets all LTI-related environment variables, and clears all `lru_cache`s (`get_settings`, `get_private_key`, `get_public_jwk`, `_get_public_key`). The caches are also cleared on teardown.

Use this fixture for any test involving LTI launch, session tokens, or JWT operations.

### `session_token` (function scope)

Creates a valid RS256 session token for course `C100` with `canvas_user_id="user-1"`. Depends on `lti_env_vars`.

Use this for testing authenticated endpoints:

```python
def test_list_jobs(client, session_token):
    response = client.get(
        "/jobs",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert response.status_code == 200
```

### `sample_canvas_data` (session scope)

A minimal Canvas quiz export dict with one `short_answer_question` containing one question, two answers, and two submissions. Used for ingestion tests.

## Writing New Tests

### Testing an API Endpoint

1. Create a test client using httpx's `TestClient`:

```python
from httpx import ASGITransport, AsyncClient
from src.api.app import create_app

app = create_app()

def test_my_endpoint(dynamodb_table, session_token):
    # If your endpoint uses repos, patch the dependency
    with TestClient(app) as client:
        response = client.get(
            "/jobs",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert response.status_code == 200
```

2. For endpoints that need DynamoDB, either:
    - Inject the moto table into the repository via the `table=` parameter
    - Use the test client within a `mock_aws()` context and the `dynamodb_table` fixture

### Testing a Repository

Pass the `dynamodb_table` fixture directly:

```python
def test_batch_create_submissions(dynamodb_table):
    repo = SubmissionRepository(table=dynamodb_table)
    subs = [Submission(job_id=some_uuid, ...)]
    repo.batch_create(subs)
    result = repo.list_by_job(some_uuid)
    assert len(result) == 1
```

### Testing LTI/OAuth Code

Use `lti_env_vars` and patch external HTTP calls at the import site:

```python
from unittest.mock import patch

def test_list_quizzes(lti_env_vars, session_token):
    with patch("src.lti.routes.get_canvas_token", return_value="fake-token"):
        with patch("src.lti.routes.CanvasAPIClient") as mock_client:
            mock_client.return_value.__enter__.return_value.list_quizzes.return_value = []
            # Make the request...
```

## Common Pitfalls

### Forgetting to clear `lru_cache`

If you modify environment variables in a test without using the `lti_env_vars` fixture, you must manually clear the caches:

```python
from src.core.config import get_settings
from src.lti.key_manager import get_private_key, get_public_jwk
from src.auth.session import _get_public_key

get_settings.cache_clear()
get_private_key.cache_clear()
get_public_jwk.cache_clear()
_get_public_key.cache_clear()
```

### Patching httpx in the wrong module

Both `src/lti/oauth.py` and `src/lti/ags.py` import httpx. If you patch `httpx.post` directly, you might affect both modules. Instead, patch at the specific import site:

```python
# Correct
@patch("src.lti.routes.get_canvas_token")

# Risky — affects all modules that import httpx
@patch("httpx.post")
```

### Course ID mismatch in session tests

The `session_token` fixture creates a token for course `C100`. If your test data uses a different course ID, you'll get a 403. Either:

- Use `C100` as your test course ID
- Create a custom session token for your test's course ID

### DynamoDB table not available

Make sure your test function accepts the `dynamodb_table` fixture parameter, and that the fixture is inside a `@mock_aws` decorated function or context. The `dynamodb_table` fixture handles this automatically.

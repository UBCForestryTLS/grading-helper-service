# Development

This page covers everything you need to set up a development environment, understand the project structure, run tests, and contribute code.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.13 | Runtime |
| [uv](https://docs.astral.sh/uv/) | Latest | Package management, virtual environments |
| [AWS CLI](https://aws.amazon.com/cli/) | v2 | AWS operations |
| [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) | Latest | Build and deploy Lambda functions |
| Docker | Latest | Required by `sam build` for cross-compilation |
| [pre-commit](https://pre-commit.com/) | Latest | Git hooks for linting/formatting |

## Getting Started

```bash
# Clone the repository
git clone https://github.com/forestrytls/grading-helper-service.git
cd grading-helper-service

# Install dependencies
uv sync

# Install pre-commit hooks
pre-commit install

# Run tests to verify everything works
uv run pytest tests/ -v
```

## Project Structure

```
grading-helper-service/
├── src/
│   ├── handlers/
│   │   └── api.py                 # Lambda entrypoint (Mangum wraps FastAPI)
│   ├── api/
│   │   ├── app.py                 # FastAPI app factory
│   │   └── routes/
│   │       ├── health.py          # GET /health
│   │       └── jobs.py            # CRUD for /jobs (session auth required)
│   ├── lti/
│   │   ├── routes.py              # LTI endpoints + Canvas integration routes
│   │   ├── jwt_validation.py      # Canvas JWT verification
│   │   ├── key_manager.py         # RSA key loading (env var or SSM)
│   │   ├── state.py               # LTI OIDC state+nonce (DynamoDB)
│   │   ├── launch_store.py        # Launch context storage (DynamoDB)
│   │   ├── oauth.py               # Canvas OAuth2 helpers
│   │   ├── canvas_api.py          # Canvas REST API client
│   │   ├── ags.py                 # AGS grade passback
│   │   └── ui.py                  # Instructor SPA HTML renderer
│   ├── auth/
│   │   └── session.py             # RS256 JWT session tokens
│   ├── core/
│   │   ├── config.py              # Settings (pydantic_settings, lru_cached)
│   │   └── aws.py                 # boto3 client/resource factories
│   ├── models/
│   │   ├── grading_job.py         # GradingJob, GradingJobCreate, JobStatus
│   │   ├── submission.py          # Submission model
│   │   └── canvas.py              # Canvas quiz export models
│   ├── repositories/
│   │   ├── grading_job.py         # GradingJobRepository (DynamoDB)
│   │   └── submission.py          # SubmissionRepository (DynamoDB)
│   └── services/
│       ├── ingestion.py           # Parse Canvas data → Job + Submissions
│       └── grading.py             # Bedrock AI grading (concurrent)
├── tests/
│   ├── conftest.py                # Shared fixtures (moto, DynamoDB, RSA keys)
│   ├── test_health.py
│   ├── test_jobs_api.py
│   ├── test_lti_routes.py
│   └── ...
├── docs/                          # MkDocs documentation
├── template.yaml                  # SAM template
├── Makefile                       # Lambda build recipe
├── samconfig.toml                 # SAM deployment config
├── pyproject.toml                 # Python project + dependencies
└── mkdocs.yml                     # MkDocs configuration
```

## Development Workflow

```mermaid
flowchart LR
    Code["Write Code"] --> Lint["pre-commit\n(Ruff lint + format)"]
    Lint --> Test["pytest\n(moto mocks)"]
    Test --> Build["sam build\n(Makefile)"]
    Build --> Deploy["sam deploy"]
    Deploy --> Verify["Test on AWS"]
```

## Running Locally

### Tests (recommended for most development)

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_jobs_api.py -v

# Run a specific test by name
uv run pytest tests/ -v -k "test_create_job"
```

### Local API Gateway

```bash
# Export requirements (needed before sam build)
uv export --no-hashes --no-dev -o requirements.txt

# Build the Lambda
sam build

# Start local API (requires Docker)
sam local start-api
```

The local API runs at `http://localhost:3000`. Note that LTI endpoints won't work locally since they require Canvas to initiate the OIDC flow.

### Required Environment Variables for Local

If running with `sam local`, set these in a `env.json` file:

```json
{
  "ApiFunction": {
    "TABLE_NAME": "your-table-name",
    "BUCKET_NAME": "your-bucket-name",
    "STAGE": "local",
    "BASE_URL": "http://localhost:3000",
    "LTI_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
  }
}
```

Then run: `sam local start-api --env-vars env.json`

## Commands Reference

| Command | Description |
|---------|-------------|
| `uv sync` | Install all dependencies |
| `uv add <package>` | Add a runtime dependency |
| `uv add --group dev <package>` | Add a dev dependency |
| `pre-commit run --all-files` | Run all linting/formatting hooks |
| `ruff check --fix .` | Lint with auto-fix |
| `ruff format .` | Format code |
| `uv run pytest tests/ -v` | Run all tests |
| `uv run pytest tests/ -v -k "name"` | Run specific test |
| `uv export --no-hashes --no-dev -o requirements.txt` | Export deps for SAM |
| `sam build` | Build Lambda (uses Makefile) |
| `sam local start-api` | Local API at localhost:3000 |
| `sam deploy --no-confirm-changeset` | Deploy to AWS |
| `mkdocs serve` | Local docs at localhost:8000 |

## Code Quality

### Ruff

[Ruff](https://docs.astral.sh/ruff/) handles both linting and formatting. It replaces flake8, pylint, isort, and black in a single tool. Configuration is in `pyproject.toml`.

### Pre-commit Hooks

Pre-commit runs Ruff on every commit. Install with `pre-commit install`. To run manually:

```bash
pre-commit run --all-files
```

## Testing

Tests use **pytest** with **moto** for AWS mocking and **httpx** for FastAPI test clients. No real AWS calls are made during testing.

### Key Fixtures (`tests/conftest.py`)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `aws_credentials` | session | Sets dummy AWS env vars so boto3 never hits real AWS |
| `dynamodb_table` | function | Creates a moto-mocked DynamoDB table matching `template.yaml` schema |
| `sample_canvas_data` | session | Minimal Canvas quiz export JSON for ingestion tests |
| `lti_env_vars` | function | Generates a real RSA key pair, sets all LTI env vars, clears all caches |
| `session_token` | function | Creates a valid RS256 session token for course `C100` |

### Testing Patterns

**Repository injection** — pass the moto table directly:
```python
def test_create_job(dynamodb_table):
    repo = GradingJobRepository(table=dynamodb_table)
    repo.create(some_job)
```

**Cache clearing** — the `lti_env_vars` fixture clears `get_settings`, `get_private_key`, `get_public_jwk`, and `_get_public_key` caches on setup and teardown. If you modify env vars in a test, you must clear these caches yourself.

**Patching Canvas calls** — patch at the import site, not at httpx:
```python
# Correct
@patch("src.lti.routes.get_canvas_token", return_value="fake-token")

# Wrong — this would affect both oauth.py and ags.py
@patch("httpx.post")
```

**Session auth** — use the `session_token` fixture:
```python
def test_list_jobs(client, session_token):
    response = client.get("/jobs", headers={"Authorization": f"Bearer {session_token}"})
```

## Adding a New Endpoint

1. Create or edit a route file in `src/api/routes/` or `src/lti/routes.py`
2. Add `session: SessionUser = Depends(require_session)` if authentication is needed
3. Register the router in `src/api/app.py` if it's a new file
4. Write tests using the httpx test client and appropriate fixtures
5. Run `pre-commit run --all-files` and `uv run pytest tests/ -v`

## Adding a New DynamoDB Entity

1. Choose a `pk`/`sk` pattern that doesn't collide with existing entities (see [Data Models](../data-models/index.md))
2. Create a repository class in `src/repositories/` following the existing pattern:
    - Accept `table=None` in `__init__`
    - Use a lazy `table` property that calls `get_dynamodb_table()` if not injected
    - Implement `_to_item()` and `_from_item()` for serialization
3. If the entity needs a GSI, add the GSI attributes in `_to_item()` and update `template.yaml`
4. If the entity needs TTL, include a `ttl` attribute with the Unix timestamp
5. Write tests using the `dynamodb_table` fixture

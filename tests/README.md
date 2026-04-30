# Tests

All tests run locally with no AWS credentials or infrastructure required.

## Running

```bash
uv run pytest tests/ -v              # full suite
uv run pytest tests/test_models.py -v # single file
```

## How It Works

Tests use **moto** to mock AWS services in-memory. The `dynamodb_table` fixture in `conftest.py` creates a fake DynamoDB table matching the schema in `template.yaml` (pk/sk, GSI1, GSI2). The `aws_credentials` fixture sets dummy values so boto3 never attempts real AWS calls.

API tests use FastAPI's `TestClient`, which makes in-process HTTP calls with no real server. `get_dynamodb_table` is patched to return the moto table.

## Test Files

| File | Layer | AWS Mocking? | What it covers |
|---|---|---|---|
| `test_health.py` | API | No | `GET /health` returns 200 with status and stage |
| `test_models.py` | Models | No | Pydantic validation, defaults, UUID generation, Canvas export parsing, rejection of bad data |
| `test_repositories.py` | Repositories | Yes (moto) | DynamoDB CRUD, GSI queries (by course, by status), status updates, float roundtrips, job isolation |
| `test_ingestion.py` | Services | Yes (moto) | End-to-end ingestion: Canvas parsing, job/submission creation, correct answer extraction |
| `test_jobs_api.py` | API | Yes (moto) | HTTP endpoints: POST/GET, 201/200/400/404/422 responses, query filtering |

## Fixtures (conftest.py)

- **`aws_credentials`** — Sets dummy AWS env vars so boto3 never hits real AWS.
- **`dynamodb_table`** — Creates a moto DynamoDB table with the same schema as `template.yaml`. Yields the table inside a `mock_aws` context. Used by repository, service, and API tests.
- **`sample_canvas_data`** — Minimal valid Canvas quiz export (1 short-answer question, 2 correct answers, 2 student submissions). Reused across model, ingestion, and API tests.

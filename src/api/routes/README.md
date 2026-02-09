# Routes

FastAPI route modules. Each file defines an `APIRouter` that gets included in the app via `src/api/app.py`.

## Files

- **`health.py`** -- `GET /health` endpoint. Returns service status and deployment stage.
- **`jobs.py`** -- Grading job management endpoints:

| Method | Path | Description |
|---|---|---|
| `POST /jobs` | Create a grading job from Canvas quiz export data | Returns 201 |
| `GET /jobs/{job_id}` | Get a single job by ID | Returns 200 or 404 |
| `GET /jobs?course_id=X` | List jobs for a course (GSI1 query) | Returns 200 |
| `GET /jobs?status=X` | List jobs by status (GSI2 query) | Returns 200 |
| `GET /jobs/{job_id}/submissions` | List submissions for a job | Returns 200 or 404 |

`GET /jobs` requires either `course_id` or `status` to prevent full table scans.

## Adding a New Route

1. Create a new file (e.g., `grading.py`) with `router = APIRouter(prefix="/...", tags=["..."])`
2. Add `app.include_router(router)` in `src/api/app.py`

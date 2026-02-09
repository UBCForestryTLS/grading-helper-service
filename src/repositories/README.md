# Repositories

Data access layer for DynamoDB. Each repository class translates between Pydantic domain models and raw DynamoDB items, so the rest of the app never deals with partition keys, sort keys, or `Decimal` types.

## Single-Table Design

All entities live in one DynamoDB table with composite keys:

| Entity | `pk` | `sk` | `GSI1PK` | `GSI1SK` | `GSI2PK` | `GSI2SK` |
|---|---|---|---|---|---|---|
| GradingJob | `JOB#{job_id}` | `METADATA` | `COURSE#{course_id}` | `JOB#{created_at}` | `STATUS#{status}` | `JOB#{job_id}` |
| Submission | `JOB#{job_id}` | `SUB#{submission_id}` | -- | -- | -- | -- |

## Files

- **`grading_job.py`** -- CRUD for grading jobs. Supports lookup by ID, listing by course (GSI1), listing by status (GSI2), and status updates.
- **`submission.py`** -- CRUD for submissions. Supports batch creation, listing by job, and single-item lookup.

## Testing

All repositories accept an optional `table` parameter in their constructor. In production, the real DynamoDB table is lazily fetched via `src.core.aws.get_dynamodb_table()`. In tests, a moto-mocked table is injected directly.

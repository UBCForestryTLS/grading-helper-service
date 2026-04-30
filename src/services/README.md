# Services

Business logic layer. Services orchestrate operations across repositories and handle domain-specific transformations.

## Files

- **`ingestion.py`** -- `IngestionService.ingest()` parses a raw Canvas quiz JSON export into a `GradingJob` with associated `Submission` records and persists them to DynamoDB. This is the entry point for getting quiz data into the system.

## Design

Services accept repositories as optional constructor parameters, defaulting to real instances. This allows tests to inject repositories backed by moto-mocked DynamoDB tables.

```python
service = IngestionService(job_repo=mock_repo, sub_repo=mock_repo)  # test
service = IngestionService()  # production
```

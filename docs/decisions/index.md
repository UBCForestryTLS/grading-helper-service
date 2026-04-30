# Design Decisions

This page records the key technology and architectural decisions made during development, along with the reasoning behind each.

---

## UV Package Manager

We use [UV](https://docs.astral.sh/uv/) for dependency management instead of pip or Poetry.

**Why?** UV is 10-100x faster (written in Rust), provides a lock file for reproducibility, and handles venv + dependencies in one tool. Backed by Astral (creators of Ruff).

---

## Ruff

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting instead of flake8, pylint, isort, or black.

**Why?** Ruff replaces multiple tools in one, is 10-100x faster (written in Rust), and provides consistent linting + formatting. Also from Astral, so pairs well with UV.

---

## DynamoDB Single-Table Design

All entities (GradingJob, Submission, LTI State, Launch Context, Canvas Token) share one DynamoDB table with composite `pk`/`sk` keys and two GSIs.

**Why?** Single-table design is a DynamoDB best practice for serverless applications. It reduces the number of tables to manage (one table vs five), keeps CloudFormation simpler, and lets us co-locate related data. Two GSIs cover all our query patterns: jobs by course and jobs by status.

**Trade-offs:** Harder to reason about at first compared to one-table-per-entity. Requires careful key design upfront. We mitigate this by documenting all key patterns in the [Data Models](../data-models/index.md) page.

---

## Cookieless LTI Sessions

Session state is carried in RS256 JWT Bearer tokens instead of cookies.

**Why?** Canvas embeds the tool in an iframe. Most modern browsers block third-party cookies in iframes (Safari always, Chrome and Firefox increasingly). Using cookies for session management would break the tool in Canvas for a large fraction of users. JWT Bearer tokens in the `Authorization` header bypass this entirely.

**How it works:** After validating the LTI launch JWT, the tool creates a signed RS256 session token and embeds it in the instructor SPA's JavaScript. The SPA sends this token in `Authorization: Bearer <token>` headers on all subsequent API calls.

---

## Mangum

We use [Mangum](https://mangum.fastapiexpert.com/) to run FastAPI inside AWS Lambda.

**Why?** Mangum is a thin ASGI adapter that translates API Gateway events into ASGI requests and ASGI responses back into API Gateway format. It lets us write a standard FastAPI application and deploy it as a Lambda without any code changes. The `api_gateway_base_path` parameter handles stripping the `/{stage}` prefix that API Gateway adds.

**Alternative considered:** Writing a raw Lambda handler with manual routing. Rejected because we'd lose FastAPI's dependency injection, Pydantic validation, OpenAPI docs, and the ability to run the app locally with `uvicorn`.

---

## FastAPI

We chose [FastAPI](https://fastapi.tiangolo.com/) over Flask or Django.

**Why?**

- **Pydantic integration** — Request/response validation with type hints, automatic error responses for bad payloads
- **Dependency injection** — `Depends(require_session)` cleanly handles auth without decorators or middleware
- **Async support** — LTI routes use `async` for OAuth token exchange
- **OpenAPI docs** — Auto-generated at `/docs` (useful during development)
- **Performance** — ASGI-based, faster than WSGI frameworks on Lambda

**Alternative considered:** Flask — simpler, but lacks built-in Pydantic validation and dependency injection. Would need Flask-RESTful or similar extensions.

---

## AWS Bedrock with Claude Haiku 4.5

AI grading uses AWS Bedrock's managed Claude Haiku 4.5 (`anthropic.claude-haiku-4-5-20251001-v1:0`).

**Why?**

- **IAM authentication** — No API keys to manage or rotate. The Lambda's execution role has `bedrock:InvokeModel` permission. This simplifies secrets management and stays within AWS's security model.
- **Cost** — Haiku 4.5 is significantly cheaper than larger models while being accurate enough for grading short-answer questions
- **Speed** — Haiku responds quickly, which matters when grading 100+ submissions concurrently
- **Data residency** — Bedrock runs in `ca-central-1`, keeping student data in Canada

**Alternative considered:** Anthropic API directly. Would require managing an API key as a secret and adds a dependency outside AWS. Bedrock keeps everything under one IAM umbrella.

---

## ARM64 Lambda

The Lambda runs on Graviton2 (arm64) instead of x86_64.

**Why?** AWS charges 20% less for arm64 Lambda functions at the same memory and duration. The only complexity is cross-compiling native Python packages (like `cryptography`), which we handle with a Makefile that passes `--platform manylinux2014_aarch64` to pip.

---

## moto for AWS Testing

Tests mock AWS services using [moto](https://github.com/getmoto/moto) instead of LocalStack or real AWS.

**Why?**

- **Fast** — moto runs in-process, no Docker containers or network calls
- **Deterministic** — No flaky tests from network issues or service limits
- **Free** — No AWS costs for running tests
- **Good DynamoDB support** — moto accurately simulates DynamoDB queries, GSIs, and conditional operations

**Alternative considered:** LocalStack — more realistic but requires Docker, slower to start, and the free tier has limitations. moto is sufficient for our DynamoDB/S3/SSM usage.

---

## RS256 Session Tokens

Session tokens use RS256 (asymmetric) signing instead of HS256 (symmetric).

**Why?** We already have an RSA private key for LTI (required for JWKS and AGS JWT assertions). Reusing the same key for session tokens avoids introducing a second secret. RS256 also means any component that has the public key can verify tokens without knowing the private key.

---

## Repository Pattern with Table Injection

All repository classes accept an optional `table=` constructor argument.

**Why?** This lets tests inject a moto-mocked DynamoDB table directly, without patching `boto3` globally. It keeps test setup simple (pass the fixture) and avoids the fragility of mock patching across module boundaries.

```python
# Production — lazy loads real table
repo = GradingJobRepository()

# Tests — uses moto-mocked table
repo = GradingJobRepository(table=dynamodb_table)
```

**Alternative considered:** Patching `boto3.resource` with `unittest.mock`. Works but is brittle — if the import path changes or a new module also calls boto3, the patch misses it. Constructor injection is more explicit and reliable.

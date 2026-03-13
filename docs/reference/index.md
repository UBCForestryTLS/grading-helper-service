# Reference

Quick-lookup tables for environment variables, DynamoDB keys, error codes, LTI claims, Canvas API scopes, and other frequently referenced values.

## Environment Variables

### Lambda Runtime Variables

| Variable | Source | Required | Description | Example |
|----------|--------|----------|-------------|---------|
| `TABLE_NAME` | SAM (`!Ref GradingTable`) | Yes | DynamoDB table name | `grading-helper-service-GradingTable-ABC123` |
| `BUCKET_NAME` | SAM (`!Ref GradingBucket`) | Yes | S3 bucket name | `grading-helper-service-gradingbucket-xyz` |
| `STAGE` | SAM (`!Ref Stage`) | Yes | Deployment stage | `dev`, `staging`, `prod` |
| `POWERTOOLS_SERVICE_NAME` | SAM (hardcoded) | No | Lambda Powertools service name | `grading-helper` |
| `BASE_URL` | SAM (`!Ref BaseUrl`) | Yes | Public API Gateway URL | `https://xxx.execute-api.ca-central-1.amazonaws.com/dev` |
| `BEDROCK_MODEL_ID` | SAM (`!Ref BedrockModelId`) | No | Bedrock model ID | `anthropic.claude-haiku-4-5-20251001-v1:0` |
| `LTI_ISS` | SAM (`!Ref LtiIss`) | Yes | LTI platform issuer | `https://canvas.instructure.com` |
| `LTI_CLIENT_ID` | SAM (`!Ref LtiClientId`) | Yes | LTI Developer Key client ID | `your-lti-client-id` |
| `LTI_DEPLOYMENT_ID` | SAM (`!Ref LtiDeploymentId`) | Yes | LTI deployment ID | `your-deployment-id` |
| `LTI_AUTH_LOGIN_URL` | SAM (`!Ref LtiAuthLoginUrl`) | Yes | Canvas OIDC auth endpoint | `https://sso.canvaslms.com/api/lti/authorize_redirect` |
| `LTI_AUTH_TOKEN_URL` | SAM (`!Ref LtiAuthTokenUrl`) | Yes | Canvas OAuth2 token endpoint | `https://sso.canvaslms.com/login/oauth2/token` |
| `LTI_KEY_SET_URL` | SAM (`!Ref LtiKeySetUrl`) | Yes | Canvas public JWKS URL | `https://sso.canvaslms.com/api/lti/security/jwks` |
| `API_CLIENT_ID` | SAM (`!Ref ApiClientId`) | For OAuth | Canvas API Developer Key client ID | `your-api-client-id` |
| `API_CLIENT_SECRET` | SAM (`!Ref ApiClientSecret`) | For OAuth | Canvas API Developer Key client secret | `your-api-client-secret` |
| `API_CANVAS_URL` | SAM (`!Ref ApiCanvasUrl`) | For OAuth | Canvas instance base URL | `https://your-canvas-instance.instructure.com` |

### Settings-Only Variables (not in SAM template)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `LTI_PRIVATE_KEY` | No | RSA private key PEM inline (overrides SSM) | `-----BEGIN PRIVATE KEY-----\n...` |
| `LTI_PRIVATE_KEY_SSM_PARAM` | No | SSM parameter name for RSA key | `/grading-helper/lti-private-key` |
| `AWS_REGION` | No | AWS region (default: `ca-central-1`) | `ca-central-1` |

## SAM Parameters

| Parameter | Type | Default | Allowed Values |
|-----------|------|---------|---------------|
| `Stage` | String | `dev` | `dev`, `staging`, `prod` |
| `BaseUrl` | String | `""` | Any URL |
| `BedrockModelId` | String | `anthropic.claude-haiku-4-5-20251001-v1:0` | Any Bedrock model ID |
| `AllowedOrigin` | String | `*` | Any origin or `*` |
| `LtiIss` | String | `""` | Platform issuer URL |
| `LtiClientId` | String | `""` | Canvas client ID |
| `LtiDeploymentId` | String | `""` | Canvas deployment ID |
| `LtiAuthLoginUrl` | String | `""` | Canvas OIDC URL |
| `LtiAuthTokenUrl` | String | `""` | Canvas token URL |
| `LtiKeySetUrl` | String | `""` | Canvas JWKS URL |
| `ApiClientId` | String | `""` | Canvas API client ID |
| `ApiClientSecret` | String | `""` | Canvas API client secret |
| `ApiCanvasUrl` | String | `""` | Canvas instance URL |

## DynamoDB Key Schema

| Entity | `pk` | `sk` | GSI1PK | GSI1SK | GSI2PK | GSI2SK | TTL |
|--------|------|------|--------|--------|--------|--------|-----|
| GradingJob | `JOB#{job_id}` | `METADATA` | `COURSE#{course_id}` | `JOB#{created_at}` | `STATUS#{status}` | `JOB#{job_id}` | -- |
| Submission | `JOB#{job_id}` | `SUB#{submission_id}` | -- | -- | -- | -- | -- |
| LTI State | `LTI_STATE#{state}` | `STATE` | -- | -- | -- | -- | 10 min |
| Launch Context | `LAUNCH#{launch_id}` | `LAUNCH` | -- | -- | -- | -- | 24 hours |
| Canvas Token | `CANVAS_TOKEN#{canvas_user_id}` | `COURSE#{course_id}` | -- | -- | -- | -- | Token expiry |

## API Error Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 400 | Bad Request | Missing LTI params, invalid state, OAuth error callback |
| 401 | Unauthorized | Missing/expired session token, no Canvas OAuth token |
| 403 | Forbidden | Job belongs to different course than session |
| 404 | Not Found | Job ID doesn't exist |
| 409 | Conflict | Grading a job not in PENDING status |
| 422 | Unprocessable Entity | Pydantic validation failure on request body |
| 502 | Bad Gateway | Canvas API call failed, OAuth token exchange failed |
| 503 | Service Unavailable | Canvas API URL or OAuth not configured |

## LTI Claim URIs

These URIs are used as keys in the decoded LTI JWT claims dict:

| Claim URI | Purpose | Code Usage |
|-----------|---------|------------|
| `https://purl.imsglobal.org/spec/lti/claim/context` | Course context (id, title) | `launch_store.py`, `routes.py` |
| `https://purl.imsglobal.org/spec/lti/claim/roles` | User roles array | `routes.py` |
| `https://purl.imsglobal.org/spec/lti/claim/deployment_id` | Deployment ID | `jwt_validation.py` |
| `https://purl.imsglobal.org/spec/lti-ags/claim/endpoint` | AGS endpoint (lineitem URL, scope) | `launch_store.py` |
| `https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice` | NRPS memberships URL | `launch_store.py` |

## Canvas API Scopes

### LTI Developer Key Scopes

| Scope | Purpose |
|-------|---------|
| `https://purl.imsglobal.org/spec/lti-ags/scope/lineitem` | Create/manage AGS lineitems |
| `https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly` | Read AGS lineitems |
| `https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly` | Read AGS results |
| `https://purl.imsglobal.org/spec/lti-ags/scope/score` | Post AGS scores |
| `https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly` | Read course roster |

### API Developer Key Scopes

| Scope | Purpose |
|-------|---------|
| `url:GET\|/api/v1/courses/:course_id/quizzes` | List quizzes |
| `url:GET\|/api/v1/courses/:course_id/quizzes/:quiz_id/questions` | Get quiz questions |
| `url:GET\|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions` | Get quiz submissions |
| `url:GET\|/api/v1/courses/:course_id/assignments` | List assignments |
| `url:GET\|/api/v1/courses/:course_id/assignments/:assignment_id/submissions` | Get assignment submissions |
| `url:GET\|/api/v1/courses/:course_id/discussion_topics` | List discussions |
| `url:GET\|/api/v1/courses/:course_id/discussion_topics/:topic_id/entries` | Get discussion entries |

## Bedrock Configuration

| Setting | Value |
|---------|-------|
| Model ID | `anthropic.claude-haiku-4-5-20251001-v1:0` |
| `anthropic_version` | `bedrock-2023-05-31` |
| `max_tokens` | `512` |
| Concurrent workers | `10` (ThreadPoolExecutor) |
| Region | `ca-central-1` |

## Glossary

| Term | Definition |
|------|-----------|
| **LTI 1.3** | Learning Tools Interoperability v1.3 — IMS Global standard for connecting tools to LMS platforms |
| **OIDC** | OpenID Connect — authentication protocol used by LTI 1.3 for the login-to-launch flow |
| **AGS** | Assignment and Grade Services — LTI service for reading/writing grades in the LMS gradebook |
| **NRPS** | Names and Role Provisioning Services — LTI service for reading course roster data |
| **JWKS** | JSON Web Key Set — a set of public keys published at a URL for JWT verification |
| **JWT** | JSON Web Token — a signed token used for authentication and claims transfer |
| **SSM** | Systems Manager (Parameter Store) — AWS service for storing configuration and secrets |
| **SAM** | Serverless Application Model — AWS framework for defining and deploying serverless apps |
| **Mangum** | Python library that adapts ASGI apps (like FastAPI) to run inside AWS Lambda |
| **moto** | Python library that mocks AWS services for testing |
| **Pydantic** | Python library for data validation using type hints |

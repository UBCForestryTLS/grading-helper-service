# Local Setup Guide

This guide walks you through setting up a development environment from scratch.

## Prerequisites

Install these tools before starting:

1. **Python 3.13** — [python.org](https://www.python.org/downloads/) or via `pyenv`
2. **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. **AWS CLI v2** — [install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
4. **SAM CLI** — [install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
5. **Docker** — [docker.com](https://www.docker.com/products/docker-desktop/) (needed for `sam build`)
6. **pre-commit** — `pip install pre-commit` or `brew install pre-commit`

## Step 1: Clone and Install

```bash
git clone https://github.com/forestrytls/grading-helper-service.git
cd grading-helper-service
uv sync
```

This creates a virtual environment and installs all dependencies (including dev dependencies).

## Step 2: Install Pre-commit Hooks

```bash
pre-commit install
```

This sets up Ruff to run automatically on every `git commit`. You can also run it manually:

```bash
pre-commit run --all-files
```

## Step 3: Verify Tests Pass

```bash
uv run pytest tests/ -v
```

All 148 tests should pass. Tests use moto to mock AWS services — no real AWS credentials needed.

## Step 4: Configure AWS CLI (for deployment)

If you need to deploy to AWS:

```bash
aws configure
# Region: ca-central-1
# Output format: json
```

You need IAM credentials with permissions for CloudFormation, Lambda, API Gateway, DynamoDB, S3, SSM, and Bedrock.

## Step 5: Build and Run Locally (optional)

```bash
# Export requirements for SAM
uv export --no-hashes --no-dev -o requirements.txt

# Build the Lambda
sam build

# Start local API Gateway
sam local start-api
```

The API will be available at `http://localhost:3000`. Note that LTI endpoints won't work locally since they require Canvas to initiate the OIDC flow.

## Troubleshooting

### `uv sync` fails with Python version error

Make sure you have Python 3.13 installed. Check with `python3.13 --version`. If you're using pyenv:

```bash
pyenv install 3.13
pyenv local 3.13
```

### `sam build` fails

- Make sure Docker is running
- The Makefile hardcodes the pip path (`/opt/homebrew/bin/python3.13`). If your Python is installed elsewhere, update the Makefile or create a symlink.

### Tests fail with import errors

Run `uv sync` again to ensure all dependencies are installed. If you switched branches, the lock file may have changed.

### Pre-commit hook fails on commit

Run `ruff check --fix .` and `ruff format .` to fix issues, then try committing again.

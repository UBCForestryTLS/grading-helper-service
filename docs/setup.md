# Setup Guide

Complete installation and configuration guide for the Grading Helper Service.

## Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- AWS Account with Bedrock access
- Claude models enabled in your AWS region

## Installation

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd grading-helper-service
uv sync
```

This installs all required dependencies:
- boto3 (AWS SDK)
- pyyaml (Configuration management)
- python-dotenv (Environment variables)

### 2. AWS Configuration

#### Option A: Using Bearer Token (Temporary Access)

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```
AWS_REGION=ca-central-1
AWS_BEARER_TOKEN_BEDROCK=your_bearer_token_here
```

#### Option B: Using AWS CLI (Persistent Access)

Configure AWS CLI with your credentials:

```bash
aws configure
```

The application will use your default AWS profile automatically.

### 3. Verify Model Access

Check which Claude models are available in your region:

```bash
python scripts/list_available_models.py
```

Expected output should include models like:
```
anthropic.claude-3-sonnet-20240229-v1:0
anthropic.claude-3-haiku-20240307-v1:0
```

## Configuration

### Model Configuration

Edit `config/config.yaml` to adjust:

- Model IDs and versions
- Cost per token (for tracking)
- Default grading parameters
- Token limits

Example:
```yaml
grading:
  default_model: "anthropic.claude-3-sonnet-20240229-v1:0"
  temperature: 0.0
  max_tokens: 1000
```

### Prompt Configuration

Edit `config/prompts.yaml` to customize:

- System prompts (defines AI behavior)
- Grading templates (structures the input)
- Prompt versions (v1_basic, v2_strict, v3_constructive)

## Testing the Installation

### Quick Test

Run the test script with the example submission:

```bash
python scripts/test_grading.py
```

This will:
1. Load `data/samples/example_submission.json`
2. Initialize the grading engine
3. Call AWS Bedrock API
4. Display grading results
5. Save output to `data/results/`

Expected output:
```
Grade: 8/10

Feedback:
[AI-generated feedback on the submission]

Tokens: 450 in, 180 out, 630 total
Cost: $0.0041
```

### Test Different Prompt Versions

Modify `scripts/test_grading.py` to test different approaches:

```python
result = engine.grade_submission(
    question=submission_data["question"],
    rubric=submission_data["rubric"],
    student_response=submission_data["student_response"],
    system_prompt_version="v2_strict"  # or "v3_constructive"
)
```

## Cost Management

### Understanding AWS Bedrock Costs

Pricing varies by model (as of 2024):

```
Claude 3 Sonnet:
  Input:  $0.003 per 1K tokens (~$3 per million)
  Output: $0.015 per 1K tokens (~$15 per million)

Claude 3 Haiku:
  Input:  $0.00025 per 1K tokens (~$0.25 per million)
  Output: $0.00125 per 1K tokens (~$1.25 per million)
```

Typical grading request:
- Input: 300-600 tokens (question + rubric + response)
- Output: 150-300 tokens (grade + feedback)
- Cost per request: $0.01-0.05

### Cost Tracking

The system automatically tracks:
- Token usage per request
- Estimated cost per request
- Total tokens and cost across sessions

Monitor costs in the output:
```
Cost: $0.0041
```

## Troubleshooting

### Authentication Errors

**Error:** `ClientError: An error occurred (UnrecognizedClientException)`

**Solution:**
- Verify AWS credentials are correct
- Check that your AWS account has Bedrock access
- Ensure your region supports Bedrock

### Model Not Found

**Error:** `ValidationException: The provided model identifier is invalid`

**Solution:**
- Run `python scripts/list_available_models.py` to see available models
- Update `config/config.yaml` with a valid model ID
- Ensure model access is enabled in AWS Bedrock console

### Rate Limiting

**Error:** `ThrottlingException: Rate exceeded`

**Solution:**
- Implement exponential backoff (planned feature)
- Reduce request frequency
- Contact AWS to increase quotas

## Next Steps

- Review [Architecture Documentation](architecture.md) (coming soon)
- Explore different prompt strategies in `config/prompts.yaml`
- Test with your own sample submissions
- Review cost tracking before scaling up

## Development Mode

For active development:

```bash
# Run with verbose logging
export LOG_LEVEL=DEBUG
python scripts/test_grading.py

# Test configuration loading
python -c "from src.core.config import ConfigLoader; c = ConfigLoader(); print(c.load_config())"
```

## Security Notes

- Never commit `.env` file (contains credentials)
- Keep `AWS_BEARER_TOKEN_BEDROCK` secret
- Rotate credentials periodically
- Consider using IAM roles for production deployment
- Review student data handling for FERPA compliance

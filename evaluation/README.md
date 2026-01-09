# LLM Grading Evaluation

Evaluate whether LLMs can approximate instructor grading on short-answer questions.

## Quick Start

```bash
# Install dependencies
uv sync --group evaluation

# Create .env with AWS credentials
echo "AWS_ACCESS_KEY_ID=xxx" > .env
echo "AWS_SECRET_ACCESS_KEY=xxx" >> .env

# Run notebook
uv run jupyter lab
```

## Methodology

We test 2 prompt conditions:

| Condition | Description |
|-----------|-------------|
| **P1: Answer Only** | Question + acceptable answers + student response |
| **P2: Answer + Rubric** | Above + explicit grading criteria |

*Note: "LLM-Generated Rubric" was removed since short-answer questions (few words) don't need custom rubrics.*

## Results (Llama 3 70B)

**Yet to run full eval so no results for now**

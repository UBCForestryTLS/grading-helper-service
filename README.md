# Grading Helper Service

AI-powered autograding system for UBC Forestry courses using AWS Bedrock

## Quick Start

```bash
# Install dependencies
uv sync

# Configure AWS credentials
cp .env.example .env
# Edit .env with your AWS credentials

# Test the system
python scripts/test_grading.py
```

## Documentation

- [Setup Guide](docs/setup.md) - Detailed installation and configuration
- [Architecture](docs/architecture.md) - System design and decisions (coming soon)
- [API Reference](docs/api-reference.md) - REST API documentation (coming soon)

## Project Structure

```
├── config/          # YAML configuration (models, prompts)
├── data/            # Sample submissions and results
├── scripts/         # Utility scripts
├── src/
│   ├── core/        # Core grading logic
│   ├── api/         # REST API (planned)
│   └── lti/         # Canvas LTI integration (planned)
└── tests/           # Test suite
```

## Current Status

Phase 1 - Core Infrastructure (In Progress)

- [x] AWS Bedrock client wrapper
- [x] Configuration management
- [x] Grading engine with prompt templating
- [x] Pre-commit hooks for code quality
- [ ] REST API
- [ ] Cost tracking utilities
- [ ] Statistical evaluation (Cohen's Kappa)

## TODO - Development Priorities

### High Priority (Implement Next)

- [ ] **Testing Infrastructure**
  - [ ] Add pytest with coverage reporting
  - [ ] Unit tests for bedrock_client, config, grade_engine
  - [ ] Integration tests for end-to-end grading
  - [ ] Test fixtures and mocking setup

- [ ] **Type Checking**
  - [ ] Add mypy static type checking
  - [ ] Add type stubs for dependencies
  - [ ] Enforce type hints in pre-commit

- [ ] **Cost Tracking Class**
  - [ ] Dedicated CostTracker module
  - [ ] Session cost summaries
  - [ ] Cost logging to file
  - [ ] Budget warnings

- [ ] **Development Workflow**
  - [ ] Add Makefile for common commands
  - [ ] Improve logging configuration
  - [ ] Environment variable validation

### Medium Priority

- [ ] **CLI Interface**
  - [ ] Add Typer/Click for command-line interface
  - [ ] Rich terminal output
  - [ ] Commands: grade, batch-grade, list-models

- [ ] **CI/CD Pipeline**
  - [ ] GitHub Actions workflow
  - [ ] Automated testing on push
  - [ ] Linting and formatting checks
  - [ ] Coverage reporting

- [ ] **Documentation**
  - [ ] Architecture diagram (Mermaid)
  - [ ] Architecture Decision Records (ADRs)
  - [ ] API documentation
  - [ ] Contributing guidelines

### Lower Priority

- [ ] **Experiment Tracking**
  - [ ] MLflow integration for model comparison
  - [ ] Prompt performance metrics
  - [ ] Experiment versioning

- [ ] **Security**
  - [ ] Add detect-secrets pre-commit hook
  - [ ] Security scanning in CI
  - [ ] Secrets management best practices

- [ ] **Maintenance**
  - [ ] CHANGELOG.md following Keep a Changelog
  - [ ] Semantic versioning
  - [ ] Automated dependency updates

## License

[To be determined]

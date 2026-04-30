# Welcome

Official documentation for the UBC Faculty of Forestry [AI Grading Helper Service](https://github.com/forestrytls/grading-helper-service/)


## Navigation

| Section | Description |
|---------|-------------|
| **[Getting Started](getting-started/start_here.md)** | Learn about project origins, motivation, and user stories |
| **[Architecture](architecture/index.md)** | System design, component breakdown, and architectural patterns |
| **[LTI Integration](lti-integration/index.md)** | LTI 1.3 OIDC flow, Canvas setup, OAuth2, grade passback |
| **[Data Models](data-models/index.md)** | DynamoDB schema, entity keys, Pydantic models |
| **[API Reference](api/index.md)** | All HTTP endpoints with request/response examples |
| **[Design Decisions](decisions/index.md)** | Why we chose each technology and pattern |
| **[Development](development/index.md)** | Set up your environment and start contributing |
| **[Deployment](deployment/index.md)** | SAM template, CI/CD pipeline, infrastructure |
| **[Evaluation](evaluation/index.md)** | Planned grading accuracy validation |
| **[Guides](guides/index.md)** | Step-by-step guides for common tasks |
| **[Reference](reference/index.md)** | Environment variables, error codes, glossary |

## About This Project

The AI Grading Helper is a tool designed to support grading and feedback automation for large Forestry courses at UBC. It leverages AWS Bedrock's large language models to help teaching teams grade more efficiently while maintaining quality and pedagogical value.

!!! tip "Key Features"
    - Automated grading with AI-powered feedback
    - Rubric-aligned evaluation
    - Instructor override capabilities
    - Quality control workflows
    - LTI integration for seamless Canvas integration

## Why Write Documentation?

* I anyways like to write documentation
* Helps me be clear about design decisions
* Helps prevent [scope creep](https://en.wikipedia.org/wiki/Scope_creep)
* Might help future developers
* Nice to look at

!!! warning "A Note on AI-Generated Content"
    Although the mindful use of GenAI is encouraged in development, please avoid updating these docs using GenAI. Writing documentation yourself ensures better understanding and knowledge transfer.

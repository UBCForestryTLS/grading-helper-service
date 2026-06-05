"""Shared observability instances using AWS Lambda Powertools."""

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

# Logger reads POWERTOOLS_SERVICE_NAME from environment automatically
# Outputs structured JSON in Lambda, readable text locally when POWERTOOLS_DEV=true
logger = Logger()

# Metrics publishes to CloudWatch under the "GradingHelper" namespace
# You'll see these as graphs in CloudWatch → Metrics → Custom Namespaces
metrics = Metrics(namespace="GradingHelper")

# Tracer integrates with AWS X-Ray for request timing
tracer = Tracer()

__all__ = ["logger", "metrics", "tracer", "MetricUnit"]

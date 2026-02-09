"""Repository layer for DynamoDB operations."""

from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository

__all__ = [
    "GradingJobRepository",
    "SubmissionRepository",
]

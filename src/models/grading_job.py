"""Pydantic models for grading jobs."""

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GradingJob(BaseModel):
    """A grading job representing a batch grading run for a quiz."""

    job_id: UUID = Field(default_factory=uuid4)
    course_id: str
    quiz_id: str
    job_name: str
    status: JobStatus = JobStatus.PENDING
    total_questions: int = 0
    total_submissions: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: str | None = None


class GradingJobCreate(BaseModel):
    """Request body for creating a new grading job."""

    course_id: str
    quiz_id: str
    job_name: str
    canvas_data: dict

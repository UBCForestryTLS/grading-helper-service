"""REST API routes for grading job management."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from src.models.grading_job import GradingJob, GradingJobCreate, JobStatus
from src.models.submission import Submission
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository
from src.services.ingestion import IngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_ingestion_service() -> IngestionService:
    return IngestionService()


def _get_job_repo() -> GradingJobRepository:
    return GradingJobRepository()


def _get_sub_repo() -> SubmissionRepository:
    return SubmissionRepository()


@router.post("", status_code=201, response_model=GradingJob)
def create_job(body: GradingJobCreate) -> GradingJob:
    """Create a new grading job from Canvas quiz export data."""
    service = _get_ingestion_service()
    try:
        return service.ingest(
            course_id=body.course_id,
            quiz_id=body.quiz_id,
            job_name=body.job_name,
            canvas_data=body.canvas_data,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())


@router.get("/{job_id}", response_model=GradingJob)
def get_job(job_id: UUID) -> GradingJob:
    """Get a grading job by ID."""
    repo = _get_job_repo()
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=list[GradingJob])
def list_jobs(
    course_id: str | None = Query(None),
    status: JobStatus | None = Query(None),
) -> list[GradingJob]:
    """List grading jobs filtered by course_id or status.

    Exactly one filter must be provided to avoid table scans.
    """
    if course_id is None and status is None:
        raise HTTPException(
            status_code=400,
            detail="Must provide either course_id or status query parameter",
        )

    repo = _get_job_repo()
    if course_id is not None:
        return repo.list_by_course(course_id)
    return repo.list_by_status(status)


@router.get("/{job_id}/submissions", response_model=list[Submission])
def list_submissions(job_id: UUID) -> list[Submission]:
    """List all submissions for a grading job."""
    job_repo = _get_job_repo()
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    sub_repo = _get_sub_repo()
    return sub_repo.list_by_job(job_id)

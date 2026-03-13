"""REST API routes for grading job management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from src.auth.session import SessionUser, require_session
from src.models.grading_job import GradingJob, GradingJobCreate, JobStatus
from src.models.submission import Submission
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository
from src.services.grading import GradingService
from src.services.ingestion import IngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_ingestion_service() -> IngestionService:
    return IngestionService()


def _get_grading_service() -> GradingService:
    return GradingService()


def _get_job_repo() -> GradingJobRepository:
    return GradingJobRepository()


def _get_sub_repo() -> SubmissionRepository:
    return SubmissionRepository()


@router.post("", status_code=201, response_model=GradingJob)
def create_job(
    body: GradingJobCreate,
    session: SessionUser = Depends(require_session),
) -> GradingJob:
    """Create a new grading job from Canvas quiz export data."""
    if body.course_id != session.course_id:
        raise HTTPException(
            status_code=403,
            detail="course_id in request does not match session",
        )
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
def get_job(
    job_id: UUID,
    session: SessionUser = Depends(require_session),
) -> GradingJob:
    """Get a grading job by ID."""
    repo = _get_job_repo()
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.course_id != session.course_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return job


@router.get("", response_model=list[GradingJob])
def list_jobs(
    status: JobStatus | None = Query(None),
    session: SessionUser = Depends(require_session),
) -> list[GradingJob]:
    """List grading jobs for the session's course, optionally filtered by status."""
    repo = _get_job_repo()
    jobs = repo.list_by_course(session.course_id)
    if status is not None:
        jobs = [j for j in jobs if j.status == status]
    return jobs


@router.post("/{job_id}/grade", response_model=GradingJob)
def grade_job(
    job_id: UUID,
    session: SessionUser = Depends(require_session),
) -> GradingJob:
    """Start AI grading for a job's submissions."""
    job_repo = _get_job_repo()
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.course_id != session.course_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.status != JobStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Job is {job.status}, must be PENDING to grade",
        )

    service = _get_grading_service()
    service.grade_job(job_id)
    return job_repo.get(job_id)


@router.get("/{job_id}/submissions", response_model=list[Submission])
def list_submissions(
    job_id: UUID,
    session: SessionUser = Depends(require_session),
) -> list[Submission]:
    """List all submissions for a grading job."""
    job_repo = _get_job_repo()
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.course_id != session.course_id:
        raise HTTPException(status_code=403, detail="Access denied")

    sub_repo = _get_sub_repo()
    return sub_repo.list_by_job(job_id)

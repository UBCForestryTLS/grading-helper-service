"""REST API routes for grading job management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError, BaseModel

from src.auth.session import SessionUser, require_instructor
from src.core.observability import logger, metrics, MetricUnit
from src.core.validation import validate_grade
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
    session: SessionUser = Depends(require_instructor),
) -> GradingJob:
    """Create a new grading job from Canvas quiz export data."""

    logger.info("Creating job", course_id=session.course_id, quiz_id=str(body.quiz_id))

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
    session: SessionUser = Depends(require_instructor),
) -> GradingJob:
    """Get a grading job by ID."""
    logger.info("Getting job", job_id=str(job_id), course_id=session.course_id)
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
    session: SessionUser = Depends(require_instructor),
) -> list[GradingJob]:
    """List grading jobs for the session's course, optionally filtered by status."""
    logger.info("Listing jobs", course_id=session.course_id, status=status)
    repo = _get_job_repo()
    jobs = repo.list_by_course(session.course_id)
    if status is not None:
        jobs = [j for j in jobs if j.status == status]
    return jobs


@router.post("/{job_id}/grade", response_model=GradingJob)
def grade_job(
    job_id: UUID,
    session: SessionUser = Depends(require_instructor),
) -> GradingJob:
    """Start AI grading for a job's submissions."""
    logger.info("Starting grading", job_id=str(job_id), course_id=session.course_id)
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
    metrics.add_metric(name="GradingJobStarted", unit=MetricUnit.Count, value=1)
    service.grade_job(job_id)
    return job_repo.get(job_id)


@router.post("/{job_id}/cancel", response_model=GradingJob)
def cancel_job(
    job_id: UUID,
    session: SessionUser = Depends(require_instructor),
) -> GradingJob:
    """Cancel a pending or processing grading job."""
    logger.info("Cancelling job", job_id=str(job_id), course_id=session.course_id)
    job_repo = _get_job_repo()
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.course_id != session.course_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.status not in (JobStatus.PENDING, JobStatus.PROCESSING):
        raise HTTPException(
            status_code=409,
            detail=f"Job is {job.status}, must be PENDING or PROCESSING to cancel",
        )

    cancelled = job_repo.cancel(job_id)
    if cancelled is None:
        job = job_repo.get(job_id)
        raise HTTPException(
            status_code=409,
            detail=f"Job could not be cancelled (current status: {job.status if job else 'unknown'})",
        )
    logger.info("Job cancelled", job_id=str(job_id))
    metrics.add_metric(name="GradingJobCancelled", unit=MetricUnit.Count, value=1)
    return cancelled


@router.post("/{job_id}/retry-failed", response_model=GradingJob)
def retry_failed_job(
    job_id: UUID,
    session: SessionUser = Depends(require_instructor),
) -> GradingJob:
    """Retry only the submissions that failed on a partially-completed job."""
    logger.info(
        "Retrying failed submissions", job_id=str(job_id), course_id=session.course_id
    )
    job_repo = _get_job_repo()
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.course_id != session.course_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.status != JobStatus.COMPLETED_WITH_ERRORS:
        raise HTTPException(
            status_code=409,
            detail=f"Job is {job.status}, must be COMPLETED_WITH_ERRORS to retry",
        )

    service = _get_grading_service()
    metrics.add_metric(name="GradingJobRetried", unit=MetricUnit.Count, value=1)
    service.retry_failed(job_id)
    return job_repo.get(job_id)


@router.get("/{job_id}/submissions", response_model=list[Submission])
def list_submissions(
    job_id: UUID,
    session: SessionUser = Depends(require_instructor),
) -> list[Submission]:
    """List all submissions for a grading job."""
    logger.info(
        "Listing submissions for job", job_id=str(job_id), course_id=session.course_id
    )
    job_repo = _get_job_repo()
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.course_id != session.course_id:
        raise HTTPException(status_code=403, detail="Access denied")

    sub_repo = _get_sub_repo()
    return sub_repo.list_by_job(job_id)


class SubmissionOverrideRequest(BaseModel):
    grade: float | None = None
    feedback: str | None = None
    revert: bool = False


@router.patch("/{job_id}/submissions/{submission_id}", response_model=Submission)
def override_submission(
    job_id: UUID,
    submission_id: UUID,
    body: SubmissionOverrideRequest,
    session: SessionUser = Depends(require_instructor),
) -> Submission:
    """Set or clear an instructor override on a submission's grade/feedback."""
    job_repo = _get_job_repo()
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.course_id != session.course_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.status not in (JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS):
        raise HTTPException(
            status_code=409,
            detail=f"Job is {job.status}, must be COMPLETED or COMPLETED_WITH_ERRORS to override a grade",
        )

    sub_repo = _get_sub_repo()
    submission = sub_repo.get(job_id, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if body.grade is None and body.feedback is None and not body.revert:
        raise HTTPException(status_code=422, detail="Nothing to update.")

    if body.revert:
        updated = sub_repo.clear_override(job_id, submission_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        return updated

    if body.grade is not None:
        error = validate_grade(body.grade, submission.points_possible)
        if error:
            raise HTTPException(status_code=422, detail=error)

    updated = sub_repo.set_override(
        job_id,
        submission_id,
        body.grade,
        body.feedback,
        session.canvas_user_id,
    )

    if updated is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    return updated

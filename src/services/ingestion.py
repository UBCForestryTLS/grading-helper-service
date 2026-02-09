"""Service for ingesting Canvas quiz exports into grading jobs."""

from uuid import uuid4

from src.models.canvas import CanvasQuizExport
from src.models.grading_job import GradingJob
from src.models.submission import Submission
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository


class IngestionService:
    """Parses Canvas data and creates grading jobs with submissions."""

    def __init__(
        self,
        job_repo: GradingJobRepository | None = None,
        sub_repo: SubmissionRepository | None = None,
    ):
        self.job_repo = job_repo or GradingJobRepository()
        self.sub_repo = sub_repo or SubmissionRepository()

    def ingest(
        self, course_id: str, quiz_id: str, job_name: str, canvas_data: dict
    ) -> GradingJob:
        """Parse Canvas data and create a grading job with submissions.

        Args:
            course_id: The Canvas course ID.
            quiz_id: The Canvas quiz ID.
            job_name: Human-readable name for the job.
            canvas_data: Raw Canvas quiz export dict.

        Returns:
            The created GradingJob.
        """
        export = CanvasQuizExport.model_validate(canvas_data)
        questions = export.all_questions

        job_id = uuid4()
        submissions: list[Submission] = []

        for question in questions:
            correct_answers = [
                answer.text for answer in question.answers if answer.weight == 100
            ]
            for student_sub in question.submissions:
                submissions.append(
                    Submission(
                        job_id=job_id,
                        question_id=question.id,
                        question_name=question.question_name,
                        question_type=question.question_type,
                        question_text=question.question_text,
                        points_possible=question.points_possible,
                        student_answer=student_sub.answer,
                        canvas_points=student_sub.points,
                        correct_answers=correct_answers,
                    )
                )

        job = GradingJob(
            job_id=job_id,
            course_id=course_id,
            quiz_id=quiz_id,
            job_name=job_name,
            total_questions=len(questions),
            total_submissions=len(submissions),
        )

        self.job_repo.create(job)
        if submissions:
            self.sub_repo.batch_create(submissions)

        return job

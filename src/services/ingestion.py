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

        if not submissions:
            raise ValueError(
                "No gradable submissions found. The quiz may contain no short-answer "
                "or essay questions, or no students have submitted."
            )

        self.job_repo.create(job)
        self.sub_repo.batch_create(submissions)

        return job

    def ingest_from_canvas_api(
        self,
        course_id: str,
        quiz_id: str,
        job_name: str,
        questions: list[dict],
        quiz_submissions: list[dict],
        answers_by_user: dict[str, list[dict]],
    ) -> GradingJob:
        """Create a grading job directly from Canvas REST API response data.

        Args:
            course_id: The Canvas course ID.
            quiz_id: The Canvas quiz ID.
            job_name: Human-readable name for the job.
            questions: List of question dicts from GET /quizzes/:id/questions.
                       Each answer uses Canvas field names: answer_text, answer_weight.
            quiz_submissions: List of quiz_submission dicts from GET /quizzes/:id/submissions.
                              Each entry has id (quiz_submission_id) and user_id.
            answers_by_user: Mapping of str(user_id) → list of answer dicts
                             from Assignments API submission_history.submission_data.
                             Each has question_id and answer.

        Returns:
            The created GradingJob.
        """
        GRADABLE_TYPES = {
            "short_answer_question",
            "fill_in_multiple_blanks_question",
            "essay_question",
        }

        job_id = uuid4()
        submissions: list[Submission] = []
        gradable_questions = [
            q for q in questions if q.get("question_type") in GRADABLE_TYPES
        ]

        for question in gradable_questions:
            question_id = question["id"]
            qtype = question.get("question_type", "")
            correct_answers = [
                a.get("answer_text", a.get("text", ""))
                for a in question.get("answers", [])
                if float(a.get("answer_weight", a.get("weight", 0))) == 100
            ]

            for qs in quiz_submissions:
                canvas_user_id = str(qs.get("user_id", ""))

                student_answer = ""
                for ans in answers_by_user.get(canvas_user_id, []):
                    if ans.get("question_id") == question_id:
                        student_answer = str(ans.get("answer") or "")
                        break

                submissions.append(
                    Submission(
                        job_id=job_id,
                        question_id=question_id,
                        question_name=question.get("question_name", ""),
                        question_type=qtype,
                        question_text=question.get("question_text", ""),
                        points_possible=float(question.get("points_possible", 0)),
                        student_answer=student_answer,
                        canvas_points=0.0,
                        correct_answers=correct_answers,
                        canvas_user_id=canvas_user_id,
                    )
                )

        job = GradingJob(
            job_id=job_id,
            course_id=course_id,
            quiz_id=quiz_id,
            job_name=job_name,
            total_questions=len(gradable_questions),
            total_submissions=len(submissions),
        )

        if not submissions:
            raise ValueError(
                "No gradable submissions found. The quiz may contain no short-answer "
                "or essay questions, or no students have submitted."
            )

        self.job_repo.create(job)
        self.sub_repo.batch_create(submissions)

        return job

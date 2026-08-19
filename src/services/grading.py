"""Service for AI grading of submissions via AWS Bedrock."""

import json

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID

from src.core.aws import get_bedrock_runtime_client
from src.core.config import get_settings
from src.core.observability import logger, metrics, MetricUnit
from src.models.grading_job import JobStatus
from src.models.submission import GradingStatus
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository


ANTHROPIC_VERSION = "bedrock-2023-05-31"
MAX_WORKERS = 10


class GradingService:
    def __init__(
        self,
        job_repo: GradingJobRepository | None = None,
        sub_repo: SubmissionRepository | None = None,
        bedrock_client=None,
        model_id: str | None = None,
    ):
        self.job_repo = job_repo or GradingJobRepository()
        self.sub_repo = sub_repo or SubmissionRepository()
        self._bedrock_client = bedrock_client
        self.model_id = model_id or get_settings().bedrock_model_id

    @property
    def bedrock_client(self):
        if self._bedrock_client is None:
            self._bedrock_client = get_bedrock_runtime_client()
        return self._bedrock_client

    def grade_job(self, job_id: UUID) -> None:
        logger.info("Starting grading job", job_id=str(job_id))
        self.job_repo.update_status(job_id, JobStatus.PROCESSING)

        submissions = self.sub_repo.list_by_job(job_id)
        if not submissions:
            logger.info("No submissions found for job", job_id=str(job_id))
            self.job_repo.update_status(
                job_id, JobStatus.COMPLETED, success_count=0, fail_count=0
            )
            return

        logger.info(
            "Grading submissions for job", job_id=str(job_id), count=len(submissions)
        )
        errors: list[str] = []
        success = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._grade_submission, sub): sub for sub in submissions
            }
            for future in as_completed(futures):
                current_job = self.job_repo.get(job_id)
                if current_job and current_job.status == JobStatus.CANCELLED:
                    logger.info("Job cancelled during grading", job_id=str(job_id))
                    for f in futures:
                        f.cancel()
                    return
                sub = futures[future]
                try:
                    future.result()
                    success += 1
                except Exception as e:
                    logger.error(
                        "Grading submission failed",
                        job_id=str(job_id),
                        submission_id=str(sub.submission_id),
                    )
                    errors.append(f"Submission {sub.submission_id}: {e}")
                    self.sub_repo.mark_failed(job_id, sub.submission_id, str(e))

        if not errors:
            logger.info("Grading completed successfully", job_id=str(job_id))
            self.job_repo.update_status(
                job_id, JobStatus.COMPLETED, success_count=success, fail_count=0
            )
            metrics.add_metric(
                name="GradingJobCompleted", unit=MetricUnit.Count, value=1
            )
        elif success == 0:
            logger.warning(
                "Grading failed entirely",
                job_id=str(job_id),
                error_count=len(errors),
            )
            self.job_repo.update_status(
                job_id,
                JobStatus.FAILED,
                error_message="; ".join(errors),
                success_count=0,
                fail_count=len(errors),
            )
            metrics.add_metric(name="GradingJobFailed", unit=MetricUnit.Count, value=1)
        else:
            logger.info(
                "Grading completed with errors",
                job_id=str(job_id),
                success_count=success,
                error_count=len(errors),
            )
            self.job_repo.update_status(
                job_id,
                JobStatus.COMPLETED_WITH_ERRORS,
                error_message="; ".join(errors),
                success_count=success,
                fail_count=len(errors),
            )
            metrics.add_metric(
                name="GradingJobCompletedWithErrors", unit=MetricUnit.Count, value=1
            )

    def retry_failed(self, job_id: UUID) -> None:
        """Re-grade only the submissions currently marked FAILED for this job."""
        failed_subs = self.sub_repo.list_failed_by_job(job_id)
        if not failed_subs:
            logger.info("No failed submissions to retry", job_id=str(job_id))
            return

        logger.info(
            "Retrying failed submissions", job_id=str(job_id), count=len(failed_subs)
        )
        self.job_repo.update_status(job_id, JobStatus.PROCESSING)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._grade_submission, sub): sub for sub in failed_subs
            }
            for future in as_completed(futures):
                sub = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(
                        "Retry failed for submission",
                        job_id=str(job_id),
                        submission_id=str(sub.submission_id),
                        error=str(e),
                    )
                    self.sub_repo.mark_failed(job_id, sub.submission_id, str(e))

        all_subs = self.sub_repo.list_by_job(job_id)
        total_failed = sum(
            1 for s in all_subs if s.grading_status == GradingStatus.FAILED
        )
        total_succeeded = len(all_subs) - total_failed
        remaining_errors = [
            f"Submission {s.submission_id}: {s.grading_error}"
            for s in all_subs
            if s.grading_status == GradingStatus.FAILED
        ]

        if total_failed == 0:
            status = JobStatus.COMPLETED
            error_message = ""
        elif total_succeeded == 0:
            status = JobStatus.FAILED
            error_message = "; ".join(remaining_errors)
        else:
            status = JobStatus.COMPLETED_WITH_ERRORS
            error_message = "; ".join(remaining_errors)

        self.job_repo.update_status(
            job_id,
            status,
            error_message=error_message,
            success_count=total_succeeded,
            fail_count=total_failed,
        )

    def _grade_submission(self, sub) -> None:
        prompt = self._build_prompt(sub)
        response = self._invoke_bedrock(prompt)
        grade, feedback = self._parse_response(response, sub.points_possible)
        now = datetime.now(timezone.utc)
        self.sub_repo.update_ai_grade(
            job_id=sub.job_id,
            submission_id=sub.submission_id,
            ai_grade=grade,
            ai_feedback=feedback,
            ai_graded_at=now,
        )

    def _build_prompt(self, sub) -> str:
        correct = (
            "\n".join(f"- {a}" for a in sub.correct_answers)
            if sub.correct_answers
            else "None provided"
        )
        return (
            "You are a teaching assistant grading student answers. "
            "Grade the following submission and respond with ONLY a JSON object "
            '(no markdown, no explanation) with keys "grade" (number) and "feedback" (string).\n\n'
            f"Question type: {sub.question_type}\n"
            f"Question: {sub.question_text}\n"
            f"Points possible: {sub.points_possible}\n"
            f"Correct/expected answers:\n{correct}\n\n"
            f"Student answer: {sub.student_answer}\n\n"
            "Respond with JSON only."
        )

    def _invoke_bedrock(self, prompt: str) -> dict:
        body = json.dumps(
            {
                "anthropic_version": ANTHROPIC_VERSION,
                "max_tokens": 512,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
                "output_config": {
                    "format": {
                        "type": "json_schema",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "grade": {
                                    "type": "number",
                                    "description": "points awarded to student based on their answer, limited to maximum points possible",
                                },
                                "feedback": {
                                    "type": "string",
                                    "description": "feedback for student explaining why their answer is correct or incorrect",
                                },
                            },
                            "required": ["grade", "feedback"],
                            "additionalProperties": False,
                        },
                    }
                },
            }
        )
        response = self.bedrock_client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        return json.loads(response["body"].read())

    def _parse_response(
        self, response: dict, points_possible: float
    ) -> tuple[float, str]:
        text = response["content"][0]["text"]

        # Handle ```json wrapping
        if "```" in text:
            start = text.find("```")
            end = text.rfind("```")
            inner = text[start : end + 3]
            # Remove the opening ``` line
            lines = inner.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            parsed = json.loads(text)
        except Exception:
            logger.exception(
                "Failed to parse Bedrock response text",
                raw_text=text,
            )
            raise
        grade = float(parsed["grade"])
        feedback = str(parsed["feedback"])

        # Clamp grade to valid range
        grade = max(0.0, min(grade, points_possible))

        return grade, feedback

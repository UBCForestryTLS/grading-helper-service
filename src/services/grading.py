"""Service for AI grading of submissions via AWS Bedrock."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID

from src.core.aws import get_bedrock_runtime_client
from src.core.config import get_settings
from src.models.grading_job import JobStatus
from src.repositories.grading_job import GradingJobRepository
from src.repositories.submission import SubmissionRepository

logger = logging.getLogger(__name__)

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
        self.job_repo.update_status(job_id, JobStatus.PROCESSING)

        submissions = self.sub_repo.list_by_job(job_id)
        if not submissions:
            self.job_repo.update_status(job_id, JobStatus.COMPLETED)
            return

        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._grade_submission, sub): sub for sub in submissions
            }
            for future in as_completed(futures):
                sub = futures[future]
                try:
                    future.result()
                except Exception as e:
                    errors.append(f"Submission {sub.submission_id}: {e}")

        if errors:
            self.job_repo.update_status(
                job_id,
                JobStatus.FAILED,
                error_message="; ".join(errors),
            )
        else:
            self.job_repo.update_status(job_id, JobStatus.COMPLETED)

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
                "messages": [{"role": "user", "content": prompt}],
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

        parsed = json.loads(text)
        grade = float(parsed["grade"])
        feedback = str(parsed["feedback"])

        # Clamp grade to valid range
        grade = max(0.0, min(grade, points_possible))

        return grade, feedback

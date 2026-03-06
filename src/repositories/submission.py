"""DynamoDB repository for Submission entities."""

from datetime import datetime
from uuid import UUID

from boto3.dynamodb.conditions import Key

from src.core.aws import get_dynamodb_table
from src.models.submission import Submission


class SubmissionRepository:
    """CRUD operations for submissions in DynamoDB."""

    def __init__(self, table=None):
        self._table = table

    @property
    def table(self):
        if self._table is None:
            self._table = get_dynamodb_table()
        return self._table

    def _to_item(self, sub: Submission) -> dict:
        item = {
            "pk": f"JOB#{sub.job_id}",
            "sk": f"SUB#{sub.submission_id}",
            "submission_id": str(sub.submission_id),
            "job_id": str(sub.job_id),
            "question_id": sub.question_id,
            "question_name": sub.question_name,
            "question_type": sub.question_type,
            "question_text": sub.question_text,
            "points_possible": str(sub.points_possible),
            "student_answer": sub.student_answer,
            "canvas_points": str(sub.canvas_points),
            "correct_answers": sub.correct_answers,
        }
        if sub.ai_grade is not None:
            item["ai_grade"] = str(sub.ai_grade)
        if sub.ai_feedback is not None:
            item["ai_feedback"] = sub.ai_feedback
        if sub.ai_graded_at is not None:
            item["ai_graded_at"] = sub.ai_graded_at.isoformat()
        return item

    def _from_item(self, item: dict) -> Submission:
        return Submission(
            submission_id=UUID(item["submission_id"]),
            job_id=UUID(item["job_id"]),
            question_id=int(item["question_id"]),
            question_name=item["question_name"],
            question_type=item["question_type"],
            question_text=item["question_text"],
            points_possible=float(item["points_possible"]),
            student_answer=item["student_answer"],
            canvas_points=float(item["canvas_points"]),
            correct_answers=item["correct_answers"],
            ai_grade=float(item["ai_grade"]) if item.get("ai_grade") else None,
            ai_feedback=item.get("ai_feedback"),
            ai_graded_at=(
                datetime.fromisoformat(item["ai_graded_at"])
                if item.get("ai_graded_at")
                else None
            ),
        )

    def batch_create(self, submissions: list[Submission]) -> None:
        with self.table.batch_writer() as batch:
            for sub in submissions:
                batch.put_item(Item=self._to_item(sub))

    def list_by_job(self, job_id: UUID) -> list[Submission]:
        response = self.table.query(
            KeyConditionExpression=(
                Key("pk").eq(f"JOB#{job_id}") & Key("sk").begins_with("SUB#")
            ),
        )
        return [self._from_item(item) for item in response["Items"]]

    def get(self, job_id: UUID, submission_id: UUID) -> Submission | None:
        response = self.table.get_item(
            Key={"pk": f"JOB#{job_id}", "sk": f"SUB#{submission_id}"}
        )
        item = response.get("Item")
        if item is None:
            return None
        return self._from_item(item)

    def update_ai_grade(
        self,
        job_id: UUID,
        submission_id: UUID,
        ai_grade: float,
        ai_feedback: str,
        ai_graded_at: datetime,
    ) -> None:
        self.table.update_item(
            Key={"pk": f"JOB#{job_id}", "sk": f"SUB#{submission_id}"},
            UpdateExpression="SET ai_grade = :grade, ai_feedback = :feedback, ai_graded_at = :graded_at",
            ExpressionAttributeValues={
                ":grade": str(ai_grade),
                ":feedback": ai_feedback,
                ":graded_at": ai_graded_at.isoformat(),
            },
        )

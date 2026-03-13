"""DynamoDB repository for GradingJob entities."""

from datetime import datetime, timezone
from uuid import UUID

from boto3.dynamodb.conditions import Key

from src.core.aws import get_dynamodb_table
from src.models.grading_job import GradingJob, JobStatus


class GradingJobRepository:
    """CRUD operations for grading jobs in DynamoDB."""

    def __init__(self, table=None):
        self._table = table

    @property
    def table(self):
        if self._table is None:
            self._table = get_dynamodb_table()
        return self._table

    def _to_item(self, job: GradingJob) -> dict:
        job_id = str(job.job_id)
        created_at = job.created_at.isoformat()
        updated_at = job.updated_at.isoformat()
        item = {
            "pk": f"JOB#{job_id}",
            "sk": "METADATA",
            "GSI1PK": f"COURSE#{job.course_id}",
            "GSI1SK": f"JOB#{created_at}",
            "GSI2PK": f"STATUS#{job.status}",
            "GSI2SK": f"JOB#{job_id}",
            "job_id": job_id,
            "course_id": job.course_id,
            "quiz_id": job.quiz_id,
            "job_name": job.job_name,
            "status": str(job.status),
            "total_questions": job.total_questions,
            "total_submissions": job.total_submissions,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        if job.error_message is not None:
            item["error_message"] = job.error_message
        return item

    def _from_item(self, item: dict) -> GradingJob:
        return GradingJob(
            job_id=UUID(item["job_id"]),
            course_id=item["course_id"],
            quiz_id=item["quiz_id"],
            job_name=item["job_name"],
            status=JobStatus(item["status"]),
            total_questions=int(item["total_questions"]),
            total_submissions=int(item["total_submissions"]),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            error_message=item.get("error_message"),
        )

    def create(self, job: GradingJob) -> GradingJob:
        self.table.put_item(Item=self._to_item(job))
        return job

    def get(self, job_id: UUID) -> GradingJob | None:
        response = self.table.get_item(Key={"pk": f"JOB#{job_id}", "sk": "METADATA"})
        item = response.get("Item")
        if item is None:
            return None
        return self._from_item(item)

    def list_by_course(self, course_id: str) -> list[GradingJob]:
        response = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(f"COURSE#{course_id}"),
        )
        return [self._from_item(item) for item in response["Items"]]

    def list_by_status(self, status: JobStatus) -> list[GradingJob]:
        response = self.table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(f"STATUS#{status}"),
        )
        return [self._from_item(item) for item in response["Items"]]

    def update_status(
        self, job_id: UUID, status: JobStatus, error_message: str | None = None
    ) -> GradingJob | None:
        now = datetime.now(timezone.utc).isoformat()
        update_expr = (
            "SET #status = :status, GSI2PK = :gsi2pk, updated_at = :updated_at"
        )
        expr_values: dict = {
            ":status": str(status),
            ":gsi2pk": f"STATUS#{status}",
            ":updated_at": now,
        }
        expr_names = {"#status": "status"}

        if error_message is not None:
            update_expr += ", error_message = :error_message"
            expr_values[":error_message"] = error_message

        self.table.update_item(
            Key={"pk": f"JOB#{job_id}", "sk": "METADATA"},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )
        return self.get(job_id)

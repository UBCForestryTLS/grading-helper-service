"""Canvas REST API client for quiz data retrieval."""

import httpx


class CanvasAPIClient:
    """Synchronous httpx client for the Canvas REST API."""

    def __init__(self, canvas_url: str, access_token: str):
        self.canvas_url = canvas_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def _get_all_pages(self, url: str) -> list[dict]:
        """Fetch all pages from a Canvas paginated list endpoint via Link header."""
        results: list[dict] = []
        next_url: str | None = url
        while next_url:
            response = self._client.get(next_url)
            response.raise_for_status()
            data = response.json()
            results.extend(data)

            # Parse Link header for next page
            link_header = response.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                part = part.strip()
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break
        return results

    def list_quizzes(self, course_id: str) -> list[dict]:
        """List all quizzes for a course."""
        url = f"{self.canvas_url}/api/v1/courses/{course_id}/quizzes"
        return self._get_all_pages(url)

    def get_quiz_questions(self, course_id: str, quiz_id: str) -> list[dict]:
        """Get all questions for a quiz."""
        url = (
            f"{self.canvas_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}/questions"
        )
        return self._get_all_pages(url)

    def get_quiz_submissions(self, course_id: str, quiz_id: str) -> list[dict]:
        """Get all quiz_submission objects for a quiz.

        Canvas returns {"quiz_submissions": [...]} — we extract the list.
        """
        url = (
            f"{self.canvas_url}/api/v1/courses/{course_id}"
            f"/quizzes/{quiz_id}/submissions"
        )
        response = self._client.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("quiz_submissions", [])

    def get_assignment_submissions(
        self, course_id: str, assignment_id: str
    ) -> list[dict]:
        """Get assignment submissions with submission_history containing submission_data.

        This is the correct way to get student quiz answers per the Canvas API.
        The quiz submissions endpoint does NOT populate submission_data.
        The assignments submissions endpoint with include[]=submission_history does.

        Each submission's submission_history[].submission_data[] contains:
        - question_id: the quiz question ID
        - text: the student's answer text
        - correct: grading status
        - points: points awarded
        """
        url = (
            f"{self.canvas_url}/api/v1/courses/{course_id}"
            f"/assignments/{assignment_id}/submissions"
            f"?include[]=submission_history&per_page=100"
        )
        return self._get_all_pages(url)

    def update_quiz_submission_scores(
        self,
        course_id: str,
        quiz_id: str,
        quiz_submission_id: int,
        attempt: int,
        questions: dict[int, dict],
    ) -> dict:
        """Update per-question scores on an existing quiz submission.

        Canvas recomputes the total automatically, preserving MC question grades.
        questions: {question_id: {"score": float, "comment": str}}
        """
        url = (
            f"{self.canvas_url}/api/v1/courses/{course_id}"
            f"/quizzes/{quiz_id}/submissions/{quiz_submission_id}"
        )
        payload = {
            "quiz_submissions": [
                {
                    "attempt": attempt,
                    "questions": {str(qid): v for qid, v in questions.items()},
                }
            ]
        }
        resp = self._client.put(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

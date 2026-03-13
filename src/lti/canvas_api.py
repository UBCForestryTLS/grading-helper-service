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

        Canvas returns {"quiz_submissions": [...], "submissions": [...]} — we
        extract just the quiz_submissions list (which includes user_id, id, etc.).
        """
        url = f"{self.canvas_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}/submissions"
        response = self._client.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("quiz_submissions", [])

    def get_submission_answers(self, quiz_submission_id: str) -> list[dict]:
        """Get per-question answers for a quiz submission.

        Calls GET /api/v1/quiz_submissions/:id/questions which returns a list
        of question objects with the student's answer filled in.
        """
        url = (
            f"{self.canvas_url}/api/v1/quiz_submissions/{quiz_submission_id}/questions"
        )
        return self._get_all_pages(url)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

"""Tests for the Canvas REST API client."""

from unittest.mock import MagicMock, patch


from src.lti.canvas_api import CanvasAPIClient


def make_mock_response(json_data, link_header=""):
    """Helper to create a mock httpx response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.headers = {"Link": link_header}
    resp.raise_for_status = MagicMock()
    return resp


class TestCanvasAPIClientInit:
    def test_strips_trailing_slash(self):
        with patch("src.lti.canvas_api.httpx.Client"):
            client = CanvasAPIClient("https://canvas.example.com/", "token")
            assert client.canvas_url == "https://canvas.example.com"

    def test_sets_auth_header(self):
        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            CanvasAPIClient("https://canvas.example.com", "my-token")
            mock_client_cls.assert_called_once_with(
                headers={"Authorization": "Bearer my-token"}
            )


class TestListQuizzes:
    def test_list_quizzes_single_page(self):
        quizzes = [{"id": 1, "title": "Quiz 1"}, {"id": 2, "title": "Quiz 2"}]
        mock_resp = make_mock_response(quizzes)

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_client_cls.return_value = mock_http
            mock_http.get.return_value = mock_resp

            client = CanvasAPIClient("https://canvas.example.com", "token")
            result = client.list_quizzes("course-123")

        assert result == quizzes
        mock_http.get.assert_called_once_with(
            "https://canvas.example.com/api/v1/courses/course-123/quizzes"
        )

    def test_list_quizzes_pagination(self):
        page1 = [{"id": 1, "title": "Quiz 1"}]
        page2 = [{"id": 2, "title": "Quiz 2"}]

        resp1 = make_mock_response(
            page1,
            link_header='<https://canvas.example.com/api/v1/courses/1/quizzes?page=2>; rel="next"',
        )
        resp2 = make_mock_response(page2)

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_client_cls.return_value = mock_http
            mock_http.get.side_effect = [resp1, resp2]

            client = CanvasAPIClient("https://canvas.example.com", "token")
            result = client.list_quizzes("1")

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2


class TestGetQuizQuestions:
    def test_get_questions(self):
        questions = [
            {
                "id": 101,
                "question_name": "Q1",
                "question_type": "short_answer_question",
                "question_text": "What is X?",
                "points_possible": 5.0,
                "answers": [],
            }
        ]
        mock_resp = make_mock_response(questions)

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_client_cls.return_value = mock_http
            mock_http.get.return_value = mock_resp

            client = CanvasAPIClient("https://canvas.example.com", "token")
            result = client.get_quiz_questions("course-1", "quiz-1")

        assert result == questions
        mock_http.get.assert_called_once_with(
            "https://canvas.example.com/api/v1/courses/course-1/quizzes/quiz-1/questions"
        )


class TestGetQuizSubmissions:
    def test_extracts_quiz_submissions_from_object(self):
        """Canvas returns an object with quiz_submissions key, not a bare list."""
        quiz_submissions = [
            {"id": 201, "user_id": 501, "quiz_id": 50},
            {"id": 202, "user_id": 502, "quiz_id": 50},
        ]
        mock_resp = make_mock_response({"quiz_submissions": quiz_submissions})

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_client_cls.return_value = mock_http
            mock_http.get.return_value = mock_resp

            client = CanvasAPIClient("https://canvas.example.com", "token")
            result = client.get_quiz_submissions("course-1", "quiz-1")

        assert result == quiz_submissions

    def test_returns_empty_list_when_no_submissions(self):
        mock_resp = make_mock_response({"quiz_submissions": []})

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_client_cls.return_value = mock_http
            mock_http.get.return_value = mock_resp

            client = CanvasAPIClient("https://canvas.example.com", "token")
            result = client.get_quiz_submissions("course-1", "quiz-1")

        assert result == []


class TestGetAssignmentSubmissions:
    def test_returns_submissions_with_history(self):
        submissions = [
            {
                "id": 301,
                "user_id": 501,
                "submission_history": [
                    {
                        "submission_data": [
                            {"question_id": 101, "text": "My answer"},
                        ]
                    }
                ],
            }
        ]
        mock_resp = make_mock_response(submissions)

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_client_cls.return_value = mock_http
            mock_http.get.return_value = mock_resp

            client = CanvasAPIClient("https://canvas.example.com", "token")
            result = client.get_assignment_submissions("course-1", "100")

        assert len(result) == 1
        assert (
            result[0]["submission_history"][0]["submission_data"][0]["text"]
            == "My answer"
        )
        mock_http.get.assert_called_once_with(
            "https://canvas.example.com/api/v1/courses/course-1"
            "/assignments/100/submissions"
            "?include[]=submission_history&per_page=100"
        )


class TestContextManager:
    def test_context_manager_closes_client(self):
        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_client_cls.return_value = mock_http

            with CanvasAPIClient("https://canvas.example.com", "token"):
                pass

            mock_http.close.assert_called_once()

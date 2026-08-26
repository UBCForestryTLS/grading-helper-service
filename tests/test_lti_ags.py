"""Tests for the LTI AGS (Assignment and Grade Services) grade passback module."""

from unittest.mock import MagicMock, patch


class TestGetAgsToken:
    def test_get_ags_token_returns_access_token(self, lti_env_vars):
        from src.lti.ags import get_ags_token

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "ags-bearer-token"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.post", return_value=mock_response) as mock_post:
            token = get_ags_token(
                client_id="10000000000001",
                auth_token_url="https://canvas.test.instructure.com/login/oauth2/token",
            )

        assert token == "ags-bearer-token"
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0].endswith("/login/oauth2/token")
        data = call_kwargs[1]["data"]
        assert data["grant_type"] == "client_credentials"
        assert "client_assertion" in data
        assert "urn:ietf:params:oauth:client-assertion-type:jwt-bearer" in data.get(
            "client_assertion_type", ""
        )

    def test_get_ags_token_jwt_assertion_is_signed(self, lti_env_vars):
        """The JWT assertion should be a properly formatted JWT."""
        from src.lti.ags import get_ags_token

        captured_assertion = None

        def capture_post(url, data=None, **kwargs):
            nonlocal captured_assertion
            captured_assertion = data.get("client_assertion")
            resp = MagicMock()
            resp.json.return_value = {"access_token": "tok"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("src.lti.ags.httpx.post", side_effect=capture_post):
            get_ags_token(
                client_id="10000000000001",
                auth_token_url="https://canvas.test.instructure.com/login/oauth2/token",
            )

        assert captured_assertion is not None
        # Verify it's a valid JWT with 3 parts
        assert len(captured_assertion.split(".")) == 3


class TestSubmitScore:
    def test_submit_score_sends_correct_payload(self):
        from src.lti.ags import submit_score

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "score-1"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.post", return_value=mock_response) as mock_post:
            result = submit_score(
                lineitem_url="https://canvas.example.com/api/lti/lineitem/1",
                token="bearer-token",
                user_id="user-abc",
                score=4.5,
                max_score=5.0,
                comment="Good answer",
            )

        assert result == {"id": "score-1"}
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0].endswith("/scores")
        payload = call_kwargs[1]["json"]
        assert payload["userId"] == "user-abc"
        assert payload["scoreGiven"] == 4.5
        assert payload["scoreMaximum"] == 5.0
        assert payload["activityProgress"] == "Completed"
        assert payload["gradingProgress"] == "FullyGraded"
        assert payload["comment"] == "Good answer"
        assert "timestamp" in payload
        headers = call_kwargs[1]["headers"]
        assert "application/vnd.ims.lis.v1.score+json" in headers.get(
            "Content-Type", ""
        )

    def test_submit_score_without_comment(self):
        from src.lti.ags import submit_score

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.post", return_value=mock_response) as mock_post:
            submit_score(
                lineitem_url="https://canvas.example.com/lineitem/1",
                token="tok",
                user_id="u1",
                score=3.0,
                max_score=5.0,
            )

        payload = mock_post.call_args[1]["json"]
        assert "comment" not in payload


class TestFindOrCreateLineitemUrl:
    def test_find_by_assignment_id_url_suffix(self):
        from src.lti.ags import find_or_create_lineitem_url

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "id": "https://canvas.example.com/api/lti/courses/1/line_items/99",
                "label": "Other",
            },
            {
                "id": "https://canvas.example.com/api/lti/courses/1/line_items/42",
                "label": "Quiz 1",
            },
        ]
        mock_resp.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.get", return_value=mock_resp):
            url = find_or_create_lineitem_url(
                lineitems_url="https://canvas.example.com/api/lti/courses/1/line_items",
                token="tok",
                assignment_id="42",
            )
        assert url == "https://canvas.example.com/api/lti/courses/1/line_items/42"

    def test_find_by_resource_id(self):
        from src.lti.ags import find_or_create_lineitem_url

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "id": "https://canvas.example.com/line_items/abc",
                "resourceId": "42",
                "label": "Quiz 1",
            },
        ]
        mock_resp.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.get", return_value=mock_resp):
            url = find_or_create_lineitem_url(
                lineitems_url="https://canvas.example.com/line_items",
                token="tok",
                assignment_id="42",
            )
        assert url == "https://canvas.example.com/line_items/abc"

    def test_find_by_label_fallback(self):
        from src.lti.ags import find_or_create_lineitem_url

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "https://canvas.example.com/line_items/1", "label": "Other Quiz"},
            {"id": "https://canvas.example.com/line_items/2", "label": "My Quiz"},
        ]
        mock_resp.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.get", return_value=mock_resp):
            url = find_or_create_lineitem_url(
                lineitems_url="https://canvas.example.com/line_items",
                token="tok",
                job_name="My Quiz",
            )
        assert url == "https://canvas.example.com/line_items/2"

    def test_creates_lineitem_when_no_match(self):
        from src.lti.ags import find_or_create_lineitem_url

        mock_get_resp = MagicMock()
        mock_get_resp.json.return_value = [
            {"id": "https://canvas.example.com/line_items/1", "label": "Other"},
        ]
        mock_get_resp.raise_for_status = MagicMock()

        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {
            "id": "https://canvas.example.com/line_items/99",
            "label": "Nonexistent",
            "scoreMaximum": 10.0,
        }
        mock_post_resp.raise_for_status = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.text = '{"id":"https://canvas.example.com/line_items/99"}'

        with (
            patch("src.lti.ags.httpx.get", return_value=mock_get_resp),
            patch("src.lti.ags.httpx.post", return_value=mock_post_resp) as mock_post,
        ):
            url = find_or_create_lineitem_url(
                lineitems_url="https://canvas.example.com/line_items",
                token="tok",
                assignment_id="999",
                job_name="Nonexistent",
                max_score=10.0,
            )

        assert url == "https://canvas.example.com/line_items/99"
        post_kwargs = mock_post.call_args
        payload = post_kwargs[1]["json"]
        assert payload["label"] == "Nonexistent"
        assert payload["scoreMaximum"] == 10.0
        assert payload["resourceId"] == "999"


class TestPassbackJobGrades:
    def test_passback_no_launch(self, dynamodb_table):
        from src.lti.ags import passback_job_grades

        result = passback_job_grades(
            job_id="some-job-id",
            launch_id="nonexistent-launch",
            table=dynamodb_table,
        )
        assert result["submitted"] == 0
        assert len(result["errors"]) == 1
        assert "not found" in result["errors"][0]

    def test_passback_no_lineitem_url(self, dynamodb_table, lti_env_vars):
        from src.lti.ags import passback_job_grades
        from src.lti.launch_store import LaunchStore

        # Create a launch without any AGS URLs
        store = LaunchStore(table=dynamodb_table)
        launch_id = store.create(
            {"sub": "user-1", "iss": "https://canvas.test.instructure.com"}
        )

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "tok"}
        mock_token_resp.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.post", return_value=mock_token_resp):
            result = passback_job_grades(
                job_id="00000000-0000-0000-0000-000000000001",
                launch_id=launch_id,
                table=dynamodb_table,
            )
        assert result["submitted"] == 0
        assert "No AGS lineitem or lineitems URL" in result["errors"][0]

    def test_passback_submits_graded_submissions(self, dynamodb_table, lti_env_vars):
        from uuid import uuid4
        from src.lti.ags import passback_job_grades
        from src.lti.launch_store import LaunchStore
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        # Create launch with AGS lineitem URL
        store = LaunchStore(table=dynamodb_table)
        launch_id = store.create(
            {
                "sub": "user-1",
                "iss": "https://canvas.test.instructure.com",
                "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                    "lineitem": "https://canvas.test.instructure.com/api/lti/lineitem/1",
                    "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/score"],
                },
            }
        )

        # Create a job and graded submission
        job_id = uuid4()
        job_repo = GradingJobRepository(table=dynamodb_table)
        job = GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="Test")
        job_repo.create(job)

        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub = Submission(
            job_id=job_id,
            question_id=1,
            question_name="Q1",
            question_type="short_answer_question",
            question_text="What?",
            points_possible=5.0,
            student_answer="Answer",
            canvas_points=0.0,
            correct_answers=["Correct answer"],
            canvas_user_id="canvas-student-42",
            ai_grade=4.0,
            ai_feedback="Good",
        )
        sub_repo.batch_create([sub])

        mock_ags_token_resp = MagicMock()
        mock_ags_token_resp.json.return_value = {"access_token": "ags-tok"}
        mock_ags_token_resp.raise_for_status = MagicMock()

        mock_score_resp = MagicMock()
        mock_score_resp.json.return_value = {}
        mock_score_resp.raise_for_status = MagicMock()

        with patch(
            "src.lti.ags.httpx.post", side_effect=[mock_ags_token_resp, mock_score_resp]
        ) as mock_post:
            result = passback_job_grades(
                job_id=str(job_id),
                launch_id=launch_id,
                table=dynamodb_table,
            )

            # Verify canvas_user_id was passed to submit_score, not submission_id
            score_call = mock_post.call_args_list[1]
            assert score_call[1]["json"]["userId"] == "canvas-student-42"

        assert result["submitted"] == 1
        assert result["errors"] == []

    def test_passback_skips_ungraded_submissions(self, dynamodb_table, lti_env_vars):
        from uuid import uuid4
        from src.lti.ags import passback_job_grades
        from src.lti.launch_store import LaunchStore
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        store = LaunchStore(table=dynamodb_table)
        launch_id = store.create(
            {
                "sub": "user-1",
                "iss": "https://canvas.test.instructure.com",
                "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                    "lineitem": "https://canvas.test.instructure.com/lineitem/1",
                    "scope": [],
                },
            }
        )

        job_id = uuid4()
        job_repo = GradingJobRepository(table=dynamodb_table)
        job_repo.create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="Test")
        )

        sub_repo = SubmissionRepository(table=dynamodb_table)
        # Submission without ai_grade
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=1,
                    question_name="Q1",
                    question_type="short_answer_question",
                    question_text="?",
                    points_possible=5.0,
                    student_answer="Answer",
                    canvas_points=0.0,
                    correct_answers=[],
                    ai_grade=None,  # not graded
                )
            ]
        )

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "tok"}
        mock_token_resp.raise_for_status = MagicMock()

        with patch("src.lti.ags.httpx.post", return_value=mock_token_resp):
            result = passback_job_grades(
                job_id=str(job_id),
                launch_id=launch_id,
                table=dynamodb_table,
            )

        assert result["submitted"] == 0
        assert result["errors"] == []

    def test_passback_uses_lineitems_url_when_no_lineitem(
        self, dynamodb_table, lti_env_vars
    ):
        """When launch has lineitems (plural) but no lineitem (singular),
        passback should look up the correct lineitem via the collection."""
        from uuid import uuid4
        from src.lti.ags import passback_job_grades
        from src.lti.launch_store import LaunchStore
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        store = LaunchStore(table=dynamodb_table)
        launch_id = store.create(
            {
                "sub": "user-1",
                "iss": "https://canvas.test.instructure.com",
                "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                    "lineitems": "https://canvas.test.instructure.com/api/lti/courses/1/line_items",
                    "scope": [
                        "https://purl.imsglobal.org/spec/lti-ags/scope/score",
                        "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
                    ],
                },
            }
        )

        job_id = uuid4()
        job_repo = GradingJobRepository(table=dynamodb_table)
        job_repo.create(
            GradingJob(
                job_id=job_id,
                course_id="C1",
                quiz_id="Q1",
                assignment_id="42",
                job_name="Test Quiz",
            )
        )

        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=1,
                    question_name="Q1",
                    question_type="short_answer_question",
                    question_text="What?",
                    points_possible=5.0,
                    student_answer="Answer",
                    canvas_points=0.0,
                    correct_answers=["Correct"],
                    canvas_user_id="student-1",
                    ai_grade=4.0,
                    ai_feedback="Good",
                )
            ]
        )

        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {"access_token": "ags-tok"}
        mock_token_resp.raise_for_status = MagicMock()

        mock_lineitems_resp = MagicMock()
        mock_lineitems_resp.json.return_value = [
            {
                "id": "https://canvas.test.instructure.com/api/lti/courses/1/line_items/42",
                "label": "Test Quiz",
                "scoreMaximum": 5.0,
            },
        ]
        mock_lineitems_resp.raise_for_status = MagicMock()

        mock_score_resp = MagicMock()
        mock_score_resp.json.return_value = {}
        mock_score_resp.raise_for_status = MagicMock()

        with (
            patch(
                "src.lti.ags.httpx.post",
                side_effect=[mock_token_resp, mock_score_resp],
            ) as mock_post,
            patch("src.lti.ags.httpx.get", return_value=mock_lineitems_resp),
        ):
            result = passback_job_grades(
                job_id=str(job_id),
                launch_id=launch_id,
                table=dynamodb_table,
            )

            score_call = mock_post.call_args_list[1]
            assert score_call[0][0].endswith("/line_items/42/scores")
            assert score_call[1]["json"]["userId"] == "student-1"

        assert result["submitted"] == 1
        assert result["errors"] == []

    def test_passback_ags_includes_ai_notice_without_override(
        self, dynamodb_table, lti_env_vars
    ):
        """AGS path: no instructor override, comment should carry the AI-only notice."""
        from uuid import uuid4
        from src.lti.ags import passback_job_grades
        from src.lti.launch_store import LaunchStore
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        store = LaunchStore(table=dynamodb_table)
        launch_id = store.create(
            {
                "sub": "user-1",
                "iss": "https://canvas.test.instructure.com",
                "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                    "lineitem": "https://canvas.test.instructure.com/api/lti/lineitem/1",
                    "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/score"],
                },
            }
        )

        job_id = uuid4()
        GradingJobRepository(table=dynamodb_table).create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="Test")
        )

        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=1,
                    question_name="Q1",
                    question_type="short_answer_question",
                    question_text="What?",
                    points_possible=5.0,
                    student_answer="Answer",
                    canvas_points=0.0,
                    correct_answers=["Correct answer"],
                    canvas_user_id="canvas-student-42",
                    ai_grade=4.0,
                    ai_feedback="Good",
                )
            ]
        )

        mock_ags_token_resp = MagicMock()
        mock_ags_token_resp.json.return_value = {"access_token": "ags-tok"}
        mock_ags_token_resp.raise_for_status = MagicMock()

        mock_score_resp = MagicMock()
        mock_score_resp.json.return_value = {}
        mock_score_resp.raise_for_status = MagicMock()

        with patch(
            "src.lti.ags.httpx.post",
            side_effect=[mock_ags_token_resp, mock_score_resp],
        ) as mock_post:
            result = passback_job_grades(
                job_id=str(job_id),
                launch_id=launch_id,
                table=dynamodb_table,
            )

            score_call = mock_post.call_args_list[1]
            comment = score_call[1]["json"]["comment"]

        assert result["submitted"] == 1
        assert (
            comment
            == "\x1b[3m(This question's grade and feedback were generated by AI)\x1b[0m\n\nGood"
        )

    def test_passback_ags_includes_instructor_notice_with_override(
        self, dynamodb_table, lti_env_vars
    ):
        """AGS path: instructor overrode grade and feedback, comment should carry
        the instructor-modified notice and the instructor's feedback text, not the
        AI's original feedback."""
        from uuid import uuid4
        from src.lti.ags import passback_job_grades
        from src.lti.launch_store import LaunchStore
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        store = LaunchStore(table=dynamodb_table)
        launch_id = store.create(
            {
                "sub": "user-1",
                "iss": "https://canvas.test.instructure.com",
                "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                    "lineitem": "https://canvas.test.instructure.com/api/lti/lineitem/1",
                    "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/score"],
                },
            }
        )

        job_id = uuid4()
        GradingJobRepository(table=dynamodb_table).create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="Test")
        )

        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=1,
                    question_name="Q1",
                    question_type="short_answer_question",
                    question_text="What?",
                    points_possible=5.0,
                    student_answer="Answer",
                    canvas_points=0.0,
                    correct_answers=["Correct answer"],
                    canvas_user_id="canvas-student-42",
                    ai_grade=4.0,
                    ai_feedback="Good",
                    instructor_grade=5.0,
                    instructor_feedback="Excellent, full marks.",
                    overridden_by="instructor-9",
                )
            ]
        )

        mock_ags_token_resp = MagicMock()
        mock_ags_token_resp.json.return_value = {"access_token": "ags-tok"}
        mock_ags_token_resp.raise_for_status = MagicMock()

        mock_score_resp = MagicMock()
        mock_score_resp.json.return_value = {}
        mock_score_resp.raise_for_status = MagicMock()

        with patch(
            "src.lti.ags.httpx.post",
            side_effect=[mock_ags_token_resp, mock_score_resp],
        ) as mock_post:
            result = passback_job_grades(
                job_id=str(job_id),
                launch_id=launch_id,
                table=dynamodb_table,
            )

            score_call = mock_post.call_args_list[1]
            payload = score_call[1]["json"]

        assert result["submitted"] == 1
        assert payload["scoreGiven"] == 5.0
        assert (
            payload["comment"]
            == "\x1b[3m(This question's grade and feedback were modified by the instructor. "
            "AI assistance may have been used to write the provided feedback.)\x1b[0m\n\nExcellent, full marks."
        )

    def test_passback_ags_includes_notice_for_feedback_only_override(
        self, dynamodb_table, lti_env_vars
    ):
        """AGS path: only feedback was overridden, grade still comes from AI.
        Covers the fourth notice case not in the original ticket."""
        from uuid import uuid4
        from src.lti.ags import passback_job_grades
        from src.lti.launch_store import LaunchStore
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        store = LaunchStore(table=dynamodb_table)
        launch_id = store.create(
            {
                "sub": "user-1",
                "iss": "https://canvas.test.instructure.com",
                "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                    "lineitem": "https://canvas.test.instructure.com/api/lti/lineitem/1",
                    "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/score"],
                },
            }
        )

        job_id = uuid4()
        GradingJobRepository(table=dynamodb_table).create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="Test")
        )

        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=1,
                    question_name="Q1",
                    question_type="short_answer_question",
                    question_text="What?",
                    points_possible=5.0,
                    student_answer="Answer",
                    canvas_points=0.0,
                    correct_answers=["Correct answer"],
                    canvas_user_id="canvas-student-42",
                    ai_grade=4.0,
                    ai_feedback="Good",
                    instructor_feedback="Also cite your sources next time.",
                    overridden_by="instructor-9",
                )
            ]
        )

        mock_ags_token_resp = MagicMock()
        mock_ags_token_resp.json.return_value = {"access_token": "ags-tok"}
        mock_ags_token_resp.raise_for_status = MagicMock()

        mock_score_resp = MagicMock()
        mock_score_resp.json.return_value = {}
        mock_score_resp.raise_for_status = MagicMock()

        with patch(
            "src.lti.ags.httpx.post",
            side_effect=[mock_ags_token_resp, mock_score_resp],
        ) as mock_post:
            result = passback_job_grades(
                job_id=str(job_id),
                launch_id=launch_id,
                table=dynamodb_table,
            )

            score_call = mock_post.call_args_list[1]
            payload = score_call[1]["json"]

        assert result["submitted"] == 1
        assert payload["scoreGiven"] == 4.0  # ai_grade, unchanged
        assert (
            payload["comment"]
            == "\x1b[3m(This question's grade was generated by AI. The feedback was "
            "modified by the instructor. AI assistance may have been used to "
            "write the provided feedback.)\x1b[0m"
            "\n\nAlso cite your sources next time."
        )


class TestPassbackQuizGradesViaRest:
    def _make_job_and_subs(self, dynamodb_table, quiz_submission_id=201, attempt=1):
        from uuid import uuid4

        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        job_id = uuid4()
        GradingJobRepository(table=dynamodb_table).create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="Test")
        )
        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=101,
                    question_name="Q1",
                    question_type="essay_question",
                    question_text="Explain X",
                    points_possible=1.0,
                    student_answer="Answer A",
                    canvas_points=0.0,
                    correct_answers=[],
                    canvas_user_id="student-1",
                    quiz_submission_id=quiz_submission_id,
                    attempt=attempt,
                    ai_grade=0.5,
                    ai_feedback="Partial credit",
                ),
                Submission(
                    job_id=job_id,
                    question_id=102,
                    question_name="Q2",
                    question_type="fill_in_multiple_blanks_question",
                    question_text="Fill in Y",
                    points_possible=1.0,
                    student_answer="Answer B",
                    canvas_points=0.0,
                    correct_answers=["Y"],
                    canvas_user_id="student-1",
                    quiz_submission_id=quiz_submission_id,
                    attempt=attempt,
                    ai_grade=1.0,
                    ai_feedback="Correct",
                ),
            ]
        )
        return job_id, sub_repo

    def test_groups_questions_per_student_into_one_put_call(self, dynamodb_table):
        from unittest.mock import MagicMock, patch

        from src.lti.ags import passback_quiz_grades_via_rest

        job_id, sub_repo = self._make_job_and_subs(dynamodb_table)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            # CanvasAPIClient stores httpx.Client() as self._client (not context manager)
            mock_http = mock_client_cls.return_value
            mock_http.put.return_value = mock_resp

            result = passback_quiz_grades_via_rest(
                job_id=str(job_id),
                quiz_id="Q1",
                course_id="C1",
                canvas_token="tok",
                canvas_url="https://canvas.example.com",
                submission_repo=sub_repo,
            )

        assert result["submitted"] == 1
        assert result["errors"] == []
        assert mock_http.put.call_count == 1
        call_payload = mock_http.put.call_args[1]["json"]
        questions = call_payload["quiz_submissions"][0]["questions"]
        assert "101" in questions
        assert "102" in questions
        assert questions["101"]["score"] == 0.5
        assert questions["102"]["score"] == 1.0

    def test_skips_submissions_with_no_ai_grade(self, dynamodb_table):
        from uuid import uuid4

        from src.lti.ags import passback_quiz_grades_via_rest
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        job_id = uuid4()
        GradingJobRepository(table=dynamodb_table).create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="T")
        )
        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=101,
                    question_name="Q1",
                    question_type="essay_question",
                    question_text="?",
                    points_possible=1.0,
                    student_answer="ans",
                    canvas_points=0.0,
                    correct_answers=[],
                    canvas_user_id="student-1",
                    quiz_submission_id=201,
                    attempt=1,
                    ai_grade=None,
                )
            ]
        )

        result = passback_quiz_grades_via_rest(
            job_id=str(job_id),
            quiz_id="Q1",
            course_id="C1",
            canvas_token="tok",
            canvas_url="https://canvas.example.com",
            submission_repo=sub_repo,
        )
        assert result["submitted"] == 0
        assert result["errors"] == []

    def test_skips_submissions_with_no_quiz_submission_id(self, dynamodb_table):
        from uuid import uuid4

        from src.lti.ags import passback_quiz_grades_via_rest
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        job_id = uuid4()
        GradingJobRepository(table=dynamodb_table).create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="T")
        )
        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=101,
                    question_name="Q1",
                    question_type="essay_question",
                    question_text="?",
                    points_possible=1.0,
                    student_answer="ans",
                    canvas_points=0.0,
                    correct_answers=[],
                    canvas_user_id="student-1",
                    quiz_submission_id=0,  # pre-migration row
                    attempt=1,
                    ai_grade=0.8,
                )
            ]
        )

        result = passback_quiz_grades_via_rest(
            job_id=str(job_id),
            quiz_id="Q1",
            course_id="C1",
            canvas_token="tok",
            canvas_url="https://canvas.example.com",
            submission_repo=sub_repo,
        )
        assert result["submitted"] == 0
        assert result["errors"] == []

    def test_returns_correct_submitted_count_for_multiple_students(
        self, dynamodb_table
    ):
        from unittest.mock import MagicMock, patch
        from uuid import uuid4

        from src.lti.ags import passback_quiz_grades_via_rest
        from src.models.grading_job import GradingJob
        from src.models.submission import Submission
        from src.repositories.grading_job import GradingJobRepository
        from src.repositories.submission import SubmissionRepository

        job_id = uuid4()
        GradingJobRepository(table=dynamodb_table).create(
            GradingJob(job_id=job_id, course_id="C1", quiz_id="Q1", job_name="T")
        )
        sub_repo = SubmissionRepository(table=dynamodb_table)
        sub_repo.batch_create(
            [
                Submission(
                    job_id=job_id,
                    question_id=101,
                    question_name="Q1",
                    question_type="essay_question",
                    question_text="?",
                    points_possible=1.0,
                    student_answer="ans",
                    canvas_points=0.0,
                    correct_answers=[],
                    canvas_user_id="student-1",
                    quiz_submission_id=201,
                    attempt=1,
                    ai_grade=0.5,
                ),
                Submission(
                    job_id=job_id,
                    question_id=101,
                    question_name="Q1",
                    question_type="essay_question",
                    question_text="?",
                    points_possible=1.0,
                    student_answer="ans",
                    canvas_points=0.0,
                    correct_answers=[],
                    canvas_user_id="student-2",
                    quiz_submission_id=202,
                    attempt=1,
                    ai_grade=1.0,
                ),
            ]
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = mock_client_cls.return_value
            mock_http.put.return_value = mock_resp

            result = passback_quiz_grades_via_rest(
                job_id=str(job_id),
                quiz_id="Q1",
                course_id="C1",
                canvas_token="tok",
                canvas_url="https://canvas.example.com",
                submission_repo=sub_repo,
            )

        assert result["submitted"] == 2
        assert mock_http.put.call_count == 2

    def test_surfaces_canvas_errors_without_raising(self, dynamodb_table):
        from unittest.mock import patch

        from src.lti.ags import passback_quiz_grades_via_rest

        job_id, sub_repo = self._make_job_and_subs(dynamodb_table)

        with patch("src.lti.canvas_api.httpx.Client") as mock_client_cls:
            mock_http = mock_client_cls.return_value
            mock_http.put.side_effect = Exception("Canvas 403 Forbidden")

            result = passback_quiz_grades_via_rest(
                job_id=str(job_id),
                quiz_id="Q1",
                course_id="C1",
                canvas_token="tok",
                canvas_url="https://canvas.example.com",
                submission_repo=sub_repo,
            )

        assert result["submitted"] == 0
        assert len(result["errors"]) == 1
        assert "Canvas 403 Forbidden" in result["errors"][0]

    def test_passback_rest_uses_effective_grade_with_override(self, monkeypatch):
        from uuid import uuid4
        from src.models.submission import Submission
        from src.lti.ags import passback_quiz_grades_via_rest

        job_id = uuid4()
        sub = Submission(
            job_id=job_id,
            question_id=1,
            question_name="Q1",
            question_type="essay_question",
            question_text="text",
            points_possible=10.0,
            student_answer="answer",
            canvas_points=0.0,
            correct_answers=[],
            canvas_user_id="u1",
            quiz_submission_id=55,
            attempt=1,
            ai_grade=6.0,
            ai_feedback="AI feedback",
            instructor_grade=9.0,
            instructor_feedback="Instructor feedback",
        )

        class FakeRepo:
            def list_by_job(self, jid):
                return [sub]

        calls = []

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def update_quiz_submission_scores(self, **kwargs):
                calls.append(kwargs)

        monkeypatch.setattr("src.lti.canvas_api.CanvasAPIClient", FakeClient)

        result = passback_quiz_grades_via_rest(
            job_id=str(job_id),
            quiz_id="1",
            course_id="1",
            canvas_token="tok",
            canvas_url="https://canvas.example.com",
            submission_repo=FakeRepo(),
        )

        assert result["submitted"] == 1
        sent_questions = calls[0]["questions"]
        assert sent_questions[1]["score"] == 9.0  # instructor override, not 6.0
        assert (
            sent_questions[1]["comment"]
            == "\x1b[3m(This question's grade and feedback were modified by the instructor. AI assistance may have been used to write the provided feedback.)\x1b[0m\n\nInstructor feedback"
        )

    def test_passback_rest_falls_back_to_ai_grade_without_override(self, monkeypatch):
        from uuid import uuid4
        from src.models.submission import Submission
        from src.lti.ags import passback_quiz_grades_via_rest

        job_id = uuid4()
        sub = Submission(
            job_id=job_id,
            question_id=1,
            question_name="Q1",
            question_type="essay_question",
            question_text="text",
            points_possible=10.0,
            student_answer="answer",
            canvas_points=0.0,
            correct_answers=[],
            canvas_user_id="u1",
            quiz_submission_id=55,
            attempt=1,
            ai_grade=6.0,
            ai_feedback="AI feedback",
        )

        class FakeRepo:
            def list_by_job(self, jid):
                return [sub]

        calls = []

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def update_quiz_submission_scores(self, **kwargs):
                calls.append(kwargs)

        monkeypatch.setattr("src.lti.canvas_api.CanvasAPIClient", FakeClient)

        result = passback_quiz_grades_via_rest(
            job_id=str(job_id),
            quiz_id="1",
            course_id="1",
            canvas_token="tok",
            canvas_url="https://canvas.example.com",
            submission_repo=FakeRepo(),
        )

        sent_questions = calls[0]["questions"]
        assert sent_questions[1]["score"] == 6.0
        assert result["submitted"] == 1
        assert calls[0]["questions"][1]["score"] == 6.0
        assert (
            calls[0]["questions"][1]["comment"]
            == "\x1b[3m(This question's grade and feedback were generated by AI)\x1b[0m\n\nAI feedback"
        )

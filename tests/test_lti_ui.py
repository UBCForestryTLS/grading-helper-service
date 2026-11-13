"""Tests for the instructor UI renderer."""

from src.lti.ui import render_instructor_ui
import pytest


def _render() -> str:
    return render_instructor_ui(
        launch_id="l1",
        session_token="tok",
        base_url="https://api.example.com",
        roles=["Instructor"],
    )


class TestRenderInstructorUI:
    def test_returns_html_string(self):
        html = render_instructor_ui(
            launch_id="launch-abc",
            session_token="test.jwt.token",
            base_url="https://test.example.com/dev",
        )
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")

    def test_includes_session_token_in_meta_tag(self):
        html = render_instructor_ui(
            launch_id="launch-abc",
            session_token="my.session.token",
            base_url="https://test.example.com/dev",
        )
        assert 'name="session-token"' in html
        assert "my.session.token" in html

    def test_includes_launch_id(self):
        html = render_instructor_ui(
            launch_id="my-launch-id-12345",
            session_token="tok",
            base_url="https://base.example.com",
        )
        assert "my-launch-id-12345" in html

    def test_includes_base_url(self):
        html = render_instructor_ui(
            launch_id="l1",
            session_token="tok",
            base_url="https://api.example.com/dev",
        )
        assert "https://api.example.com/dev" in html

    def test_includes_user_name(self):
        html = render_instructor_ui(
            launch_id="l1",
            session_token="tok",
            base_url="https://api.example.com",
            user_name="Test User",
            course_title="Intro to Forestry",
            roles=["Instructor"],
        )
        assert "Test User" in html
        assert "Intro to Forestry" in html
        assert "Instructor" in html

    def test_escapes_html_in_user_info(self):
        html = render_instructor_ui(
            launch_id="l1",
            session_token="tok",
            base_url="https://api.example.com",
            user_name="<img src=x onerror=alert(1)>",
            course_title="<b>Course</b>",
        )
        # Raw tags from user input must not appear unescaped
        assert "<img src=x onerror=alert(1)>" not in html
        assert "&lt;img" in html
        assert "&lt;b&gt;" in html

    def test_contains_js_api_calls(self):
        html = render_instructor_ui(
            launch_id="l1",
            session_token="tok",
            base_url="https://api.example.com",
        )
        assert "/lti/quizzes" in html
        assert "/lti/jobs" in html
        assert "/lti/passback/" in html

    def test_no_cdn_dependencies(self):
        html = render_instructor_ui(
            launch_id="l1",
            session_token="tok",
            base_url="https://api.example.com",
        )
        # Should not load any external scripts or stylesheets
        assert "cdn." not in html
        assert 'src="http' not in html
        assert 'href="http' not in html

    def test_default_roles_is_empty(self):
        # Should not raise when roles is None
        html = render_instructor_ui(
            launch_id="l1",
            session_token="tok",
            base_url="https://api.example.com",
        )
        assert html is not None


class TestConfidenceUI:
    @pytest.mark.parametrize(
        "cls", [".conf-badge", ".conf-low", ".conf-medium", ".conf-high"]
    )
    def test_confidence_badge_styles_present(self, cls):
        assert cls in _render()

    def test_confidence_column_header(self):
        assert "<th>AI Confidence</th>" in _render()

    def test_student_header_spans_all_eight_columns(self):
        assert "headerTd.colSpan = 8" in _render()

    @pytest.mark.parametrize(
        "element_id",
        [
            "sort-select",
            "conf-filter",
            "conf-custom",
            "conf-op",
            "conf-value",
            "override-filter",
            "view-count",
        ],
    )
    def test_controls_present(self, element_id):
        assert f'id="{element_id}"' in _render()

    @pytest.mark.parametrize(
        "name",
        [
            "function applyView",
            "function matchesFilters",
            "function matchesConfidence",
            "function matchesOverride",
            "function isOverridden",
            "function clearFilters",
            "function syncSubmission",
            "function confidenceBand",
        ],
    )
    def test_functions_present(self, name):
        assert name in _render()

    def test_f_string_braces_render_as_single_braces(self):
        assert "let filterState = { conf: 'all'" in _render()

    def test_band_boundaries(self):
        html = _render()
        assert "c <= 50" in html
        assert "c <= 79" in html

    def test_filter_uses_confidence_band(self):
        assert "confidenceBand(c) === m" in _render()

    def test_empty_custom_input_is_null_not_zero(self):
        assert "raw === '' ? null" in _render()

    def test_view_controls_wrap(self):
        assert "flex-wrap: wrap" in _render()

    def test_override_column_css_targets_column_8(self):
        html = _render()
        assert "td:nth-child(8)" in html
        assert "td:nth-child(7)" not in html

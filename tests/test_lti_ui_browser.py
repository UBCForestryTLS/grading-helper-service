"""Browser tests for the instructor UI. Run the real rendered JS against a mocked backend."""

import json

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import Page, expect

from src.lti.ui import render_instructor_ui

BASE = "http://test.local"


def _sub(sid, uid, qid, grade, max_pts=10):
    return {
        "submission_id": sid,
        "canvas_user_id": uid,
        "question_id": qid,
        "question_name": f"Q{qid}",
        "question_text": "text",
        "student_answer": "ans",
        "points_possible": max_pts,
        "effective_grade": grade,
        "instructor_grade": None,
        "instructor_feedback": None,
        "effective_feedback": "ok",
        "grading_status": "GRADED",
        "overridden_by": None,
    }


@pytest.fixture
def app(page: Page):
    subs = {
        s["submission_id"]: s
        for s in [
            _sub("a1", "A", "q1", 8),
            _sub("a2", "A", "q2", 6),  # A = 14/20 = 70%
            _sub("b1", "B", "q1", 10),
            _sub("b2", "B", "q2", 10),  # B = 20/20 = 100%
        ]
    }
    originals = {k: v["effective_grade"] for k, v in subs.items()}
    html = render_instructor_ui(
        launch_id="L1",
        session_token="tok",
        base_url=BASE,
        user_name="T",
        course_title="C",
        roles=["Instructor"],
    )

    def handle(route):
        req = route.request
        path = req.url.replace(BASE, "")
        if path == "/":
            return route.fulfill(status=200, content_type="text/html", body=html)
        if path == "/jobs/job1":
            return route.fulfill(json={"status": "COMPLETED", "effective_prompt": "p"})
        if path == "/jobs/job1/submissions":
            return route.fulfill(json=list(subs.values()))
        if path.startswith("/jobs/job1/submissions/") and req.method == "PATCH":
            sid = path.rsplit("/", 1)[1]
            body = json.loads(req.post_data)
            s = subs[sid]
            if body.get("revert"):
                s["instructor_grade"] = None
                s["effective_grade"] = originals[sid]
            elif "grade" in body:
                s["instructor_grade"] = body["grade"]
                s["effective_grade"] = body["grade"]
            return route.fulfill(json=s)
        return route.fulfill(status=404, json={"detail": "not mocked: " + path})

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route(f"{BASE}/**", handle)
    page.on("dialog", lambda d: d.accept())
    page.goto(BASE + "/")
    page.evaluate("viewJobResults('job1', 'Job 1', 'COMPLETED')")
    expect(page.locator("#stat-avg")).to_have_text("85.0%")
    page.js_errors = errors
    return page


def override(page, sid, grade):
    page.fill(f"#input-grade-{sid}", str(grade))
    page.click(f'tr[data-submission-id="{sid}"] .btn-save')


def header(page, uid):
    return page.locator(f'tr.student-header[data-uid="{uid}"]')


def rows(page, uid):
    return page.locator(f'tr.student-row[data-uid="{uid}"]')


def test_page_loads_without_js_errors(app):
    assert app.js_errors == []


def test_avg_updates_after_override(app):
    override(app, "a2", 10)  # A: 18/20 = 90%, B: 100% -> 95%
    expect(app.locator("#stat-avg")).to_have_text("95.0%")
    expect(header(app, "A")).to_contain_text("18.0 / 20.0 points")


def test_avg_returns_after_revert(app):
    override(app, "a2", 10)
    expect(app.locator("#stat-avg")).to_have_text("95.0%")
    app.click('tr[data-submission-id="a2"] .btn-revert')
    expect(app.locator("#stat-avg")).to_have_text("85.0%")
    expect(header(app, "A")).to_contain_text("14.0 / 20.0 points")
    expect(app.locator("#feedback-cell-a2")).not_to_have_text("true")


def test_groups_start_expanded(app):
    expect(rows(app, "A")).to_have_count(2)
    for r in rows(app, "A").all():
        expect(r).to_be_visible()


def test_click_header_collapses_only_that_group(app):
    header(app, "A").click()
    for r in rows(app, "A").all():
        expect(r).to_be_hidden()
    for r in rows(app, "B").all():
        expect(r).to_be_visible()
    header(app, "A").click()
    for r in rows(app, "A").all():
        expect(r).to_be_visible()


def test_collapse_keeps_typed_text(app):
    app.fill("#input-feedback-a1", "half-written note")
    header(app, "A").click()
    header(app, "A").click()
    expect(app.locator("#input-feedback-a1")).to_have_value("half-written note")


def test_override_elsewhere_keeps_group_collapsed(app):
    header(app, "A").click()
    override(app, "b1", 5)  # B = 15/20 = 75%, A = 70% -> 72.5%
    expect(app.locator("#stat-avg")).to_have_text("72.5%")
    for r in rows(app, "A").all():
        expect(r).to_be_hidden()

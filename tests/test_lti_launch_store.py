"""Tests for the LTI launch context store."""

import time


from src.lti.launch_store import LaunchStore


class TestLaunchStore:
    def test_create_and_get_roundtrip(self, dynamodb_table):
        store = LaunchStore(table=dynamodb_table)
        claims = {
            "sub": "user-456",
            "iss": "https://canvas.test.instructure.com",
            "https://purl.imsglobal.org/spec/lti/claim/context": {
                "id": "course-123",
                "label": "FRST101",
                "title": "Intro to Forestry",
            },
            "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                "lineitem": "https://canvas.test.instructure.com/api/lti/courses/1/line_items/1",
                "scope": [
                    "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
                    "https://purl.imsglobal.org/spec/lti-ags/scope/score",
                ],
            },
            "https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice": {
                "context_memberships_url": "https://canvas.test.instructure.com/api/lti/courses/1/names_and_roles",
            },
        }

        launch_id = store.create(claims)
        assert launch_id is not None
        assert len(launch_id) == 32  # uuid4().hex

        result = store.get(launch_id)
        assert result is not None
        assert result["launch_id"] == launch_id
        assert result["canvas_user_id"] == "user-456"
        assert result["course_id"] == "course-123"
        assert result["iss"] == "https://canvas.test.instructure.com"
        assert "ags_lineitem_url" in result
        assert "nrps_context_memberships_url" in result

    def test_get_returns_none_for_missing(self, dynamodb_table):
        store = LaunchStore(table=dynamodb_table)
        result = store.get("nonexistent-launch-id")
        assert result is None

    def test_ttl_field_is_set(self, dynamodb_table):
        store = LaunchStore(table=dynamodb_table)
        claims = {
            "sub": "user-1",
            "iss": "https://canvas.test.instructure.com",
            "https://purl.imsglobal.org/spec/lti/claim/context": {"id": "course-1"},
        }

        launch_id = store.create(claims)
        result = store.get(launch_id)

        assert "ttl" in result
        # TTL should be approximately now + 24h
        expected_ttl = int(time.time()) + 86400
        assert abs(int(result["ttl"]) - expected_ttl) < 5

    def test_create_with_minimal_claims(self, dynamodb_table):
        """Should handle claims without AGS or NRPS gracefully."""
        store = LaunchStore(table=dynamodb_table)
        claims = {
            "sub": "user-1",
            "iss": "https://canvas.test.instructure.com",
        }

        launch_id = store.create(claims)
        result = store.get(launch_id)

        assert result is not None
        assert result["canvas_user_id"] == "user-1"
        assert result["course_id"] == ""
        assert "ags_lineitem_url" not in result  # not stored when empty
        assert "ags_scope" not in result

    def test_create_returns_unique_ids(self, dynamodb_table):
        store = LaunchStore(table=dynamodb_table)
        claims = {"sub": "user-1", "iss": "https://canvas.test.instructure.com"}

        id1 = store.create(claims)
        id2 = store.create(claims)
        assert id1 != id2

    def test_ags_scope_string_is_split(self, dynamodb_table):
        """Canvas may send scope as a space-separated string instead of a list."""
        store = LaunchStore(table=dynamodb_table)
        claims = {
            "sub": "user-1",
            "iss": "https://canvas.test.instructure.com",
            "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
                "lineitem": "https://canvas.example.com/lineitem/1",
                "scope": "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem https://purl.imsglobal.org/spec/lti-ags/scope/score",
            },
        }

        launch_id = store.create(claims)
        result = store.get(launch_id)
        assert isinstance(result["ags_scope"], list)
        assert len(result["ags_scope"]) == 2

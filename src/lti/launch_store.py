"""DynamoDB-backed storage for LTI launch context after JWT validation."""

import time
from uuid import uuid4

from src.core.aws import get_dynamodb_table


class LaunchStore:
    """Stores LTI launch context keyed by launch_id for 24 hours."""

    def __init__(self, table=None):
        self._table = table

    @property
    def table(self):
        if self._table is None:
            self._table = get_dynamodb_table()
        return self._table

    def create(self, claims: dict) -> str:
        """Store LTI launch context from JWT claims. Returns launch_id."""
        launch_id = uuid4().hex

        context = claims.get("https://purl.imsglobal.org/spec/lti/claim/context", {})
        ags_endpoint = claims.get(
            "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint", {}
        )
        nrps_claim = claims.get(
            "https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice", {}
        )

        ags_scope = ags_endpoint.get("scope", [])
        if isinstance(ags_scope, str):
            ags_scope = ags_scope.split()

        item: dict = {
            "pk": f"LAUNCH#{launch_id}",
            "sk": "LAUNCH",
            "launch_id": launch_id,
            "canvas_user_id": claims.get("sub", ""),
            "course_id": context.get("id", ""),
            "iss": claims.get("iss", ""),
            "ttl": int(time.time()) + 86400,  # 24h
        }

        ags_lineitem_url = ags_endpoint.get("lineitem", "")
        if ags_lineitem_url:
            item["ags_lineitem_url"] = ags_lineitem_url
        if ags_scope:
            item["ags_scope"] = ags_scope

        nrps_url = nrps_claim.get("context_memberships_url", "")
        if nrps_url:
            item["nrps_context_memberships_url"] = nrps_url

        self.table.put_item(Item=item)
        return launch_id

    def get(self, launch_id: str) -> dict | None:
        """Get launch context by launch_id. Returns dict or None if not found."""
        response = self.table.get_item(
            Key={"pk": f"LAUNCH#{launch_id}", "sk": "LAUNCH"}
        )
        return response.get("Item")

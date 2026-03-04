"""DynamoDB-backed LTI state storage for the OIDC login-to-launch flow.

Stores state+nonce pairs created at login initiation, validated at launch.
Uses DynamoDB TTL for automatic cleanup of orphaned states.
"""

import time
from uuid import uuid4

from src.core.aws import get_dynamodb_table


class LTIStateStore:
    def __init__(self, table=None):
        self._table = table

    @property
    def table(self):
        if self._table is None:
            self._table = get_dynamodb_table()
        return self._table

    def create(self, platform_id: str) -> tuple[str, str]:
        """Create and store a new state+nonce pair. Returns (state, nonce)."""
        state = uuid4().hex
        nonce = uuid4().hex
        self.table.put_item(
            Item={
                "pk": f"LTI_STATE#{state}",
                "sk": "STATE",
                "nonce": nonce,
                "platform_id": platform_id,
                "ttl": int(time.time()) + 600,  # 10 min
            }
        )
        return state, nonce

    def validate(self, state: str) -> dict | None:
        """Atomically retrieve and delete state (one-time use). Returns {nonce, platform_id} or None."""
        response = self.table.delete_item(
            Key={"pk": f"LTI_STATE#{state}", "sk": "STATE"},
            ReturnValues="ALL_OLD",
        )
        item = response.get("Attributes")
        if not item:
            return None
        if item.get("ttl", 0) < int(time.time()):
            return None
        return {"nonce": item["nonce"], "platform_id": item["platform_id"]}

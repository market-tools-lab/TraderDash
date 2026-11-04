"""Local account export and deletion.

Production and the preview project are refused. The export contains the
account fields a person can already see, and never a hash or a token.
"""

from __future__ import annotations

from typing import Any, Mapping

PRODUCTION_REF = "wxvobyifckbpnqfbnlxl"
PREVIEW_REF = "ajbsoudovxstlolojvte"
PROTECTED_REFS = frozenset({PRODUCTION_REF, PREVIEW_REF})
PROTECTED_IDS = frozenset(
    {
        "e8469788-5089-45f4-8a77-60440aa56fc7",
        "7a65eb8c-2776-4447-b45c-f5dc542a5abb",
        "63ffe985-0e7e-48bd-b41b-d1741330257a",
    }
)
CONFIRMATION = "DELETE-LOCAL-ACCOUNT"
EXPORT_FIELDS = ("user_id", "email", "plan", "subscription_status", "created_at")
_FORBIDDEN = frozenset(
    {
        "password",
        "password_hash",
        "access_token",
        "token",
        "secret",
        "database_url",
        "service_role",
    }
)


class PrivacyRejected(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def export_account(row: Mapping[str, Any]) -> dict[str, Any]:
    exported = {field: row[field] for field in EXPORT_FIELDS if field in row}
    leaked = _FORBIDDEN.intersection(exported)
    if leaked:
        raise PrivacyRejected("export")
    return exported


def delete_local(
    ledger: dict[str, Any],
    user_id: str,
    *,
    target_ref: str,
    confirmation: str,
) -> str:
    if target_ref in PROTECTED_REFS or not target_ref:
        raise PrivacyRejected("target")
    if user_id in PROTECTED_IDS:
        raise PrivacyRejected("protected")
    if confirmation != CONFIRMATION:
        raise PrivacyRejected("confirmation")
    users = ledger.get("users")
    if not isinstance(users, dict) or user_id not in users:
        raise PrivacyRejected("missing")
    users.pop(user_id, None)
    for key in ("entitlements", "links"):
        bucket = ledger.get(key)
        if isinstance(bucket, dict):
            bucket.pop(user_id, None)
    return "deleted"

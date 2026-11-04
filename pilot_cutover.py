"""Preview copy of one named pilot. Production is not contacted.

The reference address is a label for the existing test account. It is not
stored on preview and it is not used to send mail. The preview row uses the
reserved synthetic identity. The migration receives only the four legacy
fields. A password hash is never one of them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from pilot_migration import (
    PREVIEW_API_URL,
    PREVIEW_PROJECT_REF,
    AuthAccount,
    LegacyAccount,
    MigrationRequest,
    TargetRejected,
    require_preview_target,
)

REFERENCE_LABEL = "traderdashtesttest@example.dk"
PREVIEW_EMAIL = "markettools-mig-i7pilot@example.invalid"
PREVIEW_LEGACY_ID = "legacy-mig-i7pilot"
PLAN = "free"
STATUS = "free"
REFERENCE = "pilot-i7"
FIELDS = ("user_id", "email", "plan", "subscription_status")
_FORBIDDEN = re.compile(r"password|token|secret|credential|database_url|session", re.IGNORECASE)


def preview_fields() -> dict[str, str]:
    """The only values the preview copy is allowed to carry."""
    return {
        "user_id": PREVIEW_LEGACY_ID,
        "email": PREVIEW_EMAIL,
        "plan": PLAN,
        "subscription_status": STATUS,
    }


def accept_fields(fields: Mapping[str, object]) -> LegacyAccount:
    """Reject every field the migration must not see."""
    for key in fields:
        if _FORBIDDEN.search(str(key)):
            raise TargetRejected("pilot input contains a forbidden field")
    names = {str(key) for key in fields}
    if names != set(FIELDS):
        raise TargetRejected("pilot input is not the four migration fields")
    values = {key: str(fields[key]).strip() for key in FIELDS}
    folded = " ".join(values.values()).lower()
    if REFERENCE_LABEL in folded or "password" in folded or "@example.dk" in folded:
        raise TargetRejected("pilot input contains the reference address or a secret")
    if values["user_id"] != PREVIEW_LEGACY_ID or values["email"] != PREVIEW_EMAIL:
        raise TargetRejected("preview identity is not the reserved synthetic account")
    if values["plan"] != PLAN or values["subscription_status"] != STATUS:
        raise TargetRejected("pilot copy is not the known free account")
    return LegacyAccount(
        user_id=values["user_id"],
        email=values["email"],
        plan=values["plan"],
        subscription_status=values["subscription_status"],
    )


def request_for(auth_user_id: str) -> tuple[MigrationRequest, LegacyAccount, AuthAccount]:
    """Build the preview migration. The reference address is not included."""
    require_preview_target(PREVIEW_PROJECT_REF, PREVIEW_API_URL)
    legacy = accept_fields(preview_fields())
    auth = AuthAccount(user_id=str(auth_user_id), email=legacy.email)
    request = MigrationRequest(
        project_ref=PREVIEW_PROJECT_REF,
        api_url=PREVIEW_API_URL,
        legacy_user_id=legacy.user_id,
        auth_user_id=auth.user_id,
        migration_reference=REFERENCE,
    )
    return request, legacy, auth

"""Read-only dry-run for one named pilot.

The command does not open a database and does not accept a connection
string. A later operator can pass query functions. Those functions are not
called until the confirmation phrase matches. The report never contains a
password, a hash, a token, or the address itself.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pilot_migration
import universes

CONFIRMATION = "CONFIRM-PRODUCTION-PILOT"
REFERENCE_EMAIL = "traderdashtesttest@example.dk"
LEGACY_SELECT = (
    "select user_id, email, plan, subscription_status "
    "from public.users where lower(email) = lower(%s)"
)
AUTH_SELECT = "select id, email from auth.users where lower(email) = lower(%s)"
LINK_SELECT = (
    "select legacy_user_id, auth_user_id, migration_status "
    "from public.legacy_auth_links where legacy_user_id = %s"
)
_FORBIDDEN = ("password", "token", "secret", "credential", "database_url", "session")
Query = Callable[[str, tuple[str]], Sequence[Mapping[str, object]]]


class ReadinessRejected(Exception):
    """A fixed refusal. The message never contains row values."""


@dataclass(frozen=True)
class PilotReport:
    outcome: str
    legacy_user_id: str
    plan: str
    subscription_status: str
    entitlement_plan: str | None
    entitlement_status: str | None
    grants_access: bool
    expected_papers: int | None
    auth_identity_exists: bool
    link_exists: bool
    wrote: bool = False

    def public_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "legacy_user_id": self.legacy_user_id,
            "plan": self.plan,
            "subscription_status": self.subscription_status,
            "entitlement_plan": self.entitlement_plan,
            "entitlement_status": self.entitlement_status,
            "grants_access": self.grants_access,
            "expected_papers": self.expected_papers,
            "auth_identity_exists": self.auth_identity_exists,
            "link_exists": self.link_exists,
            "wrote": self.wrote,
        }


def dry_run(
    query_legacy: Query,
    query_auth: Query,
    query_links: Query,
    *,
    confirmation: str,
) -> PilotReport:
    """Inspect one pilot. Queries stay uncalled until confirmation matches."""
    if confirmation != CONFIRMATION:
        raise ReadinessRejected("production confirmation is required")
    _require_safe_sql()
    legacy_rows = _rows(query_legacy(LEGACY_SELECT, (REFERENCE_EMAIL,)))
    if len(legacy_rows) != 1:
        raise ReadinessRejected("pilot inspection requires exactly one legacy user")
    legacy = _legacy(legacy_rows[0])
    auth_rows = _rows(query_auth(AUTH_SELECT, (REFERENCE_EMAIL,)))
    link_rows = _rows(query_links(LINK_SELECT, (legacy["user_id"],)))
    return inspect_rows(legacy, auth_rows, link_rows)


def inspect_rows(
    legacy: Mapping[str, object],
    auth_rows: Sequence[Mapping[str, object]],
    link_rows: Sequence[Mapping[str, object]],
) -> PilotReport:
    """Build the redacted report. The inputs are not modified."""
    account = _legacy(legacy)
    identities = [_auth(row) for row in auth_rows]
    links = [_link(row) for row in link_rows]
    if len(identities) > 1 or len(links) > 1:
        raise ReadinessRejected("pilot inspection requires exactly one legacy user")
    mapped = pilot_migration.map_legacy(account["plan"], account["subscription_status"])
    identity = identities[0] if identities else None
    link = links[0] if links else None
    papers = len(universes.stocks_for(mapped.plan_code)) if mapped.grants_access and mapped.plan_code else None
    if mapped.outcome == "rejected":
        outcome = "rejected"
    elif link and identity and link["auth_user_id"] != identity["id"]:
        outcome = "link_conflict"
    elif link and identity is None:
        outcome = "link_without_auth"
    elif link:
        outcome = "already_linked"
    elif identity is None:
        outcome = "missing_auth"
    elif mapped.grants_access:
        outcome = "ready"
    else:
        outcome = "closed"
    return PilotReport(
        outcome=outcome,
        legacy_user_id=account["user_id"],
        plan=account["plan"],
        subscription_status=account["subscription_status"],
        entitlement_plan=mapped.plan_code,
        entitlement_status=mapped.entitlement_status,
        grants_access=mapped.grants_access,
        expected_papers=papers,
        auth_identity_exists=identity is not None,
        link_exists=link is not None,
        wrote=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Refuse every command. This iteration does not contact Production."""
    del argv
    sys.stderr.write("Refused. Production is not contacted from this command.\n")
    return 2


def _require_safe_sql() -> None:
    for statement in (LEGACY_SELECT, AUTH_SELECT, LINK_SELECT):
        folded = statement.lower()
        if any(word in folded for word in _FORBIDDEN) or "insert " in folded or "update " in folded:
            raise ReadinessRejected("pilot select is not safe")


def _rows(value: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ReadinessRejected("pilot query did not return rows")
    return list(value)


def _legacy(row: Mapping[str, object]) -> dict[str, str]:
    _reject_forbidden(row)
    if set(row) != {"user_id", "email", "plan", "subscription_status"}:
        raise ReadinessRejected("pilot input is not the four migration fields")
    email = str(row["email"] or "").strip().lower()
    if email != REFERENCE_EMAIL:
        raise ReadinessRejected("pilot inspection requires exactly one legacy user")
    return {
        "user_id": str(row["user_id"] or "").strip(),
        "email": email,
        "plan": str(row["plan"] or "").strip().lower(),
        "subscription_status": str(row["subscription_status"] or "").strip().lower(),
    }


def _auth(row: Mapping[str, object]) -> dict[str, str]:
    _reject_forbidden(row)
    if set(row) != {"id", "email"}:
        raise ReadinessRejected("auth input is not the identity fields")
    email = str(row["email"] or "").strip().lower()
    if email != REFERENCE_EMAIL:
        raise ReadinessRejected("pilot inspection requires exactly one legacy user")
    return {"id": str(row["id"] or "").strip(), "email": email}


def _link(row: Mapping[str, object]) -> dict[str, str]:
    _reject_forbidden(row)
    if set(row) != {"legacy_user_id", "auth_user_id", "migration_status"}:
        raise ReadinessRejected("link input is not the link fields")
    return {
        "legacy_user_id": str(row["legacy_user_id"] or "").strip(),
        "auth_user_id": str(row["auth_user_id"] or "").strip(),
        "migration_status": str(row["migration_status"] or "").strip(),
    }


def _reject_forbidden(row: Mapping[str, object]) -> None:
    for key in row:
        folded = str(key).lower()
        if any(word in folded for word in _FORBIDDEN):
            raise ReadinessRejected("pilot input contains a forbidden field")


if __name__ == "__main__":
    sys.exit(main())

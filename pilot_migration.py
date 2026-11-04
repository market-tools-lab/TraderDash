"""Pilot migration from one legacy account to a Supabase Auth entitlement.

The function reads the legacy plan and subscription status. It never reads or
writes a password hash, never deletes the legacy row, and never updates
auth.users. Writes happen only after the caller proves the preview target.
A missing or different target raises before any gateway call.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from supabase_auth import PLANS, TRADERDASH_PRODUCT

PREVIEW_PROJECT_REF = "ajbsoudovxstlolojvte"
PREVIEW_API_URL = "https://ajbsoudovxstlolojvte.supabase.co"
LEGACY_FIELDS = ("user_id", "email", "plan", "subscription_status")
_LEGACY_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
_REFERENCE = re.compile(r"[A-Za-z0-9_.:/-]{1,120}")
_GRANT_STATUSES = {"active"}
_CLOSED_STATUS = {
    "trialing": "suspended",
    "past_due": "suspended",
    "suspended": "suspended",
    "unpaid": "revoked",
    "revoked": "revoked",
    "cancelled": "expired",
    "canceled": "expired",
    "incomplete": "expired",
    "expired": "expired",
}


class TargetRejected(Exception):
    """The caller did not name the allowed preview project."""


@dataclass(frozen=True)
class LegacyAccount:
    user_id: str
    email: str
    plan: str
    subscription_status: str | None


@dataclass(frozen=True)
class AuthAccount:
    user_id: str
    email: str


@dataclass(frozen=True)
class MigrationRequest:
    project_ref: str
    api_url: str
    legacy_user_id: str
    auth_user_id: str
    product_code: str = TRADERDASH_PRODUCT
    migration_reference: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


@dataclass(frozen=True)
class MigrationReport:
    outcome: str
    reason: str
    legacy_user_id: str
    auth_user_id: str
    plan_code: str | None
    entitlement_status: str | None
    grants_access: bool
    wrote: bool
    ignored_ends_at: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "reason": self.reason,
            "legacy_user_id": self.legacy_user_id,
            "auth_user_id": self.auth_user_id,
            "plan_code": self.plan_code,
            "entitlement_status": self.entitlement_status,
            "grants_access": self.grants_access,
            "wrote": self.wrote,
            "ignored_ends_at": self.ignored_ends_at,
        }


@dataclass(frozen=True)
class _Mapped:
    outcome: str
    reason: str
    plan_code: str | None = None
    entitlement_status: str | None = None
    grants_access: bool = False


class RecordingGateway:
    """In-memory stand-in. Tests and the preview runner share it."""

    def __init__(self) -> None:
        self.legacy: dict[str, LegacyAccount] = {}
        self.auth: dict[str, AuthAccount] = {}
        self.catalog = {(TRADERDASH_PRODUCT, plan) for plan in PLANS}
        self.links_by_legacy: dict[str, dict[str, str]] = {}
        self.links_by_auth: dict[str, dict[str, str]] = {}
        self.entitlements: dict[tuple[str, str], dict[str, str | None]] = {}
        self.writes: list[dict[str, str | None]] = []

    def legacy_user(self, user_id: str) -> LegacyAccount | None:
        return self.legacy.get(user_id)

    def auth_user(self, user_id: str) -> AuthAccount | None:
        return self.auth.get(user_id)

    def product_plan_exists(self, product_code: str, plan_code: str) -> bool:
        return (product_code, plan_code) in self.catalog

    def link_for_legacy(self, legacy_user_id: str) -> Mapping[str, str] | None:
        return self.links_by_legacy.get(legacy_user_id)

    def link_for_auth(self, auth_user_id: str) -> Mapping[str, str] | None:
        return self.links_by_auth.get(auth_user_id)

    def entitlement_for(self, auth_user_id: str, product_code: str) -> Mapping[str, str | None] | None:
        return self.entitlements.get((auth_user_id, product_code))

    def write_link(self, row: Mapping[str, str | None]) -> None:
        stored = {key: row[key] for key in ("legacy_user_id", "auth_user_id", "migration_reference")}
        stored["migration_status"] = "migrated"
        self.links_by_legacy[str(stored["legacy_user_id"])] = stored
        self.links_by_auth[str(stored["auth_user_id"])] = stored
        self.writes.append({"kind": "link", **stored})

    def write_entitlement(self, row: Mapping[str, str | None]) -> None:
        stored = {
            "auth_user_id": row["auth_user_id"],
            "product_code": row["product_code"],
            "plan_code": row["plan_code"],
            "status": row["status"],
            "source": "migration",
        }
        self.entitlements[(str(stored["auth_user_id"]), str(stored["product_code"]))] = stored
        self.writes.append({"kind": "entitlement", **stored})


def require_preview_target(project_ref: str | None, api_url: str | None) -> None:
    """Refuse every target except the named preview project."""
    if project_ref is None or api_url is None or not str(project_ref).strip() or not str(api_url).strip():
        raise TargetRejected("preview target is not configured")
    if str(project_ref).strip() != PREVIEW_PROJECT_REF:
        raise TargetRejected("project ref is not the preview project")
    if str(api_url).strip().rstrip("/") != PREVIEW_API_URL:
        raise TargetRejected("api url is not the preview project")


def map_legacy(plan: str | None, subscription_status: str | None) -> _Mapped:
    """Fail closed. Trialing and a future cancellation end do not grant access."""
    plan_code = str(plan or "").strip().lower()
    status = str(subscription_status or "").strip().lower()
    if plan_code not in PLANS:
        return _Mapped("rejected", "unknown_plan")
    if not status:
        return _Mapped("rejected", "unknown_status")
    if status == "free":
        if plan_code != "free":
            return _Mapped("rejected", "inconsistent_status")
        return _Mapped("granted", "free", "free", "active", True)
    if status in _GRANT_STATUSES:
        return _Mapped("granted", "active", plan_code, "active", True)
    closed = _CLOSED_STATUS.get(status)
    if closed is None:
        return _Mapped("rejected", "unknown_status")
    return _Mapped("closed", status, plan_code, closed, False)


def migrate(
    request: MigrationRequest,
    gateway: RecordingGateway,
    *,
    dry_run: bool = False,
) -> MigrationReport:
    require_preview_target(request.project_ref, request.api_url)
    legacy = gateway.legacy_user(request.legacy_user_id)
    if legacy is None:
        return _reject("missing_legacy", request)
    auth = gateway.auth_user(request.auth_user_id)
    if auth is None:
        return _reject("missing_auth", request)
    if _email_key(legacy.email) != _email_key(auth.email):
        return _reject("email_mismatch", request)
    mapped = map_legacy(legacy.plan, legacy.subscription_status)
    if mapped.outcome == "rejected":
        return _reject(mapped.reason, request)
    if request.product_code != TRADERDASH_PRODUCT or not gateway.product_plan_exists(
        request.product_code, str(mapped.plan_code)
    ):
        return _reject("unknown_plan", request)
    legacy_link = gateway.link_for_legacy(request.legacy_user_id)
    auth_link = gateway.link_for_auth(request.auth_user_id)
    if legacy_link and legacy_link["auth_user_id"] != request.auth_user_id:
        return _reject("legacy_already_linked", request)
    if auth_link and auth_link["legacy_user_id"] != request.legacy_user_id:
        return _reject("auth_already_linked", request)
    current = gateway.entitlement_for(request.auth_user_id, request.product_code)
    if current and current.get("source") not in (None, "migration"):
        return _reject("entitlement_conflict", request)
    same = _same_entitlement(current, mapped)
    if current is not None and not same:
        return _reject("entitlement_drift", request)
    ignored_ends_at = request.ends_at is not None and not mapped.grants_access
    if dry_run:
        return MigrationReport(
            "dry_run",
            mapped.reason,
            request.legacy_user_id,
            request.auth_user_id,
            mapped.plan_code,
            mapped.entitlement_status,
            mapped.grants_access,
            False,
            ignored_ends_at,
        )
    if legacy_link and same:
        return MigrationReport(
            "already_migrated",
            mapped.reason,
            request.legacy_user_id,
            request.auth_user_id,
            mapped.plan_code,
            mapped.entitlement_status,
            mapped.grants_access,
            False,
            ignored_ends_at,
        )
    wrote = False
    if legacy_link is None:
        gateway.write_link(
            {
                "legacy_user_id": request.legacy_user_id,
                "auth_user_id": request.auth_user_id,
                "migration_reference": request.migration_reference,
            }
        )
        wrote = True
    if not same:
        gateway.write_entitlement(
            {
                "auth_user_id": request.auth_user_id,
                "product_code": request.product_code,
                "plan_code": mapped.plan_code,
                "status": mapped.entitlement_status,
            }
        )
        wrote = True
    return MigrationReport(
        mapped.outcome,
        mapped.reason,
        request.legacy_user_id,
        request.auth_user_id,
        mapped.plan_code,
        mapped.entitlement_status,
        mapped.grants_access,
        wrote,
        ignored_ends_at,
    )


def sql_for_writes(writes: list[Mapping[str, str | None]]) -> list[str]:
    """Preview SQL for writes already accepted by migrate. No credentials."""
    statements: list[str] = []
    for write in writes:
        if write.get("kind") == "link":
            statements.append(_link_sql(write))
        elif write.get("kind") == "entitlement":
            statements.append(_entitlement_sql(write))
        else:
            raise TargetRejected("unknown migration write")
    return statements


def _reject(reason: str, request: MigrationRequest) -> MigrationReport:
    return MigrationReport(
        "rejected",
        reason,
        request.legacy_user_id,
        request.auth_user_id,
        None,
        None,
        False,
        False,
        False,
    )


def _email_key(email: str) -> str:
    return str(email or "").strip().lower()


def _same_entitlement(current: Mapping[str, str | None] | None, mapped: _Mapped) -> bool:
    if current is None:
        return False
    return current.get("plan_code") == mapped.plan_code and current.get("status") == mapped.entitlement_status


def _link_sql(write: Mapping[str, str | None]) -> str:
    legacy_user_id = _checked_legacy_id(write.get("legacy_user_id"))
    auth_user_id = _checked_uuid(write.get("auth_user_id"))
    reference = _checked_reference(write.get("migration_reference"))
    reference_sql = "null" if reference is None else f"'{reference}'"
    return (
        "insert into public.legacy_auth_links "
        "(legacy_user_id, auth_user_id, migration_status, migration_reference) "
        f"values ('{legacy_user_id}', '{auth_user_id}'::uuid, 'migrated', {reference_sql})"
    )


def _entitlement_sql(write: Mapping[str, str | None]) -> str:
    auth_user_id = _checked_uuid(write.get("auth_user_id"))
    product = str(write.get("product_code") or "")
    plan = str(write.get("plan_code") or "")
    status = str(write.get("status") or "")
    if product != TRADERDASH_PRODUCT or plan not in PLANS:
        raise TargetRejected("refusing entitlement outside the traderdash catalogue")
    if status not in {"active", "expired", "revoked", "suspended"}:
        raise TargetRejected("refusing entitlement status")
    return (
        "insert into public.entitlements (user_id, product_id, plan_id, status, source) "
        "select "
        f"'{auth_user_id}'::uuid, p.id, pl.id, '{status}', 'migration' "
        "from public.products p "
        "join public.plans pl on pl.product_id = p.id and pl.code = "
        f"'{plan}' where p.code = 'traderdash'"
    )


def _checked_legacy_id(value: str | None) -> str:
    text = str(value or "")
    if not _LEGACY_ID.fullmatch(text):
        raise TargetRejected("unsafe legacy user id")
    return text


def _checked_uuid(value: str | None) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise TargetRejected("unsafe auth user id") from None


def _checked_reference(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if not _REFERENCE.fullmatch(text):
        raise TargetRejected("unsafe migration reference")
    return text

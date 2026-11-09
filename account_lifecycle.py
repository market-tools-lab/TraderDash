"""Account deletion planning. Nothing here deletes a real account.

The dry-run reads a supplied record and returns a decision. Execution stays
off, including when a test asks for it. Production and the deleted preview
are never a target.
"""

from __future__ import annotations

from typing import Any, Mapping

import account_privacy

DELETION_UI_ENABLED = False
DELETION_EXECUTION_ENABLED = False
COOLING_OFF_DAYS = 14
PAID_STATUSES = frozenset({"active", "trialing", "past_due"})
PAID_SOURCES = frozenset({"subscription", "purchase"})


class LifecycleRejected(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def plan_deletion(account: Mapping[str, Any]) -> dict[str, Any]:
    """Describe what deletion would do. The record is not modified."""
    user_id = str(account.get("user_id") or "").strip()
    auth_id = str(account.get("auth_user_id") or "").strip()
    legacy = account.get("legacy_user") if isinstance(account.get("legacy_user"), Mapping) else None
    link = account.get("legacy_link") if isinstance(account.get("legacy_link"), Mapping) else None
    entitlements = _entitlements(account.get("entitlements"))
    profile = bool(account.get("profile"))
    target_ref = str(account.get("target_ref") or "").strip()
    subscription = str(account.get("subscription_status") or (legacy or {}).get("subscription_status") or "").strip()
    paid = _paid(subscription, entitlements)
    mode = _mode(auth_id, legacy, link, paid)
    protected = _protected(user_id, auth_id, legacy, link)
    blockers = []
    if not user_id or mode == "malformed" or _duplicate_active(entitlements):
        blockers.append("malformed")
    if not target_ref:
        blockers.append("missing_configuration")
    elif target_ref in account_privacy.PROTECTED_REFS:
        blockers.append("environment")
    if protected:
        blockers.append("protected")
    if paid:
        blockers.append("active_paid_subscription")
    if not DELETION_EXECUTION_ENABLED:
        blockers.append("execution_disabled")
    return {
        "user_id": user_id,
        "account_mode": mode,
        "profile_rows": 1 if profile else 0,
        "entitlements": len(entitlements),
        "legacy_links": 1 if link else 0,
        "legacy_rows": 1 if legacy else 0,
        "application_data": [],
        "actions": _actions(mode, paid, legacy),
        "blocking": blockers,
        "protected": protected,
        "paid_subscription": paid,
        "cooling_off_days": COOLING_OFF_DAYS,
        "deletion_allowed": False,
        "execution_enabled": DELETION_EXECUTION_ENABLED,
        "ui_enabled": DELETION_UI_ENABLED,
    }


def apply_deletion(account: Mapping[str, Any], *, confirmation: str = "") -> None:
    """Refuse every deletion. The record is not modified."""
    plan_deletion(account)
    raise LifecycleRejected("execution_disabled")


def _entitlements(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _duplicate_active(entitlements: list[Mapping[str, Any]]) -> bool:
    products = [str(row.get("product") or "") for row in entitlements if str(row.get("status") or "") == "active"]
    return len(products) != len(set(products))


def _paid(subscription: str, entitlements: list[Mapping[str, Any]]) -> bool:
    if subscription in PAID_STATUSES:
        return True
    return any(
        str(row.get("status") or "") == "active" and str(row.get("source") or "") in PAID_SOURCES
        for row in entitlements
    )


def _mode(auth_id: str, legacy: Mapping[str, Any] | None, link: Mapping[str, Any] | None, paid: bool) -> str:
    if paid and auth_id:
        return "future_paid"
    if auth_id and link and legacy:
        return "migrated"
    if auth_id and not link and legacy is None:
        return "auth_only"
    if legacy is not None and not auth_id and link is None:
        return "legacy_only"
    if paid and legacy is not None and not auth_id:
        return "future_paid"
    return "malformed"


def _protected(
    user_id: str,
    auth_id: str,
    legacy: Mapping[str, Any] | None,
    link: Mapping[str, Any] | None,
) -> bool:
    ids = {user_id, auth_id}
    if legacy is not None:
        ids.add(str(legacy.get("user_id") or ""))
    if link is not None:
        ids.add(str(link.get("legacy_user_id") or ""))
        ids.add(str(link.get("auth_user_id") or ""))
    ids.discard("")
    return bool(ids & set(account_privacy.PROTECTED_IDS))


def _actions(mode: str, paid: bool, legacy: Mapping[str, Any] | None) -> dict[str, str]:
    entitlement = "RETAIN" if paid else "DELETE"
    legacy_action = "ANONYMIZE" if legacy is not None else "N/A"
    auth_action = "DELETE" if mode in {"auth_only", "migrated", "future_paid"} else "N/A"
    if mode == "legacy_only":
        auth_action = "N/A"
    return {
        "auth.users": auth_action,
        "auth.identities": auth_action,
        "profiles": "DELETE" if mode != "legacy_only" else "N/A",
        "legacy_auth_links": "DELETE" if mode == "migrated" else "N/A",
        "entitlements": entitlement if mode != "legacy_only" else "N/A",
        "public.users": legacy_action,
        "stripe_events": "RETAIN",
        "sessions": "DELETE" if auth_action == "DELETE" else "N/A",
        "subscription_reference": "DETACH" if paid else "N/A",
    }

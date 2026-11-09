"""Stripe test-mode rules. Nothing here calls Stripe or Supabase.

ENTITLEMENT_UPDATES_ENABLED stays false. A test passes True explicitly.
A signature failure or a disabled flag leaves the ledger unchanged.
Email in a payload never creates a user.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

ENTITLEMENT_UPDATES_ENABLED = False
SIGNATURE_TOLERANCE_SECONDS = 300
_USER_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
PLAN_PRICE = {
    "nordic": "price_test_nordic",
    "international": "price_test_international",
}
PRICE_PLAN = {price: plan for plan, price in PLAN_PRICE.items()}


@dataclass
class ApplyResult:
    accepted: bool
    changed: bool
    reason: str


def build_checkout(user_id: str, plan: str, *, enabled: bool) -> dict[str, Any] | None:
    """Server-built Checkout body. The browser does not choose the account."""
    if not enabled:
        return None
    if plan not in PLAN_PRICE or not _USER_ID.fullmatch(str(user_id or "")):
        raise ValueError("checkout")
    return {
        "mode": "subscription",
        "client_reference_id": user_id,
        "metadata": {"user_id": user_id, "plan_code": plan},
        "line_items": [{"price": PLAN_PRICE[plan], "quantity": 1}],
    }


def sign(raw: str, secret: str, timestamp: int) -> str:
    digest = hmac.new(
        secret.encode(),
        f"{timestamp}.{raw}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def apply_event(
    ledger: dict[str, Any],
    raw: str,
    header: str | None,
    secret: str,
    *,
    updates_enabled: bool = ENTITLEMENT_UPDATES_ENABLED,
    now: datetime,
) -> ApplyResult:
    before = _snapshot(ledger)
    if not _signature_ok(raw, header, secret, now):
        return _finish(ledger, before, ApplyResult(False, False, "bad_signature"))
    if not updates_enabled:
        from operations import log_event

        log_event("STRIPE_DISABLED_ATTEMPT")
        return _finish(ledger, before, ApplyResult(False, False, "updates_disabled"))
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return _finish(ledger, before, ApplyResult(False, False, "bad_json"))
    if not isinstance(event, dict):
        return _finish(ledger, before, ApplyResult(False, False, "bad_json"))
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id or not event_type:
        return _finish(ledger, before, ApplyResult(False, False, "bad_event"))
    events = ledger.setdefault("events", {})
    if event_id in events:
        return _finish(ledger, before, ApplyResult(True, False, "duplicate"))
    user_id = _user_id(event)
    if user_id is None or user_id not in ledger.get("users", {}):
        return _finish(ledger, before, ApplyResult(True, False, "unknown_user"))
    changed = _apply_known_user(ledger, event_type, event, user_id, now)
    if changed:
        events[event_id] = event_type
    return _finish(ledger, before, ApplyResult(True, changed, "applied" if changed else "ignored"))


def _apply_known_user(
    ledger: dict[str, Any],
    event_type: str,
    event: dict[str, Any],
    user_id: str,
    now: datetime,
) -> bool:
    obj = _object(event)
    entitlements = ledger.setdefault("entitlements", {})
    current = dict(entitlements.get(user_id) or {"plan": "free", "status": "active", "ends_at": None})
    if event_type == "checkout.session.completed":
        plan = _plan_code(obj)
        if plan is None:
            return False
        current = {"plan": plan, "status": "active", "ends_at": None}
    elif event_type == "customer.subscription.updated":
        status = str(obj.get("status") or "")
        if status == "past_due":
            current["status"] = "suspended"
            current["ends_at"] = None
        elif status in {"canceled", "cancelled"}:
            ends_at = _period_end(obj.get("current_period_end"))
            if ends_at is not None and ends_at > now:
                current["status"] = "active"
                current["ends_at"] = ends_at
            else:
                current["status"] = "expired"
                current["ends_at"] = ends_at or now
        else:
            return False
    else:
        return False
    entitlements[user_id] = current
    return True


def _signature_ok(raw: str, header: str | None, secret: str, now: datetime) -> bool:
    if not secret or not header:
        return False
    timestamp = ""
    signatures: list[str] = []
    for part in header.split(","):
        key, separator, value = part.partition("=")
        if separator != "=":
            continue
        if key.strip() == "t":
            timestamp = value.strip()
        elif key.strip() == "v1" and value.strip():
            signatures.append(value.strip())
    if not timestamp or not signatures:
        return False
    try:
        stamp = int(timestamp)
    except ValueError:
        return False
    if abs(int(now.timestamp()) - stamp) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.{raw}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return any(hmac.compare_digest(item, expected) for item in signatures)


def _user_id(event: dict[str, Any]) -> str | None:
    obj = _object(event)
    reference = obj.get("client_reference_id")
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    candidate = reference if isinstance(reference, str) and reference else metadata.get("user_id")
    if not isinstance(candidate, str) or not _USER_ID.fullmatch(candidate):
        return None
    return candidate


def _plan_code(obj: dict[str, Any]) -> str | None:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    plan = metadata.get("plan_code")
    if plan in PLAN_PRICE:
        return str(plan)
    price = metadata.get("price")
    if isinstance(price, str) and price in PRICE_PLAN:
        return PRICE_PLAN[price]
    return None


def _period_end(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _object(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    return obj if isinstance(obj, dict) else {}


def _snapshot(ledger: dict[str, Any]) -> str:
    return json.dumps(ledger, default=_encode, sort_keys=True)


def _encode(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _finish(ledger: dict[str, Any], before: str, result: ApplyResult) -> ApplyResult:
    if _snapshot(ledger) != before and not result.changed:
        raise RuntimeError("ledger changed without a recorded change")
    if not result.changed and _snapshot(ledger) != before:
        raise RuntimeError("rejected event changed the ledger")
    return result

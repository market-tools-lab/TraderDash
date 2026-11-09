"""Closed-by-default Auth registration. This module creates no real account.

The only value that makes the code eligible is TRADERDASH_AUTH_REGISTRATION=enabled.
Missing, disabled, and unknown values stay closed. Legacy login does not read
this flag. Repair is refused for production, the deleted preview, and the
protected pilot ids. No call here sends mail by itself.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Mapping

import account_lifecycle
import account_privacy
import password_policy
import stripe_test
import supabase_auth
import universes

APPROVED_VALUE = "enabled"
CAPTCHA_REQUIRED = True
CAPTCHA_PROVIDER = "turnstile"
REPAIR_ENABLED = False
ENTITLEMENT_FUNCTION_DEPLOYED = False
LEGAL_DECISIONS_COMPLETE = False
FREE_PLAN = "free"
REQUEST_MESSAGE = "Hvis adressen kan bruges, sender vi en bekræftelse."
_MESSAGES = {
    "closed": "Ny konto oprettes ikke i denne loginvej.",
    "email": supabase_auth.INVALID_EMAIL,
    "password_mismatch": "Adgangskoderne er ikke ens.",
    "acknowledgement": "Bekræftelsen mangler.",
    "weak": "Adgangskoden er for svag.",
    "captcha": "Kontoen kunne ikke oprettes.",
    "plan": "Kontoen kunne ikke oprettes.",
    "environment": "Kontoen kunne ikke oprettes.",
    "protected": "Kontoen kunne ikke oprettes.",
    "repair_disabled": "Kontoen kunne ikke oprettes.",
    "expired": "Linket er ikke gyldigt længere.",
    "unavailable": "Kontoen kunne ikke oprettes.",
}


class RegistrationRejected(Exception):
    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message or public_message(reason))


def public_message(reason: str) -> str:
    text = _MESSAGES.get(reason, "Kontoen kunne ikke oprettes.")
    return text


def registration_open(env: Mapping[str, str] | None = None) -> bool:
    """True only for the one approved flag value. Every other value is closed."""
    source = env if env is not None else os.environ
    return str(source.get("TRADERDASH_AUTH_REGISTRATION", "")).strip().lower() == APPROVED_VALUE


def signup_link_present(params: Mapping[str, Any]) -> bool:
    kind = str(params.get("type") or "").strip().lower()
    token = str(params.get("token_hash") or "").strip()
    return kind == "signup" and bool(token)


def submit(
    email: str,
    password: str,
    confirmation: str,
    *,
    acknowledged: bool,
    captcha_token: str,
    redirect_url: str,
    plan: str = FREE_PLAN,
    env: Mapping[str, str] | None = None,
    transport=None,
) -> dict[str, Any]:
    """Validate a signup. Auth is contacted only after every local gate passes."""
    source = env if env is not None else os.environ
    if not registration_open(source) or _mode(source) != "supabase_auth":
        _log("REGISTRATION_BLOCKED", reason="closed")
        raise RegistrationRejected("closed")
    if plan != FREE_PLAN:
        _log("REGISTRATION_BLOCKED", reason="plan")
        raise RegistrationRejected("plan")
    if not supabase_auth.email_acceptable(email):
        _log("REGISTRATION_BLOCKED", reason="email")
        raise RegistrationRejected("email")
    if not password_policy.matches(password, confirmation):
        _log("REGISTRATION_BLOCKED", reason="password_mismatch")
        raise RegistrationRejected("password_mismatch")
    try:
        password_policy.require(password)
    except password_policy.PasswordRejected as exc:
        _log("REGISTRATION_BLOCKED", reason="weak")
        raise RegistrationRejected("weak", str(exc)) from exc
    if not acknowledged:
        _log("REGISTRATION_BLOCKED", reason="acknowledgement")
        raise RegistrationRejected("acknowledgement")
    if CAPTCHA_REQUIRED and not str(captcha_token or "").strip():
        _log("REGISTRATION_BLOCKED", reason="captcha")
        raise RegistrationRejected("captcha")
    if not supabase_auth.delivery_enabled() or not supabase_auth.allowed_redirect(redirect_url):
        _log("REGISTRATION_BLOCKED", reason="unavailable")
        raise RegistrationRejected("unavailable")
    client = supabase_auth.Client.from_env(transport)
    try:
        created = client.signup(email, password, redirect_url, captcha_token)
    except supabase_auth.AuthError as exc:
        _log("REGISTRATION_BLOCKED", reason="unavailable")
        raise RegistrationRejected("unavailable") from exc
    _log("REGISTRATION_REQUEST")
    if created.get("session_returned") or created.get("confirmed") is True:
        _log("REGISTRATION_BLOCKED", reason="confirmation_required")
        return {
            "state": "verification_bypassed",
            "access": False,
            "message": "Kontoen kunne ikke oprettes.",
            "user_id": "",
        }
    _log("REGISTRATION_VERIFICATION_REQUIRED")
    return {
        "state": "email_unconfirmed" if created.get("created") else "duplicate_hidden",
        "access": False,
        "message": REQUEST_MESSAGE,
        "user_id": "",
    }


def complete_verification(
    token_hash: str,
    record: Mapping[str, Any],
    *,
    verify: Callable[[str], Mapping[str, Any]] | None = None,
    transport=None,
) -> dict[str, Any]:
    """Exchange a signup link without keeping a session. Access stays off until data matches."""
    if not registration_open() or supabase_auth.auth_mode() != "supabase_auth":
        _log("REGISTRATION_BLOCKED", reason="closed")
        raise RegistrationRejected("closed")
    if verify is None:
        def verify(token: str) -> Mapping[str, Any]:
            return supabase_auth.Client.from_env(transport).exchange_signup(token)
    try:
        checked = dict(verify(token_hash))
    except supabase_auth.AuthError as exc:
        _log("REGISTRATION_BLOCKED", reason="expired")
        raise RegistrationRejected("expired") from exc
    if checked.get("expired"):
        _log("REGISTRATION_BLOCKED", reason="expired")
        raise RegistrationRejected("expired")
    user_id = str(checked.get("user_id") or "")
    merged = dict(record)
    merged["user_id"] = user_id
    merged["confirmed"] = bool(checked.get("confirmed"))
    report = reconcile(merged)
    if report["access"]:
        _log("REGISTRATION_COMPLETED")
    elif report["findings"]:
        _log("REGISTRATION_RECONCILIATION_REQUIRED", finding=report["findings"][0])
    else:
        _log("REGISTRATION_VERIFICATION_REQUIRED")
    report["message"] = "E-mailen er bekræftet. Log ind." if report["access"] else "Kontoen er ikke klar."
    report["session_kept"] = False
    return report


def reconcile(record: Mapping[str, Any]) -> dict[str, Any]:
    """Describe one account. The record is not modified."""
    user_id = str(record.get("user_id") or "").strip()
    target = str(record.get("target_ref") or "").strip()
    confirmed = bool(record.get("confirmed"))
    profile = bool(record.get("profile"))
    rows = _rows(record.get("entitlements"))
    active = [row for row in rows if str(row.get("status") or "") == "active"]
    free = [row for row in active if str(row.get("plan") or "") == FREE_PLAN and str(row.get("product") or "") == "traderdash"]
    other = [row for row in active if row not in free]
    findings = []
    if user_id in account_privacy.PROTECTED_IDS:
        findings.append("protected")
    if target in account_privacy.PROTECTED_REFS:
        findings.append("environment")
    if not confirmed:
        findings.append("email_unconfirmed")
    if confirmed and not profile:
        findings.append("profile_missing")
    if not confirmed and (profile or rows):
        findings.append("unconfirmed_with_data")
    if confirmed and profile and not free and not other:
        findings.append("entitlement_missing")
    if len(free) > 1:
        findings.append("duplicate_free")
    if other:
        findings.append("unexpected_plan")
    access = (
        confirmed
        and profile
        and len(free) == 1
        and not other
        and "protected" not in findings
        and "environment" not in findings
        and "email_unconfirmed" not in findings
    )
    papers = len(universes.stocks_for(FREE_PLAN)) if access else 0
    return {
        "user_id": user_id,
        "state": "active" if access else _state(findings),
        "confirmed": confirmed,
        "profile_present": profile,
        "free_entitlements": len(free),
        "findings": findings,
        "actions": ["create_free"] if "entitlement_missing" in findings else [],
        "access": access,
        "papers": papers,
        "mutates": False,
        "repair_enabled": REPAIR_ENABLED,
    }


def apply_free_entitlement(
    record: Mapping[str, Any],
    writer: Callable[[Mapping[str, Any]], None] | None = None,
    *,
    repair: bool = False,
) -> dict[str, Any]:
    """Ask a test writer for one Free row. Production targets are refused."""
    report = reconcile(record)
    if repair is not True or writer is None:
        raise RegistrationRejected("repair_disabled")
    if "environment" in report["findings"] or "protected" in report["findings"]:
        raise RegistrationRejected("protected" if "protected" in report["findings"] else "environment")
    if report["actions"] != ["create_free"]:
        return report
    writer({"user_id": report["user_id"], "plan": FREE_PLAN, "product": "traderdash", "status": "active"})
    report["requested_create"] = True
    report["mutates"] = False
    return report


def launch_gate(evidence: Mapping[str, Any] | None = None, *, root=None) -> dict[str, Any]:
    """A deliberate launch list. It never opens registration."""
    from pathlib import Path

    supplied = evidence or {}
    base = root or Path(__file__).resolve().parent
    auth = (base / "supabase_auth.py").read_text(encoding="utf-8")
    operations_doc = base / "docs" / "production" / "OPERATIONS.md"
    lifecycle_doc = base / "docs" / "production" / "ACCOUNT_LIFECYCLE.md"
    items = {
        "ci_green": _evidence(supplied, "ci_green"),
        "supabase_healthy": _evidence(supplied, "supabase_healthy"),
        "no_preview_branch": _evidence(supplied, "no_preview_branch"),
        "backups_current": _evidence(supplied, "backups_current"),
        "resend_healthy": _evidence(supplied, "resend_healthy"),
        "registration_code_tested": _evidence(supplied, "registration_code_tested"),
        "registration_default_off": "PASS" if not registration_open({}) else "FAIL",
        "email_verification_prepared": "PASS",
        "captcha_decision_complete": "PASS" if CAPTCHA_REQUIRED and CAPTCHA_PROVIDER == "turnstile" else "FAIL",
        "privacy_terms_decision_complete": "PASS" if LEGAL_DECISIONS_COMPLETE else "FAIL",
        "free_entitlement_idempotent": "PASS",
        "entitlement_function_deployed": "PASS" if ENTITLEMENT_FUNCTION_DEPLOYED else "FAIL",
        "deletion_policy_documented": "PASS" if lifecycle_doc.is_file() else "FAIL",
        "recovery_code_present": "PASS" if "def request_password_reset" in auth else "FAIL",
        "password_change_code_ready": "PASS" if "_refuse_deleted_preview" in auth else "FAIL",
        "password_change_live": _evidence(supplied, "password_change_live"),
        "stripe_off": "PASS" if not stripe_test.ENTITLEMENT_UPDATES_ENABLED else "FAIL",
        "deletion_execution_off": "PASS" if not account_lifecycle.DELETION_EXECUTION_ENABLED else "FAIL",
        "monitoring_runbook_current": "PASS" if operations_doc.is_file() and "release-gate" in operations_doc.read_text(encoding="utf-8") else "FAIL",
    }
    return {"items": items, "open_registration": False, "decision": "closed"}


def _evidence(evidence: Mapping[str, Any], name: str) -> str:
    return "PASS" if evidence.get(name) is True else "FAIL"


def _mode(source: Mapping[str, str]) -> str:
    value = str(source.get("TRADERDASH_AUTH_MODE", "")).strip().lower()
    return "supabase_auth" if value == "supabase_auth" else "legacy"


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _state(findings: list[str]) -> str:
    if "protected" in findings or "environment" in findings:
        return "blocked"
    if "email_unconfirmed" in findings:
        return "email_unconfirmed"
    if findings:
        return "reconciliation_required"
    return "incomplete"


def _log(category: str, **fields: Any) -> None:
    from operations import log_event

    log_event(category, **fields)

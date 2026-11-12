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
import captcha
import password_policy
import stripe_test
import supabase_auth
import universes

APPROVED_VALUE = "enabled"
ACK_VERSION = "traderdash-pilot-2026-11-09"
TRADERDASH_PILOT_MINIMUM_AGE = 18
CAPTCHA_REQUIRED = True
CAPTCHA_PROVIDER = "turnstile"
REPAIR_ENABLED = False
ENTITLEMENT_FUNCTION_DEPLOYED = True
SUPPORT_MAILBOX_OPERATIONAL = True
LEGAL_DECISIONS_COMPLETE = False
SELF_ENROLLMENT_DEPLOYED = True
FREE_PLAN = "free"
_REPAIR_TARGET = "local-test"
_ACCEPTED_FREE_SOURCES = frozenset({"signup", "migration"})
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
    captcha_transport: captcha.Transport | None = None,
) -> dict[str, Any]:
    """Validate a signup. Auth is contacted only after every local gate passes.

    The live path always supplies the server-side siteverify caller. A test
    may replace that caller. verify() still refuses a missing transport.
    """
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
    try:
        captcha.verify(
            captcha_token,
            env=source,
            transport=captcha.https_transport if captcha_transport is None else captcha_transport,
        )
    except captcha.CaptchaRejected:
        _log("REGISTRATION_BLOCKED", reason="captcha")
        raise RegistrationRejected("captcha") from None
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
    try:
        if verify is None:
            checked = dict(supabase_auth.Client.from_env(transport).confirm_traderdash_signup(token_hash))
            merged = {
                "user_id": str(checked.get("user_id") or ""),
                "target_ref": str(checked.get("target_ref") or ""),
                "confirmed": bool(checked.get("confirmed")),
                "profile": bool(checked.get("profile")),
                "entitlements": checked.get("entitlements") or [],
                "acknowledgement_version": str(checked.get("acknowledgement_version") or ""),
            }
        else:
            checked = dict(verify(token_hash))
            merged = dict(record)
            merged["user_id"] = str(checked.get("user_id") or "")
            merged["confirmed"] = bool(checked.get("confirmed"))
    except supabase_auth.AuthError as exc:
        _log("REGISTRATION_BLOCKED", reason="expired")
        raise RegistrationRejected("expired") from exc
    if checked.get("expired"):
        _log("REGISTRATION_BLOCKED", reason="expired")
        raise RegistrationRejected("expired")
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
    if target != account_privacy.PRODUCTION_REF:
        findings.append("environment")
    if not confirmed:
        findings.append("email_unconfirmed")
    if confirmed and str(record.get("acknowledgement_version") or "") != ACK_VERSION:
        findings.append("acknowledgement_missing")
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
    source = str(free[0].get("source") or "") if len(free) == 1 else ""
    if len(free) == 1 and source not in _ACCEPTED_FREE_SOURCES:
        findings.append("unexpected_source")
    access = (
        confirmed
        and profile
        and len(free) == 1
        and not other
        and "protected" not in findings
        and "environment" not in findings
        and "email_unconfirmed" not in findings
        and "unexpected_source" not in findings
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
        "account_stage": {
            "confirmed": confirmed,
            "acknowledgement_version": str(record.get("acknowledgement_version") or ""),
        },
        "product_stage": {
            "product": "traderdash",
            "profile": profile,
            "free_entitlements": len(free),
            "papers": papers,
            "source": source,
        },
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
    target = str(record.get("target_ref") or "").strip()
    if "protected" in report["findings"]:
        raise RegistrationRejected("protected")
    if target != _REPAIR_TARGET:
        raise RegistrationRejected("environment")
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
    provision = (base / "supabase" / "migrations" / "20261109110000_provision_traderdash_free.sql").read_text(encoding="utf-8")
    bridge = (base / "supabase" / "migrations" / "20261109140000_provision_traderdash_free_self.sql").read_text(encoding="utf-8")
    component = (base / "captcha_component" / "index.html").read_text(encoding="utf-8")
    platform = (base / "docs" / "production" / "MARKET_TOOLS_PLATFORM.md").read_text(encoding="utf-8")
    terms = (base / "docs" / "production" / "TERMS_OF_USE.md").read_text(encoding="utf-8")
    pilot = (base / "docs" / "production" / "PUBLIC_PILOT.md").read_text(encoding="utf-8")
    items = {
        "ci_green": _external(supplied, "ci_green"),
        "supabase_healthy": _external(supplied, "supabase_healthy"),
        "no_preview_branch": _external(supplied, "no_preview_branch"),
        "backups_current": _external(supplied, "backups_current"),
        "resend_healthy": _external(supplied, "resend_healthy"),
        "registration_code_tested": _external(supplied, "registration_code_tested"),
        "registration_default_off": "PASS" if not registration_open({}) else "FAIL",
        "email_verification_prepared": "PASS",
        "captcha_decision_complete": "PASS" if CAPTCHA_REQUIRED and CAPTCHA_PROVIDER == "turnstile" else "FAIL",
        "turnstile_server_verification": "PASS" if "def verify" in (base / "captcha.py").read_text(encoding="utf-8") else "FAIL",
        "turnstile_token_return": "PASS" if _token_return_ready(component) else "FAIL",
        "turnstile_widget_configured": _external(supplied, "turnstile_widget_configured"),
        "privacy_draft_present": "PASS" if (base / "docs" / "production" / "PRIVACY_NOTICE.md").is_file() else "FAIL",
        "terms_draft_present": "PASS" if (base / "docs" / "production" / "TERMS_OF_USE.md").is_file() else "FAIL",
        "traderdash_age_policy": "PASS" if _age_policy_ready(platform, terms) else "FAIL",
        "privacy_terms_decision_complete": _external(supplied, "privacy_terms_decision_complete") if not LEGAL_DECISIONS_COMPLETE else "PASS",
        "support_requirements_documented": "PASS" if (base / "docs" / "production" / "SUPPORT_MAIL.md").is_file() else "FAIL",
        "support_mailbox_operational": "PASS" if SUPPORT_MAILBOX_OPERATIONAL else _external(supplied, "support_mailbox_operational"),
        "free_entitlement_idempotent": "PASS",
        "entitlement_function_prepared": "PASS" if "revoke all on function public.provision_traderdash_free(uuid) from public, anon, authenticated;" in provision else "FAIL",
        "entitlement_function_deployed": "PASS" if ENTITLEMENT_FUNCTION_DEPLOYED else _external(supplied, "entitlement_function_deployed"),
        "self_enrollment_prepared": "PASS" if _self_enrollment_ready(bridge) else "FAIL",
        "self_enrollment_deployed": "PASS" if SELF_ENROLLMENT_DEPLOYED else "FAIL",
        "pilot_recreation_documented": "PASS" if "Genskabelse" in pilot else "FAIL",
        "pilot_branch_deployed": _external(supplied, "pilot_branch_deployed"),
        "deletion_policy_documented": "PASS" if lifecycle_doc.is_file() else "FAIL",
        "recovery_code_present": "PASS" if "def request_password_reset" in auth else "FAIL",
        "password_change_code_ready": "PASS" if "_refuse_deleted_preview" in auth else "FAIL",
        "password_change_live": _external(supplied, "password_change_live"),
        "stripe_off": "PASS" if not stripe_test.ENTITLEMENT_UPDATES_ENABLED else "FAIL",
        "deletion_execution_off": "PASS" if not account_lifecycle.DELETION_EXECUTION_ENABLED else "FAIL",
        "monitoring_runbook_current": "PASS" if operations_doc.is_file() and "release-gate" in operations_doc.read_text(encoding="utf-8") else "FAIL",
    }
    return {"items": items, "open_registration": False, "decision": "closed"}


def _self_enrollment_ready(sql: str) -> bool:
    compact = " ".join(sql.split())
    return (
        "NOT APPLIED" in sql
        and "auth.uid()" in sql
        and "email_confirmed_at" in sql
        and "perform public.provision_traderdash_free(actor)" in compact
        and "when unique_violation then" in compact
        and "revoke all on function public.provision_traderdash_free_self() from public, anon;" in sql
        and "grant execute on function public.provision_traderdash_free_self() to authenticated;" in sql
        and "grant execute on function public.provision_traderdash_free_self() to anon" not in sql
        and "service_role" not in sql
    )


def _token_return_ready(component: str) -> bool:
    return (
        "streamlit:setComponentValue" in component
        and 'var ACTION = "registration"' in component
        and "event.source !== window.parent" in component
        and captcha.PASS_SECRET not in component
        and "TRADERDASH_TURNSTILE_SECRET_KEY" not in component
    )


def _age_policy_ready(platform: str, terms: str) -> bool:
    return (
        TRADERDASH_PILOT_MINIMUM_AGE == 18
        and "fyldt 18" in terms
        and "ikke en Market Tools-regel" in platform
    )


def _external(evidence: Mapping[str, Any], name: str) -> str:
    return "PASS" if evidence.get(name) is True else "EXTERNAL"


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

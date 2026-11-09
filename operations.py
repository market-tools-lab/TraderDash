"""Local health and release checks. Nothing here contacts Production.

Streamlit Community Cloud has no separate health route. A future container
can run ``python -m operations``. The report contains modes and booleans,
never passwords, tokens, connection strings, or key values.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Mapping, Sequence

import account_lifecycle
import stripe_test
import supabase_auth

CATEGORIES = frozenset(
    {
        "APP_START",
        "CONFIG_ERROR",
        "AUTH_FAILURE",
        "AUTH_RECOVERY_REQUEST",
        "DATABASE_FAILURE",
        "ENTITLEMENT_FAILURE",
        "STRIPE_DISABLED_ATTEMPT",
        "ACCOUNT_LIFECYCLE_BLOCKED",
        "REGISTRATION_REQUEST",
        "REGISTRATION_BLOCKED",
        "REGISTRATION_VERIFICATION_REQUIRED",
        "REGISTRATION_COMPLETED",
        "REGISTRATION_RECONCILIATION_REQUIRED",
        "UNHANDLED_APPLICATION_ERROR",
    }
)
EXPECTED_MIGRATIONS = (
    "20261030160000",
    "20261104143544",
    "20261104143902",
)
REGISTRATION_OPEN = False
_TRUTHY = frozenset({"1", "true", "on", "open", "enabled", "live"})
_SECRET_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "anon_key",
        "secret",
        "database_url",
        "token_hash",
        "service_role",
    }
)
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_JWT = re.compile(r"eyJ\S+")
_URL = re.compile(r"[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_CORRELATION: ContextVar[str] = ContextVar("traderdash_correlation", default="")

DEPENDENCIES = (
    {"name": "github_ci", "class": "AUTOMATIC", "mutates": False},
    {"name": "release_flags", "class": "AUTOMATIC", "mutates": False},
    {"name": "supabase_database", "class": "MANUAL", "mutates": False},
    {"name": "supabase_auth", "class": "MANUAL", "mutates": False},
    {"name": "resend", "class": "MANUAL", "mutates": False},
    {"name": "streamlit_legacy", "class": "MANUAL", "mutates": False},
    {"name": "streamlit_pilot", "class": "MANUAL", "mutates": False},
    {"name": "backups", "class": "MANUAL", "mutates": False},
    {"name": "migration_versions", "class": "MANUAL", "mutates": False},
    {"name": "recovery_mail", "class": "INCIDENT-ONLY", "mutates": False},
    {"name": "preview_branch", "class": "INCIDENT-ONLY", "mutates": False},
    {"name": "restore", "class": "INCIDENT-ONLY", "mutates": False},
)


def correlation_id() -> str:
    """A process-local id. It is not derived from a person."""
    current = _CORRELATION.get()
    if current:
        return current
    current = uuid.uuid4().hex[:12]
    _CORRELATION.set(current)
    return current


def redact(value: Any) -> Any:
    """Remove secret-shaped text. Mappings keep their keys."""
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            name = str(key).lower()
            cleaned[str(key)] = "[redacted]" if name in _SECRET_KEYS else redact(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    text = _EMAIL.sub("[email]", str(value))
    text = _JWT.sub("[token]", text)
    text = _URL.sub("[url]", text)
    return text


def log_event(category: str, *, _stream=None, **fields: Any) -> dict[str, Any]:
    """Write one redacted JSON line. Unknown categories become unhandled."""
    if category not in CATEGORIES:
        category = "UNHANDLED_APPLICATION_ERROR"
        fields = {"where": "unknown"}
    payload = {
        "category": category,
        "correlation_id": correlation_id(),
        **redact(fields),
    }
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if _secret_text(line):
        payload = {
            "category": "UNHANDLED_APPLICATION_ERROR",
            "correlation_id": correlation_id(),
            "redacted": True,
        }
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    (_stream or sys.stderr).write(line + "\n")
    return payload


def liveness() -> dict[str, str]:
    """The process can import this module and answer."""
    return {"kind": "liveness", "status": "ok"}


def assess(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Readiness from code flags and name presence. Values are not copied."""
    source = env if env is not None else os_environ()
    blockers = _blockers(source)
    mode = _mode(source)
    if mode == "supabase_auth" and not (_present(source, "TRADERDASH_SUPABASE_URL") and _present(source, "TRADERDASH_SUPABASE_ANON_KEY")):
        blockers.append("missing_configuration")
    report = {
        "liveness": "ok",
        "readiness": "ready" if not blockers else "not_ready",
        "auth_mode": mode,
        "blockers": blockers,
        "flags": {
            "registration_open": REGISTRATION_OPEN,
            "stripe_updates": stripe_test.ENTITLEMENT_UPDATES_ENABLED,
            "deletion_ui": account_lifecycle.DELETION_UI_ENABLED,
            "deletion_execution": account_lifecycle.DELETION_EXECUTION_ENABLED,
        },
        "dependencies": [dict(item) for item in DEPENDENCIES],
        "contacts_production": False,
    }
    if _secret_text(json.dumps(report)):
        return {
            "liveness": "ok",
            "readiness": "not_ready",
            "auth_mode": mode,
            "blockers": ["report_redacted"],
            "contacts_production": False,
        }
    return report


def migration_status(applied: Sequence[str] | None) -> dict[str, Any]:
    """Compare a supplied version list. None means the check was not run."""
    if applied is None:
        return {"status": "not_checked", "mutates": False}
    found = [str(item) for item in applied]
    if any(_secret_text(item) for item in found):
        return {"status": "rejected", "mutates": False}
    return {
        "status": "ok" if tuple(found) == EXPECTED_MIGRATIONS else "drift",
        "expected_count": len(EXPECTED_MIGRATIONS),
        "observed_count": len(found),
        "mutates": False,
    }


def release_validation(root: Path | None = None) -> dict[str, Any]:
    """Static release checks. They do not open a network connection."""
    base = root or Path(__file__).resolve().parent
    findings = []
    app = _read(base, "app.py")
    workflow = _read(base, ".github/workflows/release-gate.yml")
    config = _read(base, ".streamlit/config.toml")
    webhook = _read(base, "supabase/functions/stripe-webhook/index.ts")
    auth = _read(base, "supabase_auth.py")
    docker = _read(base, "Dockerfile")
    if "Ny konto oprettes ikke i denne loginvej." not in app or REGISTRATION_OPEN:
        findings.append("registration")
    if "Slet konto" in app or account_lifecycle.DELETION_UI_ENABLED:
        findings.append("deletion_ui")
    if account_lifecycle.DELETION_EXECUTION_ENABLED:
        findings.append("deletion_execution")
    if stripe_test.ENTITLEMENT_UPDATES_ENABLED or "const ENTITLEMENT_UPDATES_ENABLED = false;" not in webhook:
        findings.append("stripe")
    if 'showErrorDetails = "none"' not in config:
        findings.append("error_details")
    if not _push_includes_master(workflow):
        findings.append("ci_master")
    if "cancel-in-progress:" not in workflow:
        findings.append("concurrency")
    if "secrets." in workflow:
        findings.append("workflow_secrets")
    if "_refuse_deleted_preview" not in auth:
        findings.append("preview_guard")
    if 'CMD ["python", "-m", "operations"]' not in docker:
        findings.append("container_health")
    if "service_role" in docker or "eyJ" in docker:
        findings.append("container_secret")
    return {"ok": not findings, "findings": findings, "contacts_production": False}


def os_environ() -> Mapping[str, str]:
    import os

    return os.environ


def _mode(source: Mapping[str, str]) -> str:
    value = str(source.get("TRADERDASH_AUTH_MODE", "")).strip().lower()
    if value == "supabase_auth":
        return "supabase_auth"
    return "legacy"


def _present(source: Mapping[str, str], name: str) -> bool:
    return bool(str(source.get(name, "")).strip())


def _blockers(source: Mapping[str, str]) -> list[str]:
    blockers = []
    raw = str(source.get("TRADERDASH_AUTH_MODE", "")).strip().lower()
    if raw not in {"", "legacy", "supabase_auth"}:
        blockers.append("auth_mode")
    url = str(source.get("TRADERDASH_SUPABASE_URL", "")).strip().lower()
    if supabase_auth.PREVIEW_ORIGIN.removeprefix("https://").split(".")[0] in url:
        blockers.append("deleted_preview")
    if str(source.get("TRADERDASH_REGISTRATION", "")).strip().lower() in _TRUTHY:
        blockers.append("registration_switch")
    if str(source.get("TRADERDASH_STRIPE", "")).strip().lower() in _TRUTHY:
        blockers.append("stripe_switch")
    registration_flag = str(source.get("TRADERDASH_AUTH_REGISTRATION", "")).strip().lower()
    if registration_flag == "enabled":
        blockers.append("registration_enabled")
    elif registration_flag not in {"", "disabled"}:
        blockers.append("registration_flag")
    if stripe_test.ENTITLEMENT_UPDATES_ENABLED:
        blockers.append("stripe_code")
    if account_lifecycle.DELETION_UI_ENABLED:
        blockers.append("deletion_ui")
    if account_lifecycle.DELETION_EXECUTION_ENABLED:
        blockers.append("deletion_execution")
    return blockers


def _push_includes_master(workflow: str) -> bool:
    parts = workflow.split("push:", 1)
    if len(parts) != 2:
        return False
    return "\n      - master\n" in parts[1]


def _read(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def _secret_text(value: str) -> bool:
    text = str(value)
    lowered = text.lower()
    return bool(_JWT.search(text) or _URL.search(text) or "service_role" in lowered or "password=" in lowered)


def main() -> int:
    log_event("APP_START")
    report = assess()
    sys.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")
    return 0 if report["readiness"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())

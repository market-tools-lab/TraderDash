"""Registration CAPTCHA. Login and password recovery do not use this module.

Cloudflare Turnstile is the selected provider. The secret stays on the
server. A client token is not enough. Production rejects the documented
test secrets. Tests never call challenges.cloudflare.com.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
ACTION = "registration"
PASS_SECRET = "1x0000000000000000000000000000000AA"
FAIL_SECRET = "2x0000000000000000000000000000000AA"
SPENT_SECRET = "3x0000000000000000000000000000000AA"
PASS_SITE_KEY = "1x00000000000000000000AA"
_TEST_SECRETS = frozenset({PASS_SECRET, FAIL_SECRET, SPENT_SECRET})
_SITE_KEY = re.compile(r"^[0-9A-Za-z_-]{10,80}$")
_TOKEN = re.compile(r"^[A-Za-z0-9._-]{20,2048}$")
_SEEN: set[str] = set()
_COMPONENT = None
Transport = Callable[[str, Mapping[str, str]], Mapping[str, Any]]
Widget = Callable[[str, str], Any]


class CaptchaRejected(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("Kontoen kunne ikke oprettes.")


def reset_seen() -> None:
    _SEEN.clear()


def site_key(env: Mapping[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    return str(source.get("TRADERDASH_TURNSTILE_SITE_KEY", "")).strip()


def site_key_allowed(candidate: str, env: Mapping[str, str] | None = None) -> bool:
    """A public site key may be shown. A secret or a production test key may not."""
    source = env if env is not None else os.environ
    key = str(candidate or "").strip()
    if key in _TEST_SECRETS or not _SITE_KEY.fullmatch(key):
        return False
    production = str(source.get("TRADERDASH_ENV", "")).strip().lower() == "production"
    mode = str(source.get("TRADERDASH_TURNSTILE_MODE", "")).strip().lower()
    if key == PASS_SITE_KEY and (production or mode == "live"):
        return False
    return True


def _mount(sitekey: str, action: str) -> Any:
    """Isolated Streamlit component. It receives the site key and returns a token."""
    global _COMPONENT
    if action != ACTION:
        return ""
    if _COMPONENT is None:
        import streamlit.components.v1 as components

        _COMPONENT = components.declare_component(
            "traderdash_turnstile",
            path=str(Path(__file__).resolve().parent / "captcha_component"),
        )
    return _COMPONENT(sitekey=sitekey, action=ACTION, default="", key="traderdash_turnstile_registration")


def render_widget(
    candidate: str,
    *,
    env: Mapping[str, str] | None = None,
    component: Widget | None = None,
) -> str | None:
    """Return the token. None means the widget cannot be shown."""
    key = str(candidate or "").strip()
    if not site_key_allowed(key, env):
        return None
    runner = component or _mount
    value = runner(key, ACTION)
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        return ""
    return value


def verify(
    token: str,
    *,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
) -> None:
    """Fail closed. The token is not returned and is not logged here."""
    source = env if env is not None else os.environ
    secret = str(source.get("TRADERDASH_TURNSTILE_SECRET_KEY", "")).strip()
    mode = str(source.get("TRADERDASH_TURNSTILE_MODE", "")).strip().lower()
    required = str(source.get("TRADERDASH_TURNSTILE", "")).strip().lower() == "required"
    hostname = str(source.get("TRADERDASH_TURNSTILE_HOSTNAME", "")).strip().lower()
    production = str(source.get("TRADERDASH_ENV", "")).strip().lower() == "production"
    if not required or not secret or not hostname:
        raise CaptchaRejected("missing_configuration")
    if secret in _TEST_SECRETS and (production or mode != "test"):
        raise CaptchaRejected("test_key_refused")
    presented = str(token or "").strip()
    if not presented or presented in _SEEN:
        raise CaptchaRejected("token")
    if secret == FAIL_SECRET:
        raise CaptchaRejected("invalid")
    if secret == SPENT_SECRET:
        raise CaptchaRejected("reused")
    if secret == PASS_SECRET:
        _SEEN.add(presented)
        return
    if transport is None:
        raise CaptchaRejected("unavailable")
    try:
        body = transport(
            SITEVERIFY_URL,
            {"secret": secret, "response": presented},
        )
    except (OSError, TimeoutError):
        raise CaptchaRejected("timeout") from None
    if not isinstance(body, Mapping) or body.get("success") is not True:
        errors = body.get("error-codes") if isinstance(body, Mapping) else None
        if isinstance(errors, list) and "timeout-or-duplicate" in errors:
            raise CaptchaRejected("reused")
        raise CaptchaRejected("invalid")
    response_host = str(body.get("hostname") or "").strip().lower()
    response_action = str(body.get("action") or "").strip().lower()
    if response_host != hostname or urlsplit("https://" + response_host).hostname != hostname:
        raise CaptchaRejected("hostname")
    if response_action != ACTION:
        raise CaptchaRejected("action")
    _SEEN.add(presented)


def https_transport(url: str, payload: Mapping[str, str]) -> Mapping[str, Any]:
    """POST a siteverify body with the server-side HTTPS caller.

    A network or provider failure raises TimeoutError. verify() turns that
    into a closed result. This function does not log the secret or the token.
    """
    import json
    import urllib.error
    import urllib.request

    body = {
        "secret": str(payload.get("secret") or ""),
        "response": str(payload.get("response") or ""),
    }
    request = urllib.request.Request(
        str(url),
        data=json.dumps(body).encode(),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TimeoutError("siteverify unreachable") from None
    try:
        parsed = json.loads(raw.decode()) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OSError("siteverify unreadable") from None
    if not isinstance(parsed, Mapping):
        raise OSError("siteverify unreadable")
    return parsed

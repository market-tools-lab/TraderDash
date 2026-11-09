"""Registration CAPTCHA. Login and password recovery do not use this module.

Cloudflare Turnstile is the selected provider. The secret stays on the
server. A client token is not enough. Production rejects the documented
test secrets. Tests never call challenges.cloudflare.com.
"""

from __future__ import annotations

import os
import re
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
_SEEN: set[str] = set()
Transport = Callable[[str, Mapping[str, str]], Mapping[str, Any]]


class CaptchaRejected(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("Kontoen kunne ikke oprettes.")


def reset_seen() -> None:
    _SEEN.clear()


def site_key(env: Mapping[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    return str(source.get("TRADERDASH_TURNSTILE_SITE_KEY", "")).strip()


def widget_markup(candidate: str) -> str:
    """Official widget markup. A secret or an unsafe site key produces nothing."""
    key = str(candidate or "").strip()
    if key in _TEST_SECRETS or not _SITE_KEY.fullmatch(key):
        return ""
    return (
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
        f'<div class="cf-turnstile" data-sitekey="{key}" data-action="{ACTION}"></div>'
    )


def render_widget(candidate: str) -> bool:
    """Show the widget. The sandboxed frame cannot submit the token by itself."""
    markup = widget_markup(candidate)
    if not markup:
        return False
    import streamlit as st

    st.html(markup, unsafe_allow_javascript=True)
    return True


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

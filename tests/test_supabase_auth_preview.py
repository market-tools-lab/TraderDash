"""Preview Auth login. Skipped unless every preview value is configured.

Nothing in this file is a default user, password, or key. The URL must be
the preview origin. A service-role key is rejected before any request.
"""

from __future__ import annotations

import base64
import json
import os
import unittest
from collections.abc import Mapping
from urllib.parse import urlsplit

import supabase_auth
import universes

PREVIEW_REF = "ajbsoudovxstlolojvte"
REQUIRED = (
    "TRADERDASH_SUPABASE_URL",
    "TRADERDASH_SUPABASE_ANON_KEY",
    "TRADERDASH_PREVIEW_TEST_EMAIL",
    "TRADERDASH_PREVIEW_TEST_USER_ID",
    "TRADERDASH_PREVIEW_TEST_PASSWORD",
)


class PreviewConfigError(Exception):
    """A safe explanation. The message never includes a secret or a URL."""


def preview_config(environ: Mapping[str, str] | None = None) -> tuple[dict[str, str] | None, str | None]:
    """Return (config, None), (None, skip reason), or raise PreviewConfigError."""
    env = os.environ if environ is None else environ
    missing = [name for name in REQUIRED if not str(env.get(name, "")).strip()]
    if missing:
        return None, "missing preview configuration: " + ", ".join(missing)
    _require_preview_url(str(env["TRADERDASH_SUPABASE_URL"]))
    _require_preview_key(str(env["TRADERDASH_SUPABASE_ANON_KEY"]).strip())
    return {
        "email": str(env["TRADERDASH_PREVIEW_TEST_EMAIL"]).strip(),
        "user_id": str(env["TRADERDASH_PREVIEW_TEST_USER_ID"]).strip(),
        "password": str(env["TRADERDASH_PREVIEW_TEST_PASSWORD"]),
    }, None


def _require_preview_url(url: str) -> None:
    parsed = urlsplit(url.strip())
    path = parsed.path.rstrip("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != PREVIEW_REF + ".supabase.co"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or path
    ):
        raise PreviewConfigError("TRADERDASH_SUPABASE_URL is not the preview project")


def _require_preview_key(key: str) -> None:
    if key.startswith("sb_secret_"):
        raise PreviewConfigError("service role is not allowed in the preview test")
    if key.startswith("sb_publishable_"):
        return
    claims = _jwt_claims(key)
    if claims is None:
        raise PreviewConfigError("preview key must be an anon or publishable key")
    role = str(claims.get("role") or "")
    ref = str(claims.get("ref") or "")
    if role == "service_role":
        raise PreviewConfigError("service role is not allowed in the preview test")
    if role != "anon" or ref != PREVIEW_REF:
        raise PreviewConfigError("preview key does not belong to the preview project")


def _jwt_claims(key: str) -> dict | None:
    parts = key.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        raise PreviewConfigError("preview key could not be checked") from None
    if not isinstance(claims, dict):
        raise PreviewConfigError("preview key could not be checked")
    return claims


class PreviewAuthTests(unittest.TestCase):
    def setUp(self):
        try:
            config, skip = preview_config()
        except PreviewConfigError as exc:
            self.fail(str(exc))
        if skip:
            self.skipTest(skip)
        self.config = config

    def test_login_profile_free_entitlement_and_logout(self):
        email = self.config["email"]
        user_id = self.config["user_id"]
        try:
            session = supabase_auth.sign_in(email, self.config["password"])
        except supabase_auth.AuthError:
            self.fail("preview auth is not available")
        if session is None:
            self.fail("preview login was rejected")
        if session.user_id != user_id or session.profile_id != user_id:
            self.fail("signed-in user does not match the configured test user")
        if session.plan != "free":
            self.fail("active entitlement did not resolve to free")
        self.assertEqual(len(universes.stocks_for("free")), 30)
        state = {
            "login_password": "present-before-remember",
            "register_password": "present-before-remember",
            "register_confirmation": "present-before-remember",
        }
        supabase_auth.remember(session, state)
        for key in supabase_auth.PASSWORD_KEYS:
            self._require_absent(state, key)
        if state.get(supabase_auth.USER_KEY) != user_id:
            self.fail("session state does not keep the configured user id")
        if not state.get(supabase_auth.TOKEN_KEY):
            self.fail("session state has no access token")
        supabase_auth.logout(state)
        self._require_absent(state, supabase_auth.TOKEN_KEY)
        self._require_absent(state, supabase_auth.USER_KEY)

    def _require_absent(self, state: dict, key: str) -> None:
        if key in state:
            self.fail(f"{key} is still present")

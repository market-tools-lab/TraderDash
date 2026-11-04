"""Supabase Auth mode and entitlement translation. No network and no secrets."""

from __future__ import annotations

import base64
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import access
import supabase_auth
import universes

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def _row(plan: str, status: str = "active", product: str = "traderdash", ends_at=None, starts_at="2020-01-01T00:00:00Z"):
    return {
        "status": status,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "products": {"code": product},
        "plans": {"code": plan},
    }


def _transport(password_ok: str, rows: list[dict]):
    def transport(method, url, headers, body):
        if url.endswith("/token?grant_type=password"):
            if body["password"] != password_ok:
                return 400, {"error": "invalid_grant"}
            return 200, {
                "access_token": "session-token",
                "user": {"id": "user-1", "email": body["email"]},
            }
        if url.endswith("/auth/v1/user"):
            if headers["Authorization"] != "Bearer session-token":
                return 401, {}
            return 200, {"id": "user-1", "email": "person@example.invalid"}
        if "/profiles" in url:
            return 200, [{"id": "user-1", "display_name": None}]
        if "/entitlements" in url:
            return 200, rows
        if url.endswith("/logout"):
            return 204, {}
        return 500, {}

    return transport


class AuthModeTests(unittest.TestCase):
    def test_missing_or_unknown_mode_stays_on_legacy(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRADERDASH_AUTH_MODE", None)
            self.assertEqual(supabase_auth.auth_mode(), "legacy")
        for value in ("", "legacy", "dual", "SUPABASE", "supabase"):
            with patch.dict(os.environ, {"TRADERDASH_AUTH_MODE": value}):
                self.assertEqual(supabase_auth.auth_mode(), "legacy")

    def test_supabase_auth_mode_is_explicit(self):
        with patch.dict(os.environ, {"TRADERDASH_AUTH_MODE": "supabase_auth"}):
            self.assertEqual(supabase_auth.auth_mode(), "supabase_auth")
        with patch.dict(os.environ, {"TRADERDASH_AUTH_MODE": "  Supabase_Auth  "}):
            self.assertEqual(supabase_auth.auth_mode(), "supabase_auth")

    def test_legacy_gate_still_uses_the_existing_account_functions(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("accounts.authenticate(email, password)", source)
        self.assertIn("accounts.create_user(email, password)", source)
        self.assertIn("accounts.get_user(", source)


class SessionTests(unittest.TestCase):
    def test_password_is_removed_after_login(self):
        state = {
            "login_password": "not-kept",
            "register_password": "not-kept",
            "register_confirmation": "not-kept",
        }
        session = supabase_auth.AuthSession(
            user_id="user-1",
            email="person@example.invalid",
            access_token="session-token",
            plan="free",
            profile_id="user-1",
        )
        supabase_auth.remember(session, state)
        self.assertNotIn("login_password", state)
        self.assertNotIn("register_password", state)
        self.assertNotIn("register_confirmation", state)
        self.assertEqual(state[supabase_auth.USER_KEY], "user-1")
        self.assertEqual(state[supabase_auth.TOKEN_KEY], "session-token")

    def test_logout_removes_the_session(self):
        state = {supabase_auth.TOKEN_KEY: "session-token", supabase_auth.USER_KEY: "user-1"}
        calls = []

        def transport(method, url, headers, body):
            calls.append(method)
            return 204, {}

        with patch.dict(
            os.environ,
            {
                "TRADERDASH_SUPABASE_URL": "https://ajbsoudovxstlolojvte.supabase.co",
                "TRADERDASH_SUPABASE_ANON_KEY": "test-anon-key",
            },
        ):
            supabase_auth.logout(state, transport=transport)
        self.assertEqual(calls, ["POST"])
        self.assertNotIn(supabase_auth.TOKEN_KEY, state)
        self.assertNotIn(supabase_auth.USER_KEY, state)

    def test_sign_in_reads_free_entitlement_and_rejects_a_wrong_password(self):
        transport = _transport("correct-password", [_row("free")])
        with patch.dict(
            os.environ,
            {
                "TRADERDASH_SUPABASE_URL": "https://ajbsoudovxstlolojvte.supabase.co",
                "TRADERDASH_SUPABASE_ANON_KEY": "test-anon-key",
            },
        ):
            rejected = supabase_auth.sign_in("person@example.invalid", "wrong", transport=transport)
            session = supabase_auth.sign_in("person@example.invalid", "correct-password", transport=transport)
        self.assertIsNone(rejected)
        self.assertIsNotNone(session)
        self.assertEqual(session.user_id, "user-1")
        self.assertEqual(session.profile_id, "user-1")
        self.assertEqual(session.plan, "free")
        self.assertEqual(len(universes.stocks_for(session.plan)), 30)
        self.assertTrue(access.may_analyse(next(iter(universes.stocks_for("free"))), session.plan))


class EntitlementTranslationTests(unittest.TestCase):
    def test_known_plans_pass_through(self):
        for plan in ("free", "nordic", "international"):
            self.assertEqual(supabase_auth.plan_from_entitlements([_row(plan)], NOW), plan)

    def test_closed_states_grant_no_plan(self):
        past = (NOW - timedelta(hours=1)).isoformat()
        future = (NOW + timedelta(days=1)).isoformat()
        closed = [
            [],
            None,
            [_row("free", status="revoked")],
            [_row("nordic", status="suspended")],
            [_row("international", status="expired")],
            [_row("free", ends_at=past)],
            [_row("free", starts_at=future)],
            [_row("free", product="other-product")],
            [_row("unknown")],
        ]
        for rows in closed:
            self.assertIsNone(supabase_auth.plan_from_entitlements(rows, NOW))
        self.assertFalse(access.may_analyse("NOVO-B.CO", ""))


def _jwt(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


class PreviewConfigTests(unittest.TestCase):
    def test_preview_source_has_no_historical_user_or_secret(self):
        source = (ROOT / "tests" / "test_supabase_auth_preview.py").read_text(encoding="utf-8")
        auth_source = (ROOT / "supabase_auth.py").read_text(encoding="utf-8")
        self.assertNotIn("32772e00-62a3-4d85-8da6-eeb806cb56c5", source)
        self.assertNotIn("service_role", auth_source)
        self.assertNotIn("print(", auth_source)
        self.assertNotIn("print(", source)
        self.assertNotIn("example.supabase.co", auth_source)
        for line in auth_source.splitlines():
            if "supabase.co" in line:
                self.assertIn("ajbsoudovxstlolojvte", line)
        self.assertNotIn("TRADERDASH_SUPABASE_SERVICE", source)

    def test_missing_preview_configuration_skips_without_a_default_user(self):
        from tests.test_supabase_auth_preview import REQUIRED, preview_config

        config, reason = preview_config({})
        self.assertIsNone(config)
        self.assertIsNotNone(reason)
        for name in REQUIRED:
            self.assertIn(name, reason)

    def test_only_the_preview_origin_and_anon_key_are_accepted(self):
        from tests.test_supabase_auth_preview import PreviewConfigError, preview_config

        anon = _jwt({"role": "anon", "ref": "ajbsoudovxstlolojvte"})
        base = {
            "TRADERDASH_SUPABASE_URL": "https://ajbsoudovxstlolojvte.supabase.co",
            "TRADERDASH_SUPABASE_ANON_KEY": anon,
            "TRADERDASH_PREVIEW_TEST_EMAIL": "person@example.invalid",
            "TRADERDASH_PREVIEW_TEST_USER_ID": "user-from-env",
            "TRADERDASH_PREVIEW_TEST_PASSWORD": "not-stored",
        }
        config, reason = preview_config(base)
        self.assertIsNone(reason)
        self.assertEqual(config["user_id"], "user-from-env")
        self.assertNotIn("access_token", config)

        other_host = dict(base, TRADERDASH_SUPABASE_URL="https://example.supabase.co")
        with self.assertRaises(PreviewConfigError):
            preview_config(other_host)

        service = dict(base, TRADERDASH_SUPABASE_ANON_KEY=_jwt({"role": "service_role", "ref": "ajbsoudovxstlolojvte"}))
        with self.assertRaises(PreviewConfigError) as raised:
            preview_config(service)
        self.assertNotIn("eyJ", str(raised.exception))
        self.assertNotIn("service_role", str(raised.exception))

        other_project = dict(base, TRADERDASH_SUPABASE_ANON_KEY=_jwt({"role": "anon", "ref": "other-project"}))
        with self.assertRaises(PreviewConfigError):
            preview_config(other_project)

        secret = dict(base, TRADERDASH_SUPABASE_ANON_KEY="sb_secret_not_a_client_key")
        with self.assertRaises(PreviewConfigError):
            preview_config(secret)

        publishable = dict(base, TRADERDASH_SUPABASE_ANON_KEY="sb_publishable_example")
        config, reason = preview_config(publishable)
        self.assertIsNone(reason)
        self.assertEqual(config["email"], "person@example.invalid")

"""Password policy and reset flow. No network and no stored secrets."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import password_policy
import supabase_auth

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    "TRADERDASH_SUPABASE_URL": "https://ajbsoudovxstlolojvte.supabase.co",
    "TRADERDASH_SUPABASE_ANON_KEY": "test-anon-key",
}
PASSPHRASE = "correct horse battery staple"


class PolicyTests(unittest.TestCase):
    def test_length_and_weak_passwords(self):
        password_policy.require(PASSPHRASE)
        password_policy.require(("alpha-bravo-" * 12)[:128])
        with self.assertRaises(password_policy.PasswordRejected):
            password_policy.require("a" * 129)
        with self.assertRaises(password_policy.PasswordRejected):
            password_policy.require("short-pass")
        with self.assertRaises(password_policy.PasswordRejected) as raised:
            password_policy.require("passwordpassword")
        self.assertNotIn("passwordpassword", str(raised.exception))
        self.assertFalse(password_policy.matches("one-long-secret", "another-secret"))
        self.assertTrue(password_policy.matches(PASSPHRASE, PASSPHRASE))


class ResetFlowTests(unittest.TestCase):
    def test_reset_is_neutral_and_stays_on_the_preview(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append((method, url, None if body is None else sorted(body)))
            return 400, {"msg": "not found"}

        with patch.dict(os.environ, ENV):
            accepted = supabase_auth.request_password_reset(
                "person@example.invalid",
                supabase_auth.PREVIEW_ORIGIN,
                transport=transport,
            )
            with self.assertRaises(supabase_auth.AuthError) as raised:
                supabase_auth.request_password_reset(
                    "person@example.invalid",
                    "https://example.supabase.co",
                    transport=transport,
                )
        self.assertTrue(accepted)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "POST")
        self.assertIn("/auth/v1/recover?redirect_to=", calls[0][1])
        self.assertNotIn("person@example.invalid", calls[0][1])
        self.assertNotIn("example.supabase.co", str(raised.exception))
        self.assertNotIn("person@example.invalid", str(raised.exception))

    def test_missing_recovery_session_is_rejected_before_a_request(self):
        def transport(method, url, headers, body):
            raise AssertionError("request was sent")

        with patch.dict(os.environ, ENV):
            self.assertIsNone(supabase_auth.verify_recovery_session("", transport=transport))
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.update_password("", PASSPHRASE, transport=transport)

    def test_password_change_checks_confirmation_and_clears_the_session(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append((method, url))
            if method == "PUT":
                self.assertNotIn("password", "".join(calls[-1]))
                return 200, {"id": "user-1"}
            return 204, {}

        state = {
            supabase_auth.TOKEN_KEY: "session-token",
            supabase_auth.USER_KEY: "user-1",
            "next_password": PASSPHRASE,
            "next_confirmation": PASSPHRASE,
        }
        with patch.dict(os.environ, ENV):
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.change_password("session-token", PASSPHRASE, "different-secret", transport=transport)
            supabase_auth.change_password("session-token", PASSPHRASE, PASSPHRASE, transport=transport)
            supabase_auth.sign_out_all_supported_sessions(state, transport=transport)
        self.assertEqual(calls[0][0], "PUT")
        self.assertIn("/auth/v1/user", calls[0][1])
        self.assertIn("scope=global", calls[1][1])
        self.assertNotIn("next_password", state)
        self.assertNotIn(supabase_auth.TOKEN_KEY, state)

    def test_legacy_login_does_not_gain_the_reset_form(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        legacy = source.split("def render_account_gate", 1)[1].split("\nst.title", 1)[0]
        self.assertNotIn("request_password_reset", legacy)
        self.assertIn("accounts.create_user(email, password)", legacy)
        self.assertEqual(source.count("request_password_reset"), 1)

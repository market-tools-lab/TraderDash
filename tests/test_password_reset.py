"""Password policy and reset flow. No network and no stored secrets."""

from __future__ import annotations

import os
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

import password_policy
import supabase_auth

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    "TRADERDASH_SUPABASE_URL": "https://ajbsoudovxstlolojvte.supabase.co",
    "TRADERDASH_SUPABASE_ANON_KEY": "test-anon-key",
}
READY = {
    **ENV,
    "TRADERDASH_PASSWORD_RECOVERY": "enabled",
    "TRADERDASH_AUTH_EMAIL_DELIVERY": "configured",
    "TRADERDASH_AUTH_REDIRECT_URL": "https://ajbsoudovxstlolojvte.supabase.co",
    "TRADERDASH_AUTH_REDIRECT_ALLOWLIST": "https://ajbsoudovxstlolojvte.supabase.co",
}
PILOT_REDIRECT = "https://traderdash-next.streamlit.app"
PRODUCTION_URL = "https://wxvobyifckbpnqfbnlxl.supabase.co"
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
    def test_known_and_unknown_addresses_get_the_same_neutral_result(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append((method, url, body))
            return (200 if len(calls) == 1 else 400), {}

        with patch.dict(os.environ, READY):
            known = supabase_auth.request_password_reset(
                "person@example.invalid",
                supabase_auth.configured_redirect(),
                transport=transport,
            )
            unknown = supabase_auth.request_password_reset(
                "missing@example.invalid",
                supabase_auth.configured_redirect(),
                transport=transport,
            )
        self.assertTrue(known)
        self.assertTrue(unknown)
        self.assertEqual(supabase_auth.RESET_MESSAGE, "Hvis der er en konto til e-mailadressen, sender vi en vejledning.")
        self.assertEqual(len(calls), 2)
        for _method, url, body in calls:
            self.assertIn("/auth/v1/recover?redirect_to=", url)
            self.assertNotIn("example.invalid", url)
            self.assertNotIn("@", url)
            self.assertNotIn(body["email"], url)

    def test_empty_and_malformed_addresses_do_not_call_auth(self):
        def transport(method, url, headers, body):
            raise AssertionError("request was sent")

        with patch.dict(os.environ, READY):
            for email in ("", "   ", "not-an-email", "a@b", "a@@example.invalid", "person@example.invalid extra"):
                with self.assertRaises(supabase_auth.AuthError) as raised:
                    supabase_auth.request_password_reset(email, supabase_auth.PREVIEW_ORIGIN, transport=transport)
                self.assertEqual(str(raised.exception), supabase_auth.INVALID_EMAIL)
                if email.strip():
                    self.assertNotIn(email.strip(), str(raised.exception))

    def test_missing_delivery_configuration_fails_before_a_request(self):
        def transport(method, url, headers, body):
            raise AssertionError("request was sent")

        blocked = {
            "TRADERDASH_SUPABASE_URL": PRODUCTION_URL,
            "TRADERDASH_SUPABASE_ANON_KEY": "test-anon-key",
            "TRADERDASH_AUTH_REDIRECT_URL": PILOT_REDIRECT,
            "TRADERDASH_AUTH_REDIRECT_ALLOWLIST": PILOT_REDIRECT,
        }
        with patch.dict(os.environ, blocked, clear=False):
            os.environ.pop("TRADERDASH_PASSWORD_RECOVERY", None)
            os.environ.pop("TRADERDASH_AUTH_EMAIL_DELIVERY", None)
            self.assertFalse(supabase_auth.delivery_enabled())
            with self.assertRaises(supabase_auth.AuthError) as raised:
                supabase_auth.request_password_reset(
                    "person@example.invalid",
                    PILOT_REDIRECT,
                    transport=transport,
                )
        self.assertEqual(str(raised.exception), supabase_auth.RESET_UNAVAILABLE)
        self.assertNotIn(PRODUCTION_URL, str(raised.exception))

    def test_redirects_must_match_the_allowlist_exactly(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append(url)
            return 200, {}

        allow = PILOT_REDIRECT + ",http://localhost:8501"
        ready = {
            **READY,
            "TRADERDASH_AUTH_REDIRECT_URL": PILOT_REDIRECT,
            "TRADERDASH_AUTH_REDIRECT_ALLOWLIST": allow,
        }
        rejected = [
            "https://example.supabase.co",
            PILOT_REDIRECT + "/evil",
            PILOT_REDIRECT + "?next=https://evil.example",
            "https://user:secret@traderdash-next.streamlit.app",
            "http://evil.example",
            "",
        ]
        with patch.dict(os.environ, ready):
            supabase_auth.request_password_reset("person@example.invalid", PILOT_REDIRECT, transport=transport)
            supabase_auth.request_password_reset("person@example.invalid", "http://localhost:8501", transport=transport)
            for redirect in rejected:
                with self.assertRaises(supabase_auth.AuthError):
                    supabase_auth.request_password_reset("person@example.invalid", redirect, transport=transport)
        self.assertEqual(len(calls), 2)
        self.assertIn(urllib.parse.quote(PILOT_REDIRECT, safe=""), calls[0])
        self.assertIn(urllib.parse.quote("http://localhost:8501", safe=""), calls[1])
        self.assertTrue(all("evil" not in url and "secret" not in url for url in calls))

    def test_session_cooldown_does_not_send_a_second_request(self):
        calls = []
        moment = supabase_auth.datetime(2026, 11, 4, tzinfo=supabase_auth.timezone.utc)

        def transport(method, url, headers, body):
            calls.append(url)
            return 200, {}

        state = {}
        with patch.dict(os.environ, READY):
            supabase_auth.request_password_reset(
                "person@example.invalid",
                supabase_auth.PREVIEW_ORIGIN,
                transport=transport,
                state=state,
                now=moment,
            )
            with self.assertRaises(supabase_auth.AuthError) as raised:
                supabase_auth.request_password_reset(
                    "other@example.invalid",
                    supabase_auth.PREVIEW_ORIGIN,
                    transport=transport,
                    state=state,
                    now=moment,
                )
        self.assertEqual(len(calls), 1)
        self.assertEqual(str(raised.exception), supabase_auth.RESET_COOLDOWN)
        self.assertNotIn("other@example.invalid", str(raised.exception))

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
        pilot = dict(ENV, TRADERDASH_SUPABASE_URL=PRODUCTION_URL)
        with patch.dict(os.environ, pilot):
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.change_password("session-token", PASSPHRASE, "different-secret", transport=transport)
            supabase_auth.change_password("session-token", PASSPHRASE, PASSPHRASE, transport=transport)
            supabase_auth.sign_out_all_supported_sessions(state, transport=transport)
        self.assertEqual(calls[0][0], "PUT")
        self.assertIn(PRODUCTION_URL + "/auth/v1/user", calls[0][1])
        self.assertNotIn("ajbsoudovxstlolojvte", calls[0][1])
        self.assertIn("scope=global", calls[1][1])
        self.assertNotIn("ajbsoudovxstlolojvte", calls[1][1])
        self.assertNotIn("next_password", state)
        self.assertNotIn(supabase_auth.TOKEN_KEY, state)

    def test_deleted_preview_is_not_a_password_change_target(self):
        def transport(method, url, headers, body):
            raise AssertionError("request was sent")

        with patch.dict(os.environ, ENV):
            with self.assertRaises(supabase_auth.AuthError) as raised:
                supabase_auth.change_password("session-token", PASSPHRASE, PASSPHRASE, transport=transport)
        self.assertNotIn(PASSPHRASE, str(raised.exception))
        self.assertNotIn("ajbsoudovxstlolojvte", str(raised.exception))

    def test_short_password_and_missing_session_do_not_call_the_pilot(self):
        def transport(method, url, headers, body):
            raise AssertionError("request was sent")

        pilot = dict(ENV, TRADERDASH_SUPABASE_URL=PRODUCTION_URL)
        with patch.dict(os.environ, pilot):
            with self.assertRaises(supabase_auth.AuthError) as raised:
                supabase_auth.change_password("session-token", "short-pass", "short-pass", transport=transport)
            self.assertNotIn("short-pass", str(raised.exception))
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.change_password("", PASSPHRASE, PASSPHRASE, transport=transport)

    def test_legacy_gate_does_not_offer_password_change(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        legacy = source.split("def render_account_gate", 1)[1]
        self.assertNotIn("Skift adgangskode", legacy)
        self.assertNotIn("Slet konto", source)

    def test_legacy_login_does_not_gain_the_reset_form(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        legacy = source.split("def render_account_gate", 1)[1].split("\nst.title", 1)[0]
        self.assertNotIn("request_password_reset", legacy)
        self.assertIn("accounts.create_user(email, password)", legacy)
        self.assertIn("discard_recovery_query", source)
        self.assertEqual(source.count("request_password_reset"), 1)
        self.assertIn("configured_redirect()", source)
        self.assertNotIn("request_password_reset(email, supabase_auth.PREVIEW_ORIGIN)", source)


class RecoveryTests(unittest.TestCase):
    def test_wrong_project_implicit_and_closed_delivery_never_call_auth(self):
        def transport(method, url, headers, body):
            raise AssertionError("request was sent")

        params = {"token_hash": "hash-1", "type": "recovery", "ref": "other-project", "next": "https://evil.example"}
        with patch.dict(os.environ, READY):
            with self.assertRaises(supabase_auth.AuthError) as raised:
                supabase_auth.take_recovery_token(params)
            self.assertNotIn("hash-1", str(raised.exception))
            implicit = {"code": "pkce-code"}
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.take_recovery_token(implicit)
        closed = dict(READY)
        closed.pop("TRADERDASH_PASSWORD_RECOVERY")
        with patch.dict(os.environ, closed, clear=True):
            os.environ.update({key: value for key, value in closed.items()})
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.take_recovery_token({"token_hash": "hash-1", "type": "recovery"})
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.complete_recovery("hash-1", PASSPHRASE, PASSPHRASE, transport=transport)

    def test_expired_link_and_password_failures_keep_secrets_out_of_errors(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append(url)
            return 403, {"msg": "hash-1 " + PASSPHRASE}

        with patch.dict(os.environ, READY):
            with self.assertRaises(supabase_auth.AuthError) as expired:
                supabase_auth.complete_recovery("hash-1", PASSPHRASE, PASSPHRASE, transport=transport)
            with self.assertRaises(supabase_auth.AuthError) as mismatch:
                supabase_auth.complete_recovery("hash-1", PASSPHRASE, "another-long-secret", transport=transport)
            with self.assertRaises(supabase_auth.AuthError) as weak:
                supabase_auth.complete_recovery("hash-1", "passwordpassword", "passwordpassword", transport=transport)
        self.assertEqual(str(expired.exception), supabase_auth.RESET_INVALID)
        self.assertNotIn("hash-1", str(expired.exception))
        self.assertNotIn(PASSPHRASE, str(expired.exception))
        self.assertEqual(str(mismatch.exception), "Adgangskoderne er ikke ens.")
        self.assertEqual(str(weak.exception), "Adgangskoden er for svag.")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].endswith("/auth/v1/verify"))

    def test_successful_recovery_updates_the_password_and_drops_the_session(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append((method, url, None if body is None else dict(body)))
            if url.endswith("/auth/v1/verify"):
                self.assertNotIn("hash-1", url)
                return 200, {"access_token": "access-1", "refresh_token": "refresh-1"}
            if method == "PUT":
                self.assertEqual(headers["Authorization"], "Bearer access-1")
                self.assertNotIn("refresh-1", url)
                return 200, {"id": "user-1"}
            if url.endswith("/auth/v1/logout"):
                self.assertEqual(headers["Authorization"], "Bearer access-1")
                return 204, {}
            raise AssertionError(url)

        state = {supabase_auth.RECOVERY_TOKEN_KEY: "hash-1", "recovery_password": PASSPHRASE}
        with patch.dict(os.environ, READY):
            supabase_auth.complete_recovery("hash-1", PASSPHRASE, PASSPHRASE, transport=transport, state=state)
        self.assertEqual([call[0] for call in calls], ["POST", "PUT", "POST"])
        self.assertNotIn(supabase_auth.RECOVERY_TOKEN_KEY, state)
        self.assertNotIn("recovery_password", state)
        self.assertNotIn("refresh-1", str(state))
        self.assertNotIn("access-1", str(state))

    def test_templates_are_placeholders_without_live_links(self):
        directory = ROOT / "docs" / "production" / "email"
        reset_text = (directory / "password-reset.txt").read_text(encoding="utf-8")
        reset_html = (directory / "password-reset.html").read_text(encoding="utf-8")
        changed = (directory / "password-changed.txt").read_text(encoding="utf-8")
        signup_text = (directory / "signup-confirmation.txt").read_text(encoding="utf-8")
        signup_html = (directory / "signup-confirmation.html").read_text(encoding="utf-8")
        for body in (reset_text, reset_html, signup_text, signup_html):
            self.assertIn("{{ .TokenHash }}", body)
            self.assertIn("{{ .RedirectTo }}", body)
            self.assertNotIn("wxvobyifckbpnqfbnlxl", body)
            self.assertNotIn("eyJ", body)
            self.assertNotIn("ConfirmationURL", body)
        self.assertIn("type=signup", signup_text)
        self.assertIn("type=signup", signup_html)
        self.assertIn("ikke til udsendelse", changed.lower())

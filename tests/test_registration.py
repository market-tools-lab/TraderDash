"""Closed registration. No network, no real account, and no mail."""

from __future__ import annotations

import os
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import account_lifecycle
import account_privacy
import operations
import registration
import stripe_test
import supabase_auth

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_URL = "https://wxvobyifckbpnqfbnlxl.supabase.co"
PREVIEW_URL = "https://ajbsoudovxstlolojvte.supabase.co"
REDIRECT = "https://traderdash-next.streamlit.app"
PASSPHRASE = "correct horse battery staple"
TOKEN = "captcha-token-test"
EMAIL = "person@example.invalid"
NEW_ID = "11111111-1111-4111-8111-111111111111"
OPEN = {
    "TRADERDASH_AUTH_MODE": "supabase_auth",
    "TRADERDASH_AUTH_REGISTRATION": "enabled",
    "TRADERDASH_PASSWORD_RECOVERY": "enabled",
    "TRADERDASH_AUTH_EMAIL_DELIVERY": "configured",
    "TRADERDASH_SUPABASE_URL": PRODUCTION_URL,
    "TRADERDASH_SUPABASE_ANON_KEY": "test-anon-key",
    "TRADERDASH_AUTH_REDIRECT_URL": REDIRECT,
    "TRADERDASH_AUTH_REDIRECT_ALLOWLIST": REDIRECT,
}


def opened(**extra):
    values = dict(OPEN)
    values.update(extra)
    return patch.dict(os.environ, values, clear=False)


class RegistrationTests(unittest.TestCase):
    def test_missing_disabled_and_unknown_flags_stay_closed(self):
        self.assertFalse(registration.registration_open({}))
        self.assertFalse(registration.registration_open({"TRADERDASH_AUTH_REGISTRATION": "disabled"}))
        self.assertFalse(registration.registration_open({"TRADERDASH_AUTH_REGISTRATION": "yes"}))
        calls = []
        with self.assertRaises(registration.RegistrationRejected) as raised:
            registration.submit(
                EMAIL,
                PASSPHRASE,
                PASSPHRASE,
                acknowledged=True,
                captcha_token=TOKEN,
                redirect_url=REDIRECT,
                env={"TRADERDASH_AUTH_MODE": "supabase_auth", "TRADERDASH_AUTH_REGISTRATION": "disabled"},
                transport=lambda *args: calls.append(args),
            )
        self.assertEqual(raised.exception.reason, "closed")
        self.assertEqual(calls, [])
        legacy = {"TRADERDASH_AUTH_MODE": "legacy", "TRADERDASH_AUTH_REGISTRATION": "enabled"}
        with self.assertRaises(registration.RegistrationRejected) as legacy_raised:
            registration.submit(
                EMAIL,
                PASSPHRASE,
                PASSPHRASE,
                acknowledged=True,
                captcha_token=TOKEN,
                redirect_url=REDIRECT,
                env=legacy,
                transport=lambda *args: calls.append(args),
            )
        self.assertEqual(legacy_raised.exception.reason, "closed")
        self.assertEqual(calls, [])

    def test_local_rejections_do_not_call_auth_or_log_secrets(self):
        cases = [
            ("not-an-email", PASSPHRASE, PASSPHRASE, True, TOKEN, "free", "email"),
            (EMAIL, PASSPHRASE, "another passphrase", True, TOKEN, "free", "password_mismatch"),
            (EMAIL, "passwordpassword", "passwordpassword", True, TOKEN, "free", "weak"),
            (EMAIL, PASSPHRASE, PASSPHRASE, False, TOKEN, "free", "acknowledgement"),
            (EMAIL, PASSPHRASE, PASSPHRASE, True, "", "free", "captcha"),
            (EMAIL, PASSPHRASE, PASSPHRASE, True, TOKEN, "nordic", "plan"),
            (EMAIL, PASSPHRASE, PASSPHRASE, True, TOKEN, "international", "plan"),
        ]
        for email, password, confirmation, acknowledged, captcha, plan, reason in cases:
            calls = []
            stream = StringIO()
            with opened(), redirect_stderr(stream), self.assertRaises(registration.RegistrationRejected) as raised:
                registration.submit(
                    email,
                    password,
                    confirmation,
                    acknowledged=acknowledged,
                    captcha_token=captcha,
                    redirect_url=REDIRECT,
                    plan=plan,
                    transport=lambda *args: calls.append(args),
                )
            self.assertEqual(raised.exception.reason, reason)
            self.assertEqual(calls, [])
            text = stream.getvalue()
            self.assertNotIn(PASSPHRASE, text)
            self.assertNotIn("passwordpassword", text)
            self.assertNotIn(EMAIL, text)
            self.assertNotIn(TOKEN, text)

    def test_valid_signup_stays_unconfirmed_and_hides_secrets(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append((method, url, body))
            return 200, {"user": {"id": NEW_ID}}

        stream = StringIO()
        with opened(), redirect_stderr(stream):
            result = registration.submit(
                EMAIL,
                PASSPHRASE,
                PASSPHRASE,
                acknowledged=True,
                captcha_token=TOKEN,
                redirect_url=REDIRECT,
                transport=transport,
            )
        self.assertEqual(result["state"], "email_unconfirmed")
        self.assertFalse(result["access"])
        self.assertEqual(result["message"], registration.REQUEST_MESSAGE)
        self.assertEqual(result["user_id"], "")
        self.assertEqual(calls[0][0], "POST")
        self.assertTrue(calls[0][1].startswith(PRODUCTION_URL + "/auth/v1/signup"))
        self.assertNotIn("ajbsoudovxstlolojvte", calls[0][1])
        self.assertEqual(calls[0][2]["password"], PASSPHRASE)
        text = stream.getvalue()
        self.assertIn("REGISTRATION_VERIFICATION_REQUIRED", text)
        self.assertNotIn(PASSPHRASE, text)
        self.assertNotIn(EMAIL, text)
        self.assertNotIn(TOKEN, text)
        self.assertNotIn("access_token", text)

    def test_duplicate_signup_uses_the_same_public_message(self):
        def transport(method, url, headers, body):
            return 422, {"message": EMAIL}

        with opened():
            created = registration.submit(
                EMAIL, PASSPHRASE, PASSPHRASE, acknowledged=True, captcha_token=TOKEN, redirect_url=REDIRECT, transport=lambda *args: (200, {"user": {}})
            )
            duplicate = registration.submit(
                EMAIL, PASSPHRASE, PASSPHRASE, acknowledged=True, captcha_token=TOKEN, redirect_url=REDIRECT, transport=transport
            )
        self.assertEqual(created["message"], duplicate["message"])
        self.assertEqual(duplicate["state"], "duplicate_hidden")
        self.assertFalse(duplicate["access"])
        self.assertNotIn(EMAIL, duplicate["message"])

    def test_immediate_session_does_not_grant_access(self):
        def transport(method, url, headers, body):
            return 200, {"access_token": "session-secret", "user": {"id": NEW_ID, "email_confirmed_at": "2026-11-09"}}

        stream = StringIO()
        with opened(), redirect_stderr(stream):
            result = registration.submit(
                EMAIL, PASSPHRASE, PASSPHRASE, acknowledged=True, captcha_token=TOKEN, redirect_url=REDIRECT, transport=transport
            )
        self.assertEqual(result["state"], "verification_bypassed")
        self.assertFalse(result["access"])
        self.assertNotIn("session-secret", stream.getvalue())

    def test_preview_redirect_and_bad_redirect_send_nothing(self):
        calls = []

        def transport(*args):
            calls.append(args)
            return 200, {"user": {}}

        with opened(TRADERDASH_SUPABASE_URL=PREVIEW_URL):
            with self.assertRaises(registration.RegistrationRejected):
                registration.submit(
                    EMAIL, PASSPHRASE, PASSPHRASE, acknowledged=True, captcha_token=TOKEN, redirect_url=REDIRECT, transport=transport
                )
        with opened():
            with self.assertRaises(registration.RegistrationRejected) as raised:
                registration.submit(
                    EMAIL, PASSPHRASE, PASSPHRASE, acknowledged=True, captcha_token=TOKEN, redirect_url="https://example.invalid", transport=transport
                )
        self.assertEqual(raised.exception.reason, "unavailable")
        self.assertEqual(calls, [])

    def test_verification_callback_is_idempotent_and_keeps_no_session(self):
        record = _ready()
        seen = []

        def verify(token):
            seen.append(token)
            return {"user_id": NEW_ID, "confirmed": True, "expired": False}

        with opened():
            first = registration.complete_verification("hash-1", record, verify=verify)
            second = registration.complete_verification("hash-1", record, verify=verify)
        self.assertEqual(first["access"], second["access"])
        self.assertTrue(first["access"])
        self.assertEqual(first["papers"], 30)
        self.assertEqual(first["free_entitlements"], 1)
        self.assertFalse(first["session_kept"])
        self.assertFalse(first["mutates"])
        self.assertEqual(seen, ["hash-1", "hash-1"])
        self.assertEqual(record["user_id"], "")

    def test_expired_callback_and_recovery_type_stay_separate(self):
        with opened():
            with self.assertRaises(registration.RegistrationRejected) as raised:
                registration.complete_verification("hash-1", _ready(), verify=lambda token: {"expired": True})
            self.assertEqual(raised.exception.reason, "expired")
            self.assertNotIn("hash-1", str(raised.exception))
            with self.assertRaises(supabase_auth.AuthError):
                supabase_auth.take_recovery_token({"token_hash": "hash-1", "type": "signup"})

    def test_partial_records_and_protected_identity_do_not_grant_access(self):
        pilot = sorted(account_privacy.PROTECTED_IDS)[0]
        missing_profile = _ready()
        missing_profile["profile"] = False
        missing_entitlement = _ready()
        missing_entitlement["entitlements"] = []
        unconfirmed = _ready()
        unconfirmed["confirmed"] = False
        duplicate = _ready()
        duplicate["entitlements"] = list(duplicate["entitlements"]) + list(duplicate["entitlements"])
        protected = _ready()
        protected["user_id"] = pilot
        preview = _ready()
        preview["target_ref"] = account_privacy.PREVIEW_REF
        for record, finding in (
            (missing_profile, "profile_missing"),
            (missing_entitlement, "entitlement_missing"),
            (unconfirmed, "unconfirmed_with_data"),
            (duplicate, "duplicate_free"),
            (protected, "protected"),
            (preview, "environment"),
        ):
            report = registration.reconcile(record)
            self.assertIn(finding, report["findings"])
            self.assertFalse(report["access"])
            self.assertFalse(report["mutates"])
        calls = []
        with self.assertRaises(registration.RegistrationRejected) as raised:
            registration.apply_free_entitlement(protected, calls.append, repair=True)
        self.assertEqual(raised.exception.reason, "protected")
        self.assertEqual(calls, [])

    def test_free_entitlement_is_created_once_and_only_away_from_production(self):
        record = _ready()
        record["entitlements"] = []
        calls = []
        first = registration.apply_free_entitlement(record, calls.append, repair=True)
        self.assertEqual(first["actions"], ["create_free"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["plan"], "free")
        self.assertEqual(record["entitlements"], [])
        record["entitlements"] = [calls[0]]
        second = registration.apply_free_entitlement(record, calls.append, repair=True)
        self.assertEqual(second["free_entitlements"], 1)
        self.assertEqual(second["actions"], [])
        self.assertEqual(len(calls), 1)
        with self.assertRaises(registration.RegistrationRejected):
            registration.apply_free_entitlement(record, calls.append)
        production = dict(record, target_ref=account_privacy.PRODUCTION_REF)
        with self.assertRaises(registration.RegistrationRejected) as raised:
            registration.apply_free_entitlement(production, calls.append, repair=True)
        self.assertEqual(raised.exception.reason, "environment")
        self.assertEqual(len(calls), 1)
        self.assertFalse(registration.REPAIR_ENABLED)
        self.assertFalse(stripe_test.ENTITLEMENT_UPDATES_ENABLED)
        self.assertFalse(account_lifecycle.DELETION_EXECUTION_ENABLED)

    def test_launch_gate_stays_closed_and_logs_are_categorised(self):
        evidence = {name: True for name in ("ci_green", "supabase_healthy", "no_preview_branch", "backups_current", "resend_healthy", "registration_code_tested", "password_change_live")}
        gate = registration.launch_gate(evidence, root=ROOT)
        self.assertFalse(gate["open_registration"])
        self.assertEqual(gate["decision"], "closed")
        self.assertEqual(gate["items"]["registration_default_off"], "PASS")
        self.assertEqual(gate["items"]["stripe_off"], "PASS")
        self.assertEqual(gate["items"]["deletion_execution_off"], "PASS")
        self.assertEqual(gate["items"]["captcha_decision_complete"], "PASS")
        self.assertEqual(gate["items"]["privacy_terms_decision_complete"], "FAIL")
        self.assertEqual(gate["items"]["entitlement_function_deployed"], "FAIL")
        self.assertEqual(registration.launch_gate({}, root=ROOT)["items"]["ci_green"], "FAIL")
        report = operations.assess({"TRADERDASH_AUTH_REGISTRATION": "enabled"})
        self.assertIn("registration_enabled", report["blockers"])
        unknown = operations.assess({"TRADERDASH_AUTH_REGISTRATION": "maybe"})
        self.assertIn("registration_flag", unknown["blockers"])
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("if registration.registration_open():", app)
        self.assertIn("Ny konto oprettes ikke i denne loginvej.", app)
        self.assertNotIn("repair=True", app)
        legacy = app.split("def render_account_gate", 1)[1]
        self.assertIn("accounts.create_user", legacy)
        self.assertIn("Opret konto", legacy)

    def test_password_change_still_refuses_the_deleted_preview(self):
        calls = []
        client = supabase_auth.Client(PREVIEW_URL, "test-anon-key", lambda *args: calls.append(args))
        with self.assertRaises(supabase_auth.AuthError):
            client.update_password("token", PASSPHRASE)
        self.assertEqual(calls, [])


def _ready() -> dict:
    return {
        "user_id": "",
        "target_ref": "local-test",
        "confirmed": True,
        "profile": True,
        "entitlements": [{"status": "active", "plan": "free", "product": "traderdash"}],
    }

"""Closed registration. No network, no real account, and no mail."""

from __future__ import annotations

import hashlib
import json
import os
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import account_lifecycle
import account_privacy
import captcha
import operations
import registration
import stripe_test
import supabase_auth
import universes

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
    "TRADERDASH_TURNSTILE": "required",
    "TRADERDASH_TURNSTILE_MODE": "test",
    "TRADERDASH_TURNSTILE_SITE_KEY": captcha.PASS_SITE_KEY,
    "TRADERDASH_TURNSTILE_SECRET_KEY": captcha.PASS_SECRET,
    "TRADERDASH_TURNSTILE_HOSTNAME": "traderdash-next.streamlit.app",
}


def opened(**extra):
    values = dict(OPEN)
    values.update(extra)
    return patch.dict(os.environ, values, clear=False)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        captcha.reset_seen()

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

    def test_live_signup_supplies_siteverify_and_withholds_auth_until_it_passes(self):
        seen = {}

        def fake_verify(token, *, env=None, transport=None):
            seen["transport"] = transport
            raise captcha.CaptchaRejected("unavailable")

        auth_calls = []
        with opened(), patch.object(captcha, "verify", fake_verify):
            with self.assertRaises(registration.RegistrationRejected) as missing:
                registration.submit(
                    EMAIL,
                    PASSPHRASE,
                    PASSPHRASE,
                    acknowledged=True,
                    captcha_token=TOKEN,
                    redirect_url=REDIRECT,
                    transport=lambda *args: auth_calls.append(args),
                )
        self.assertIs(seen["transport"], captcha.https_transport)
        self.assertEqual(missing.exception.reason, "captcha")
        self.assertEqual(auth_calls, [])
        self.assertFalse(registration.registration_open({}))
        self.assertFalse(stripe_test.ENTITLEMENT_UPDATES_ENABLED)
        self.assertFalse(account_lifecycle.DELETION_UI_ENABLED)
        self.assertFalse(account_lifecycle.DELETION_EXECUTION_ENABLED)

        site_calls = []

        def siteverify(url, payload):
            site_calls.append((url, payload["response"]))
            if payload["response"] == "bad-token":
                return {"success": False, "error-codes": ["invalid-input-response"]}
            return {"success": True, "hostname": "traderdash-next.streamlit.app", "action": "registration"}

        def auth(method, url, headers, body):
            auth_calls.append(url)
            return 200, {"user": {"id": NEW_ID}}

        live = dict(OPEN)
        live["TRADERDASH_TURNSTILE_MODE"] = "live"
        live["TRADERDASH_TURNSTILE_SECRET_KEY"] = "live-secret-not-a-test-key"
        live["TRADERDASH_ENV"] = "production"
        stream = StringIO()
        with patch.dict(os.environ, live, clear=False), redirect_stderr(stream):
            with self.assertRaises(registration.RegistrationRejected) as rejected:
                registration.submit(
                    EMAIL,
                    PASSPHRASE,
                    PASSPHRASE,
                    acknowledged=True,
                    captcha_token="bad-token",
                    redirect_url=REDIRECT,
                    transport=auth,
                    captcha_transport=siteverify,
                )
            self.assertEqual(rejected.exception.reason, "captcha")
            self.assertEqual(auth_calls, [])
            accepted = registration.submit(
                EMAIL,
                PASSPHRASE,
                PASSPHRASE,
                acknowledged=True,
                captcha_token="good-live-token",
                redirect_url=REDIRECT,
                transport=auth,
                captcha_transport=siteverify,
            )
        self.assertEqual(site_calls[0][0], captcha.SITEVERIFY_URL)
        self.assertEqual(accepted["state"], "email_unconfirmed")
        self.assertEqual(len(auth_calls), 1)
        logged = stream.getvalue()
        self.assertNotIn("live-secret-not-a-test-key", logged)
        self.assertNotIn("bad-token", logged)
        self.assertNotIn("good-live-token", logged)
        blocked = [json.loads(line) for line in logged.splitlines() if "REGISTRATION_BLOCKED" in line]
        self.assertEqual(blocked, [{"category": "REGISTRATION_BLOCKED", "correlation_id": blocked[0]["correlation_id"], "reason": "invalid", "stage": "siteverify"}])

    def test_captcha_stages_stay_closed_and_omit_the_token(self):
        live = dict(OPEN)
        live["TRADERDASH_TURNSTILE_MODE"] = "live"
        live["TRADERDASH_TURNSTILE_SECRET_KEY"] = "live-secret-not-a-test-key"
        live["TRADERDASH_ENV"] = "production"
        secret = live["TRADERDASH_TURNSTILE_SECRET_KEY"]

        def siteverify(url, payload):
            kind = payload["response"]
            if kind == "timeout-token":
                raise TimeoutError("timed out")
            if kind == "spent-token-value":
                return {"success": False, "error-codes": ["timeout-or-duplicate"]}
            if kind == "host-token-value":
                return {"success": True, "hostname": "example.invalid", "action": "registration"}
            if kind == "action-token-value":
                return {"success": True, "hostname": "traderdash-next.streamlit.app", "action": "login"}
            return {"success": False, "error-codes": ["invalid-input-response"]}

        cases = (
            ("", "token", "missing"),
            ("timeout-token", "timeout", "siteverify"),
            ("spent-token-value", "reused", "siteverify"),
            ("host-token-value", "hostname", "hostname"),
            ("action-token-value", "action", "action"),
        )
        for presented, reason, stage in cases:
            stream = StringIO()
            auth_calls = []
            with patch.dict(os.environ, live, clear=False), redirect_stderr(stream):
                with self.assertRaises(registration.RegistrationRejected) as raised:
                    registration.submit(
                        EMAIL,
                        PASSPHRASE,
                        PASSPHRASE,
                        acknowledged=True,
                        captcha_token=presented,
                        redirect_url=REDIRECT,
                        transport=lambda *args: auth_calls.append(args),
                        captcha_transport=siteverify,
                    )
            self.assertEqual(raised.exception.reason, "captcha")
            self.assertEqual(str(raised.exception), "Kontoen kunne ikke oprettes.")
            self.assertEqual(auth_calls, [])
            payload = json.loads(stream.getvalue().strip())
            self.assertEqual(payload["category"], "REGISTRATION_BLOCKED")
            self.assertEqual(payload["reason"], reason)
            self.assertEqual(payload["stage"], stage)
            self.assertNotIn(secret, stream.getvalue())
            self.assertNotIn(presented, stream.getvalue()) if presented else None

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
                EMAIL, PASSPHRASE, PASSPHRASE, acknowledged=True, captcha_token=TOKEN + "-2", redirect_url=REDIRECT, transport=transport
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
                    EMAIL, PASSPHRASE, PASSPHRASE, acknowledged=True, captcha_token=TOKEN + "-redirect", redirect_url="https://example.invalid", transport=transport
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
        record["target_ref"] = "local-test"
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
        self.assertEqual(gate["items"]["turnstile_token_return"], "PASS")
        self.assertEqual(gate["items"]["traderdash_age_policy"], "PASS")
        self.assertEqual(gate["items"]["support_requirements_documented"], "PASS")
        self.assertEqual(gate["items"]["pilot_recreation_documented"], "PASS")
        self.assertEqual(gate["items"]["privacy_terms_decision_complete"], "EXTERNAL")
        self.assertEqual(gate["items"]["support_mailbox_operational"], "PASS")
        self.assertEqual(gate["items"]["turnstile_widget_configured"], "EXTERNAL")
        self.assertEqual(gate["items"]["entitlement_function_deployed"], "PASS")
        self.assertEqual(gate["items"]["self_enrollment_prepared"], "PASS")
        self.assertEqual(gate["items"]["self_enrollment_deployed"], "PASS")
        self.assertTrue(registration.SELF_ENROLLMENT_DEPLOYED)
        self.assertEqual(gate["items"]["pilot_branch_deployed"], "EXTERNAL")
        self.assertEqual(registration.launch_gate({}, root=ROOT)["items"]["ci_green"], "EXTERNAL")
        self.assertEqual(registration.TRADERDASH_PILOT_MINIMUM_AGE, 18)
        self.assertFalse(gate["open_registration"])
        report = operations.assess({"TRADERDASH_AUTH_REGISTRATION": "enabled"})
        self.assertIn("registration_enabled", report["blockers"])
        unknown = operations.assess({"TRADERDASH_AUTH_REGISTRATION": "maybe"})
        self.assertIn("registration_flag", unknown["blockers"])
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("if registration.registration_open():", app)
        self.assertIn("Ny konto oprettes ikke i denne loginvej.", app)
        self.assertIn("fyldt 18", app)
        self.assertIn("registration.ACK_VERSION", app)
        self.assertNotIn("auth_register_captcha", app)
        self.assertNotIn("repair=True", app)
        self.assertNotIn("service_role", app)
        self.assertIn("continue_traderdash_enrollment", app)
        self.assertNotIn('"profile": False', app)
        legacy = app.split("def render_account_gate", 1)[1]
        self.assertIn("accounts.create_user", legacy)
        self.assertIn("Opret konto", legacy)

    def test_password_change_still_refuses_the_deleted_preview(self):
        calls = []
        client = supabase_auth.Client(PREVIEW_URL, "test-anon-key", lambda *args: calls.append(args))
        with self.assertRaises(supabase_auth.AuthError):
            client.update_password("token", PASSPHRASE)
        self.assertEqual(calls, [])

    def test_production_readiness_allows_one_free_signup_and_refuses_mutation(self):
        report = registration.reconcile(_ready())
        self.assertTrue(report["access"])
        self.assertEqual(report["papers"], 30)
        self.assertEqual(report["product_stage"]["source"], "signup")
        self.assertNotIn("environment", report["findings"])
        self.assertFalse(report["mutates"])
        calls = []
        with self.assertRaises(registration.RegistrationRejected) as raised:
            registration.apply_free_entitlement(_ready(), calls.append, repair=True)
        self.assertEqual(raised.exception.reason, "environment")
        self.assertEqual(calls, [])

    def test_wrong_project_paid_plans_and_foreign_sources_do_not_grant_access(self):
        wrong = _ready()
        wrong["target_ref"] = "other-project"
        nordic = _ready()
        nordic["entitlements"] = [
            {"status": "active", "plan": "nordic", "product": "traderdash", "source": "subscription"}
        ]
        international = _ready()
        international["entitlements"] = [
            {"status": "active", "plan": "international", "product": "traderdash", "source": "purchase"}
        ]
        subscription = _ready()
        subscription["entitlements"] = [
            {"status": "active", "plan": "free", "product": "traderdash", "source": "subscription"}
        ]
        purchase = _ready()
        purchase["entitlements"] = [
            {"status": "active", "plan": "free", "product": "traderdash", "source": "purchase"}
        ]
        for record, finding in (
            (wrong, "environment"),
            (nordic, "unexpected_plan"),
            (international, "unexpected_plan"),
            (subscription, "unexpected_source"),
            (purchase, "unexpected_source"),
        ):
            report = registration.reconcile(record)
            self.assertIn(finding, report["findings"])
            self.assertFalse(report["access"])
            self.assertEqual(report["papers"], 0)

    def test_confirmed_signup_enrolls_only_the_caller_and_drops_the_session(self):
        secret = "session-token-should-not-leak"
        calls = []
        enrolled = {"done": False}

        def transport(method, url, headers, body):
            calls.append((method, url, body))
            if url.endswith("/auth/v1/verify"):
                self.assertEqual(body, {"type": "signup", "token_hash": "hash-1"})
                return 200, {
                    "access_token": secret,
                    "refresh_token": "refresh-should-not-leak",
                    "user": {
                        "id": NEW_ID,
                        "email_confirmed_at": "2026-11-09T12:00:00Z",
                        "user_metadata": {"acknowledgement_version": registration.ACK_VERSION},
                    },
                }
            if url.endswith("/rest/v1/rpc/provision_traderdash_free_self"):
                self.assertEqual(body, {})
                enrolled["done"] = True
                return 204, {}
            if "/profiles" in url:
                return 200, [{"id": NEW_ID}]
            if "/entitlements" in url:
                if not enrolled["done"]:
                    return 200, []
                return 200, [
                    {
                        "status": "active",
                        "source": "signup",
                        "products": {"code": "traderdash"},
                        "plans": {"code": "free"},
                    }
                ]
            if url.endswith("/auth/v1/logout"):
                return 204, {}
            self.fail(url)

        stream = StringIO()
        with opened(), redirect_stderr(stream):
            first = registration.complete_verification("hash-1", {"profile": False}, transport=transport)
            second = registration.complete_verification("hash-1", {}, transport=transport)
        self.assertTrue(first["access"])
        self.assertTrue(second["access"])
        self.assertEqual(first["papers"], 30)
        self.assertEqual(first["product_stage"]["source"], "signup")
        self.assertFalse(first["session_kept"])
        self.assertFalse(first["mutates"])
        rpc = [call for call in calls if call[1].endswith("/rest/v1/rpc/provision_traderdash_free_self")]
        self.assertEqual(len(rpc), 2)
        self.assertEqual(sum(1 for call in calls if call[1].endswith("/auth/v1/logout")), 2)
        text = stream.getvalue()
        self.assertNotIn(secret, text)
        self.assertNotIn("refresh-should-not-leak", text)
        self.assertNotIn("hash-1", text)
        self.assertNotIn(NEW_ID, text)

    def test_unconfirmed_and_foreign_projects_do_not_enroll(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append(url)
            if url.endswith("/auth/v1/verify"):
                return 200, {"access_token": "temp-token", "user": {"id": NEW_ID}}
            if "provision_traderdash_free_self" in url:
                return 403, {"message": "email not confirmed"}
            if "/profiles" in url or "/entitlements" in url:
                return 200, []
            if url.endswith("/auth/v1/logout"):
                return 204, {}
            self.fail(url)

        with opened():
            report = registration.complete_verification("hash-1", {}, transport=transport)
        self.assertFalse(report["access"])
        self.assertIn("email_unconfirmed", report["findings"])
        self.assertTrue(any("provision_traderdash_free_self" in url for url in calls))
        preview = supabase_auth.Client(PREVIEW_URL, "test-anon-key", lambda *args: calls.append("preview"))
        with self.assertRaises(supabase_auth.AuthError):
            preview.enroll_self("temp-token")
        self.assertNotIn("preview", calls)
        other = supabase_auth.Client("https://example.supabase.co", "test-anon-key", lambda *args: calls.append("other"))
        with self.assertRaises(supabase_auth.AuthError):
            other.enroll_self("temp-token")
        self.assertNotIn("other", calls)

    def test_missing_entitlement_is_retried_for_the_signed_in_user_only(self):
        calls = []

        def transport(method, url, headers, body):
            calls.append((method, url, body))
            if "provision_traderdash_free_self" in url:
                self.assertEqual(body, {})
                return 204, {}
            if "/entitlements" in url:
                seen = len([item for item in calls if "/entitlements" in item[1]])
                if seen == 1:
                    return 200, []
                return 200, [
                    {
                        "status": "active",
                        "starts_at": "2020-01-01T00:00:00Z",
                        "ends_at": None,
                        "products": {"code": "traderdash"},
                        "plans": {"code": "free"},
                    }
                ]
            if "/profiles" in url:
                return 200, [{"id": NEW_ID, "display_name": None}]
            if url.endswith("/auth/v1/user"):
                return 200, {"id": NEW_ID, "email": EMAIL}
            self.fail(url)

        session = supabase_auth.AuthSession(
            user_id=NEW_ID,
            email=EMAIL,
            access_token="kept-token",
            plan=None,
            profile_id=NEW_ID,
        )
        with opened():
            result = supabase_auth.continue_traderdash_enrollment(session, transport=transport)
        self.assertEqual(result.plan, "free")
        self.assertEqual(sum(1 for call in calls if "provision_traderdash_free_self" in call[1]), 1)
        occupied = supabase_auth.AuthSession(
            user_id=NEW_ID,
            email=EMAIL,
            access_token="kept-token",
            plan=None,
            profile_id=NEW_ID,
        )

        def occupied_transport(method, url, headers, body):
            if "provision_traderdash_free_self" in url:
                raise AssertionError("existing entitlement was enrolled again")
            if "/entitlements" in url:
                return 200, [
                    {
                        "status": "active",
                        "starts_at": "2020-01-01T00:00:00Z",
                        "ends_at": None,
                        "products": {"code": "traderdash"},
                        "plans": {"code": "nordic"},
                    }
                ]
            if "/profiles" in url:
                return 200, [{"id": NEW_ID}]
            self.fail(url)

        with opened():
            left = supabase_auth.continue_traderdash_enrollment(occupied, transport=occupied_transport)
        self.assertIs(left, occupied)

    def test_existing_free_session_is_left_unchanged(self):
        session = supabase_auth.AuthSession(
            user_id=NEW_ID,
            email=EMAIL,
            access_token="kept-token",
            plan="free",
            profile_id=NEW_ID,
        )

        def transport(*args):
            raise AssertionError("enrollment was called")

        with opened():
            result = supabase_auth.continue_traderdash_enrollment(session, transport=transport)
        self.assertIs(result, session)

    def test_bridge_migration_is_unapplied_and_keeps_the_broad_function_closed(self):
        bridge_path = ROOT / "supabase" / "migrations" / "20261109140000_provision_traderdash_free_self.sql"
        broad_path = ROOT / "supabase" / "migrations" / "20261109110000_provision_traderdash_free.sql"
        bridge = bridge_path.read_bytes().replace(b"\r\n", b"\n")
        broad = broad_path.read_bytes().replace(b"\r\n", b"\n")
        digest = hashlib.sha256(bridge).hexdigest()
        manifest = (ROOT / "docs" / "production" / "MIGRATION_MANIFEST.md").read_text(encoding="utf-8")
        self.assertEqual(
            hashlib.sha256(broad).hexdigest(),
            "4e32c4e652b6d26b2cc73cc453438fcf0867b37eb84a1d2b25edd26361babbc7",
        )
        self.assertIn(digest, manifest)
        self.assertIn("NOT APPLIED", bridge.decode())
        self.assertNotIn("Production applied: YES", manifest)
        text = bridge.decode()
        self.assertIn("function public.provision_traderdash_free_self()", text)
        self.assertNotIn("provision_traderdash_free_self(target", text)
        self.assertNotIn("service_role", text)
        component = (ROOT / "captcha_component" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("provision_traderdash_free", component)
        self.assertNotIn("service_role", component)

    def test_partial_confirmed_account_enrolls_once_and_a_failed_enroll_stays_partial(self):
        secret = "partial-session-should-not-leak"
        store = {"rows": []}

        def transport(method, url, headers, body):
            if url.endswith("/auth/v1/verify"):
                self.assertEqual(body, {"type": "signup", "token_hash": "hash-partial"})
                self.assertNotIn(NEW_ID, json.dumps(body))
                return 200, {
                    "access_token": secret,
                    "refresh_token": "refresh-partial",
                    "user": {
                        "id": NEW_ID,
                        "email_confirmed_at": "2026-11-12T11:40:00Z",
                        "user_metadata": {"acknowledgement_version": registration.ACK_VERSION},
                    },
                }
            if url.endswith("/rest/v1/rpc/provision_traderdash_free_self"):
                self.assertEqual(body, {})
                if not store["rows"]:
                    store["rows"].append(
                        {
                            "status": "active",
                            "source": "signup",
                            "products": {"code": "traderdash"},
                            "plans": {"code": "free"},
                        }
                    )
                return 204, {}
            if "/profiles" in url:
                return 200, [{"id": NEW_ID}]
            if "/entitlements" in url:
                return 200, list(store["rows"])
            if url.endswith("/auth/v1/logout"):
                return 204, {}
            self.fail(url)

        stream = StringIO()
        with opened(), redirect_stderr(stream):
            first = registration.complete_verification("hash-partial", {"profile": True}, transport=transport)
            second = registration.complete_verification("hash-partial", {"profile": True}, transport=transport)
        self.assertTrue(first["access"])
        self.assertTrue(second["access"])
        self.assertEqual(first["papers"], 30)
        self.assertEqual(first["product_stage"]["free_entitlements"], 1)
        self.assertEqual(second["product_stage"]["source"], "signup")
        self.assertEqual(len(store["rows"]), 1)
        text = stream.getvalue()
        self.assertIn("REGISTRATION_VERIFIED", text)
        self.assertIn("PRODUCT_ENROLLMENT_REQUEST", text)
        self.assertIn("PRODUCT_ENROLLMENT_COMPLETED", text)
        self.assertIn("REGISTRATION_COMPLETED", text)
        self.assertLess(text.index("PRODUCT_ENROLLMENT_REQUEST"), text.index("PRODUCT_ENROLLMENT_COMPLETED"))
        self.assertLess(text.index("PRODUCT_ENROLLMENT_COMPLETED"), text.index("REGISTRATION_COMPLETED"))
        self.assertNotIn(secret, text)
        self.assertNotIn("refresh-partial", text)
        self.assertNotIn("hash-partial", text)
        self.assertNotIn(EMAIL, text)

        def refused(method, url, headers, body):
            if url.endswith("/auth/v1/verify"):
                return 200, {
                    "access_token": secret,
                    "user": {
                        "id": NEW_ID,
                        "email_confirmed_at": "2026-11-12T11:40:00Z",
                        "user_metadata": {"acknowledgement_version": registration.ACK_VERSION},
                    },
                }
            if "provision_traderdash_free_self" in url:
                return 500, {"message": "free plan missing"}
            if "/profiles" in url:
                return 200, [{"id": NEW_ID}]
            if "/entitlements" in url:
                return 200, []
            if url.endswith("/auth/v1/logout"):
                return 204, {}
            self.fail(url)

        failed = StringIO()
        with opened(), redirect_stderr(failed):
            report = registration.complete_verification("hash-partial", {"profile": True}, transport=refused)
        self.assertFalse(report["access"])
        self.assertEqual(report["papers"], 0)
        failed_text = failed.getvalue()
        self.assertIn("PRODUCT_ENROLLMENT_BLOCKED", failed_text)
        self.assertIn("REGISTRATION_PARTIAL", failed_text)
        self.assertNotIn("REGISTRATION_COMPLETED", failed_text)
        self.assertNotIn(secret, failed_text)

    def test_login_resume_completes_a_missing_free_entitlement_once(self):
        calls = []
        rows = []

        def transport(method, url, headers, body):
            calls.append(url)
            if "provision_traderdash_free_self" in url:
                self.assertEqual(body, {})
                rows.append(
                    {
                        "status": "active",
                        "source": "signup",
                        "starts_at": "2020-01-01T00:00:00Z",
                        "ends_at": None,
                        "products": {"code": "traderdash"},
                        "plans": {"code": "free"},
                    }
                )
                return 204, {}
            if "/entitlements" in url:
                return 200, list(rows)
            if "/profiles" in url:
                return 200, [{"id": NEW_ID, "display_name": None}]
            self.fail(url)

        session = supabase_auth.AuthSession(
            user_id=NEW_ID,
            email=EMAIL,
            access_token="login-token",
            plan=None,
            profile_id=NEW_ID,
            confirmed=True,
        )
        closed = {"TRADERDASH_AUTH_REGISTRATION": "disabled"}
        with opened(**closed):
            first = supabase_auth.continue_traderdash_enrollment(session, transport=transport)
            second = supabase_auth.continue_traderdash_enrollment(first, transport=transport)
        self.assertEqual(first.plan, "free")
        self.assertEqual(len(universes.stocks_for(first.plan)), 30)
        self.assertIs(second, first)
        self.assertEqual(sum("provision_traderdash_free_self" in url for url in calls), 1)
        self.assertEqual(len(rows), 1)

        def blocked(method, url, headers, body):
            if "provision_traderdash_free_self" in url:
                raise AssertionError("blocked plan was provisioned")
            if "/profiles" in url:
                return 200, [{"id": NEW_ID}]
            if "/entitlements" in url:
                return 200, [
                    {
                        "status": "active",
                        "source": source,
                        "starts_at": "2020-01-01T00:00:00Z",
                        "ends_at": None,
                        "products": {"code": "traderdash"},
                        "plans": {"code": plan},
                    }
                ]
            self.fail(url)

        for plan, source in (
            ("nordic", "subscription"),
            ("international", "purchase"),
            ("free", "subscription"),
        ):
            occupied = supabase_auth.AuthSession(
                user_id=NEW_ID,
                email=EMAIL,
                access_token="login-token",
                plan=None,
                profile_id=NEW_ID,
                confirmed=True,
            )
            with opened(**closed):
                left = supabase_auth.continue_traderdash_enrollment(occupied, transport=blocked)
            self.assertIsNone(left.plan)

        unconfirmed = supabase_auth.AuthSession(
            user_id=NEW_ID,
            email=EMAIL,
            access_token="login-token",
            plan=None,
            profile_id=NEW_ID,
            confirmed=False,
        )

        def refuse_unconfirmed(*args):
            raise AssertionError("unconfirmed login was provisioned")

        with opened(**closed):
            stayed = supabase_auth.continue_traderdash_enrollment(unconfirmed, transport=refuse_unconfirmed)
        self.assertIs(stayed, unconfirmed)

        duplicate = [
            {
                "status": "active",
                "starts_at": "2020-01-01T00:00:00Z",
                "ends_at": None,
                "products": {"code": "traderdash"},
                "plans": {"code": "free"},
            },
            {
                "status": "active",
                "starts_at": "2020-01-01T00:00:00Z",
                "ends_at": None,
                "products": {"code": "traderdash"},
                "plans": {"code": "free"},
            },
        ]
        self.assertIsNone(supabase_auth.plan_from_entitlements(duplicate))

    def test_controlled_signup_runbook_keeps_registration_closed(self):
        text = (ROOT / "docs" / "production" / "CONTROLLED_SIGNUP.md").read_text(encoding="utf-8")
        self.assertIn("TRADERDASH_AUTH_REGISTRATION", text)
        self.assertIn("traderdash-next", text)
        self.assertIn("traderdash-market", text)
        self.assertIn("provision_traderdash_free_self", text)
        self.assertIn("30 papirer", text)
        self.assertIn("## Stop", text)
        self.assertIn("disabled", text)
        self.assertNotIn("eyJ", text)
        self.assertNotIn("service_role", text)
        self.assertFalse(registration.registration_open({}))


def _ready() -> dict:
    return {
        "user_id": "",
        "target_ref": account_privacy.PRODUCTION_REF,
        "confirmed": True,
        "profile": True,
        "acknowledgement_version": registration.ACK_VERSION,
        "entitlements": [
            {"status": "active", "plan": "free", "product": "traderdash", "source": "signup"}
        ],
    }

"""Operations checks stay local and keep secrets out of the report."""

from __future__ import annotations

import json
import unittest
from io import StringIO
from pathlib import Path

import account_lifecycle
import operations
import stripe_test

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = "https://ajbsoudovxstlolojvte.supabase.co"
PRODUCTION = "https://wxvobyifckbpnqfbnlxl.supabase.co"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"


class OperationsTests(unittest.TestCase):
    def test_legacy_without_secrets_is_ready_and_closed(self):
        report = operations.assess({})
        self.assertEqual(report["liveness"], "ok")
        self.assertEqual(report["readiness"], "ready")
        self.assertEqual(report["auth_mode"], "legacy")
        self.assertFalse(report["flags"]["registration_open"])
        self.assertFalse(report["flags"]["stripe_updates"])
        self.assertFalse(report["flags"]["deletion_ui"])
        self.assertFalse(report["flags"]["deletion_execution"])
        self.assertFalse(report["contacts_production"])
        self.assertNotIn("eyJ", json.dumps(report))

    def test_pilot_readiness_hides_the_key_and_rejects_the_deleted_preview(self):
        ready = operations.assess(
            {
                "TRADERDASH_AUTH_MODE": "supabase_auth",
                "TRADERDASH_SUPABASE_URL": PRODUCTION,
                "TRADERDASH_SUPABASE_ANON_KEY": TOKEN,
            }
        )
        blob = json.dumps(ready)
        self.assertEqual(ready["readiness"], "ready")
        self.assertEqual(ready["auth_mode"], "supabase_auth")
        self.assertNotIn(TOKEN, blob)
        self.assertNotIn("eyJ", blob)
        blocked = operations.assess(
            {
                "TRADERDASH_AUTH_MODE": "supabase_auth",
                "TRADERDASH_SUPABASE_URL": PREVIEW,
                "TRADERDASH_SUPABASE_ANON_KEY": TOKEN,
            }
        )
        self.assertIn("deleted_preview", blocked["blockers"])
        self.assertEqual(blocked["readiness"], "not_ready")
        self.assertNotIn("ajbsoudovxstlolojvte", json.dumps(blocked))

    def test_missing_pilot_configuration_and_unknown_mode_fail_closed(self):
        missing = operations.assess({"TRADERDASH_AUTH_MODE": "supabase_auth"})
        self.assertIn("missing_configuration", missing["blockers"])
        self.assertEqual(missing["readiness"], "not_ready")
        unknown = operations.assess({"TRADERDASH_AUTH_MODE": "preview"})
        self.assertEqual(unknown["auth_mode"], "legacy")
        self.assertIn("auth_mode", unknown["blockers"])

    def test_unexpected_registration_or_stripe_switches_are_drift(self):
        report = operations.assess({"TRADERDASH_REGISTRATION": "open", "TRADERDASH_STRIPE": "enabled"})
        self.assertIn("registration_switch", report["blockers"])
        self.assertIn("stripe_switch", report["blockers"])
        self.assertEqual(report["readiness"], "not_ready")

    def test_code_flags_fail_closed_when_forced_on(self):
        original_stripe = stripe_test.ENTITLEMENT_UPDATES_ENABLED
        original_ui = account_lifecycle.DELETION_UI_ENABLED
        original_execution = account_lifecycle.DELETION_EXECUTION_ENABLED
        try:
            stripe_test.ENTITLEMENT_UPDATES_ENABLED = True
            account_lifecycle.DELETION_UI_ENABLED = True
            account_lifecycle.DELETION_EXECUTION_ENABLED = True
            report = operations.assess({})
        finally:
            stripe_test.ENTITLEMENT_UPDATES_ENABLED = original_stripe
            account_lifecycle.DELETION_UI_ENABLED = original_ui
            account_lifecycle.DELETION_EXECUTION_ENABLED = original_execution
        self.assertIn("stripe_code", report["blockers"])
        self.assertIn("deletion_ui", report["blockers"])
        self.assertIn("deletion_execution", report["blockers"])

    def test_logs_drop_secrets_and_unknown_categories(self):
        stream = StringIO()
        written = operations.log_event(
            "AUTH_FAILURE",
            _stream=stream,
            email="person@example.invalid",
            password="correct horse battery staple",
            token=TOKEN,
            database_url="postgresql://user:secret@db.example/traderdash",
            detail="postgresql://user:secret@db.example/traderdash eyJabc person@example.invalid",
        )
        text = stream.getvalue()
        self.assertNotIn("person@example.invalid", text)
        self.assertNotIn("correct horse", text)
        self.assertNotIn("eyJ", text)
        self.assertNotIn("postgresql://", text)
        self.assertEqual(written["password"], "[redacted]")
        unknown = operations.log_event("PASSWORD=hunter2", _stream=StringIO())
        self.assertEqual(unknown["category"], "UNHANDLED_APPLICATION_ERROR")
        self.assertNotIn("hunter2", json.dumps(unknown))

    def test_migration_comparison_does_not_query_or_echo_secrets(self):
        self.assertEqual(operations.migration_status(None)["status"], "not_checked")
        self.assertEqual(operations.migration_status(operations.EXPECTED_MIGRATIONS)["status"], "ok")
        drifted = operations.migration_status(("20261030160000",))
        self.assertEqual(drifted["status"], "drift")
        self.assertNotIn("20261030160000", json.dumps(drifted))
        rejected = operations.migration_status(("postgresql://db.example/app",))
        self.assertEqual(rejected["status"], "rejected")
        self.assertNotIn("postgresql", json.dumps(rejected))

    def test_release_validation_matches_the_repository(self):
        report = operations.release_validation(ROOT)
        self.assertTrue(report["ok"], report["findings"])
        self.assertFalse(report["contacts_production"])
        classes = {item["class"] for item in operations.DEPENDENCIES}
        self.assertEqual(classes, {"AUTOMATIC", "MANUAL", "INCIDENT-ONLY"})
        self.assertTrue(all(item["mutates"] is False for item in operations.DEPENDENCIES))

    def test_dependency_catalog_keeps_mail_and_restore_for_incidents(self):
        by_name = {item["name"]: item["class"] for item in operations.DEPENDENCIES}
        self.assertEqual(by_name["github_ci"], "AUTOMATIC")
        self.assertEqual(by_name["resend"], "MANUAL")
        self.assertEqual(by_name["recovery_mail"], "INCIDENT-ONLY")
        self.assertEqual(by_name["restore"], "INCIDENT-ONLY")
        self.assertEqual(by_name["preview_branch"], "INCIDENT-ONLY")

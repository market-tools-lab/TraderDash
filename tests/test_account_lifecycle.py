"""Deletion planning never mutates an account and never contacts Supabase."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

import account_lifecycle
import account_privacy
import stripe_test

ROOT = Path(__file__).resolve().parents[1]
LOCAL = "local-test"
AUTH = "33333333-3333-4333-8333-333333333333"
LEGACY = "legacy-local-1"
PILOT = "e8469788-5089-45f4-8a77-60440aa56fc7"


def auth_only(**extra):
    account = {
        "user_id": AUTH,
        "auth_user_id": AUTH,
        "profile": True,
        "entitlements": [{"status": "active", "source": "signup", "product": "traderdash"}],
        "target_ref": LOCAL,
    }
    account.update(extra)
    return account


class DeletionPlanTests(unittest.TestCase):
    def test_dry_run_does_not_mutate_and_stays_off(self):
        account = auth_only()
        before = copy.deepcopy(account)
        plan = account_lifecycle.plan_deletion(account)
        self.assertEqual(account, before)
        self.assertFalse(plan["deletion_allowed"])
        self.assertFalse(plan["execution_enabled"])
        self.assertFalse(plan["ui_enabled"])
        self.assertFalse(account_lifecycle.DELETION_UI_ENABLED)
        self.assertIn("execution_disabled", plan["blocking"])
        with self.assertRaises(account_lifecycle.LifecycleRejected):
            account_lifecycle.apply_deletion(account, confirmation="DELETE")
        self.assertEqual(account, before)

    def test_auth_only_migrated_and_legacy_only_are_distinct(self):
        auth_plan = account_lifecycle.plan_deletion(auth_only())
        migrated = account_lifecycle.plan_deletion(
            {
                "user_id": AUTH,
                "auth_user_id": AUTH,
                "profile": True,
                "legacy_user": {"user_id": LEGACY, "subscription_status": "free"},
                "legacy_link": {"legacy_user_id": LEGACY, "auth_user_id": AUTH},
                "entitlements": [{"status": "active", "source": "migration", "product": "traderdash"}],
                "target_ref": LOCAL,
            }
        )
        legacy = account_lifecycle.plan_deletion(
            {
                "user_id": LEGACY,
                "legacy_user": {"user_id": LEGACY, "subscription_status": "free"},
                "target_ref": LOCAL,
            }
        )
        self.assertEqual(auth_plan["account_mode"], "auth_only")
        self.assertEqual(auth_plan["actions"]["profiles"], "DELETE")
        self.assertEqual(auth_plan["actions"]["public.users"], "N/A")
        self.assertEqual(migrated["account_mode"], "migrated")
        self.assertEqual(migrated["actions"]["legacy_auth_links"], "DELETE")
        self.assertEqual(migrated["actions"]["public.users"], "ANONYMIZE")
        self.assertEqual(legacy["account_mode"], "legacy_only")
        self.assertEqual(legacy["actions"]["auth.users"], "N/A")
        self.assertEqual(legacy["profile_rows"], 0)

    def test_protected_identity_is_blocked_by_id_not_email(self):
        protected = account_lifecycle.plan_deletion(
            auth_only(user_id=PILOT, auth_user_id=PILOT, email="other@example.invalid")
        )
        self.assertTrue(protected["protected"])
        self.assertIn("protected", protected["blocking"])
        self.assertIn(PILOT, account_privacy.PROTECTED_IDS)
        renamed = account_lifecycle.plan_deletion(auth_only(email="the-real-address@example.invalid"))
        self.assertFalse(renamed["protected"])
        self.assertNotIn("protected", renamed["blocking"])

    def test_paid_duplicate_missing_and_wrong_environment_fail_closed(self):
        paid = account_lifecycle.plan_deletion(
            auth_only(
                subscription_status="active",
                entitlements=[{"status": "active", "source": "subscription", "product": "traderdash"}],
            )
        )
        duplicate = account_lifecycle.plan_deletion(
            auth_only(
                entitlements=[
                    {"status": "active", "source": "signup", "product": "traderdash"},
                    {"status": "active", "source": "manual", "product": "traderdash"},
                ]
            )
        )
        missing = account_lifecycle.plan_deletion(auth_only(target_ref=""))
        production = account_lifecycle.plan_deletion(auth_only(target_ref="wxvobyifckbpnqfbnlxl"))
        preview = account_lifecycle.plan_deletion(auth_only(target_ref="ajbsoudovxstlolojvte"))
        broken = account_lifecycle.plan_deletion(
            {"user_id": AUTH, "auth_user_id": AUTH, "legacy_user": {"user_id": LEGACY}, "target_ref": LOCAL}
        )
        self.assertEqual(paid["account_mode"], "future_paid")
        self.assertIn("active_paid_subscription", paid["blocking"])
        self.assertEqual(paid["actions"]["entitlements"], "RETAIN")
        self.assertEqual(paid["actions"]["subscription_reference"], "DETACH")
        self.assertEqual(paid["actions"]["stripe_events"], "RETAIN")
        self.assertIn("malformed", duplicate["blocking"])
        self.assertIn("missing_configuration", missing["blocking"])
        self.assertIn("environment", production["blocking"])
        self.assertIn("environment", preview["blocking"])
        self.assertIn("malformed", broken["blocking"])
        for plan in (paid, duplicate, missing, production, preview, broken):
            self.assertFalse(plan["deletion_allowed"])

    def test_ui_registration_and_stripe_stay_closed(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("Slet konto", app)
        self.assertIn("Ny konto oprettes ikke i denne loginvej.", app)
        self.assertFalse(stripe_test.ENTITLEMENT_UPDATES_ENABLED)
        self.assertFalse(account_lifecycle.DELETION_UI_ENABLED)

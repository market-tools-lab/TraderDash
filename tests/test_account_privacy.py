"""Export and local deletion never touch Production or a password hash."""

from __future__ import annotations

import unittest

import account_privacy

LOCAL_REF = "local-test"
USER = "22222222-2222-4222-8222-222222222222"


def ledger():
    return {
        "users": {
            USER: {
                "user_id": USER,
                "email": "local@example.invalid",
                "plan": "free",
                "subscription_status": "free",
                "created_at": "2026-11-04T12:00:00+00:00",
                "password_hash": "scrypt$not-a-real-hash",
                "access_token": "not-a-token",
            }
        },
        "entitlements": {USER: {"plan": "free", "status": "active"}},
        "links": {USER: {"status": "migrated"}},
    }


class AccountPrivacyTests(unittest.TestCase):
    def test_export_omits_the_hash_and_token(self):
        exported = account_privacy.export_account(ledger()["users"][USER])
        self.assertEqual(
            set(exported),
            {"user_id", "email", "plan", "subscription_status", "created_at"},
        )
        self.assertNotIn("password_hash", exported)
        self.assertNotIn("access_token", exported)

    def test_production_and_preview_are_refused(self):
        state = ledger()
        for ref in (account_privacy.PRODUCTION_REF, account_privacy.PREVIEW_REF, ""):
            with self.assertRaises(account_privacy.PrivacyRejected) as caught:
                account_privacy.delete_local(
                    state,
                    USER,
                    target_ref=ref,
                    confirmation=account_privacy.CONFIRMATION,
                )
            self.assertEqual(caught.exception.reason, "target")
        self.assertIn(USER, state["users"])

    def test_protected_pilot_id_is_refused(self):
        state = ledger()
        pilot = "e8469788-5089-45f4-8a77-60440aa56fc7"
        state["users"][pilot] = dict(state["users"][USER])
        with self.assertRaises(account_privacy.PrivacyRejected) as caught:
            account_privacy.delete_local(
                state,
                pilot,
                target_ref=LOCAL_REF,
                confirmation=account_privacy.CONFIRMATION,
            )
        self.assertEqual(caught.exception.reason, "protected")
        self.assertIn(pilot, state["users"])

    def test_local_delete_removes_user_entitlement_and_link(self):
        state = ledger()
        with self.assertRaises(account_privacy.PrivacyRejected):
            account_privacy.delete_local(state, USER, target_ref=LOCAL_REF, confirmation="no")
        self.assertEqual(
            account_privacy.delete_local(
                state,
                USER,
                target_ref=LOCAL_REF,
                confirmation=account_privacy.CONFIRMATION,
            ),
            "deleted",
        )
        self.assertNotIn(USER, state["users"])
        self.assertNotIn(USER, state["entitlements"])
        self.assertNotIn(USER, state["links"])

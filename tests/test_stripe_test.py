"""Stripe test mode. The production flag stays false, and no network is used."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import stripe_test
import universes
from tests.test_entitlement_access import granted_plan, paper_count

ROOT = Path(__file__).resolve().parents[1]
SECRET = "test-webhook-secret"
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
USER = "11111111-1111-4111-8111-111111111111"


def ledger():
    return {
        "users": {USER: {"email": "pilot@example.invalid"}},
        "entitlements": {USER: {"plan": "free", "status": "active", "ends_at": None}},
        "events": {},
    }


def raw_event(event_id: str, event_type: str, obj: dict) -> str:
    return json.dumps({"id": event_id, "type": event_type, "data": {"object": obj}})


def signed(raw: str, *, timestamp: int | None = None, secret: str = SECRET) -> str:
    stamp = int(NOW.timestamp()) if timestamp is None else timestamp
    return stripe_test.sign(raw, secret, stamp)


class StripeTestModeTests(unittest.TestCase):
    def test_production_flag_and_webhook_stay_disabled(self):
        self.assertFalse(stripe_test.ENTITLEMENT_UPDATES_ENABLED)
        source = (ROOT / "supabase" / "functions" / "stripe-webhook" / "index.ts").read_text(encoding="utf-8")
        self.assertIn("const ENTITLEMENT_UPDATES_ENABLED = false;", source)

    def test_checkout_is_built_on_the_server_and_stays_off_by_default(self):
        self.assertIsNone(stripe_test.build_checkout(USER, "nordic", enabled=False))
        body = stripe_test.build_checkout(USER, "nordic", enabled=True)
        self.assertEqual(body["client_reference_id"], USER)
        self.assertEqual(body["metadata"]["user_id"], USER)
        self.assertNotIn("email", body["metadata"])
        self.assertNotIn("secret", json.dumps(body))
        with self.assertRaises(ValueError):
            stripe_test.build_checkout("not-a-user", "nordic", enabled=True)

    def test_bad_signature_changes_nothing(self):
        state = ledger()
        before = json.dumps(state)
        raw = raw_event("evt_bad", "checkout.session.completed", {"metadata": {"plan_code": "nordic", "user_id": USER}})
        result = stripe_test.apply_event(state, raw, "t=1,v1=deadbeef", SECRET, updates_enabled=True, now=NOW)
        self.assertEqual(result.reason, "bad_signature")
        self.assertEqual(json.dumps(state), before)

    def test_disabled_flag_does_not_store_or_change_a_valid_event(self):
        state = ledger()
        raw = raw_event(
            "evt_off",
            "checkout.session.completed",
            {"client_reference_id": USER, "metadata": {"user_id": USER, "plan_code": "nordic"}},
        )
        result = stripe_test.apply_event(state, raw, signed(raw), SECRET, now=NOW)
        self.assertEqual(result.reason, "updates_disabled")
        self.assertEqual(state["entitlements"][USER]["plan"], "free")
        self.assertEqual(state["events"], {})

    def test_nordic_payment_grants_seventy_nine_papers_once(self):
        state = ledger()
        raw = raw_event(
            "evt_nordic",
            "checkout.session.completed",
            {"client_reference_id": USER, "metadata": {"user_id": USER, "plan_code": "nordic", "email": "other@example.invalid"}},
        )
        first = stripe_test.apply_event(state, raw, signed(raw), SECRET, updates_enabled=True, now=NOW)
        second = stripe_test.apply_event(state, raw, signed(raw), SECRET, updates_enabled=True, now=NOW)
        row = {"status": "active", "plan_code": "nordic", "ends_at": None}
        self.assertTrue(first.changed)
        self.assertEqual(second.reason, "duplicate")
        self.assertFalse(second.changed)
        self.assertEqual(state["entitlements"][USER]["plan"], "nordic")
        self.assertEqual(paper_count(row), 79)
        self.assertEqual(len(universes.stocks_for("nordic")), 79)

    def test_past_due_suspends_access(self):
        state = ledger()
        state["entitlements"][USER] = {"plan": "nordic", "status": "active", "ends_at": None}
        raw = raw_event(
            "evt_due",
            "customer.subscription.updated",
            {"metadata": {"user_id": USER}, "status": "past_due"},
        )
        result = stripe_test.apply_event(state, raw, signed(raw), SECRET, updates_enabled=True, now=NOW)
        self.assertTrue(result.changed)
        self.assertEqual(state["entitlements"][USER]["status"], "suspended")
        self.assertEqual(paper_count({"status": "suspended", "plan_code": "nordic", "ends_at": None}), 0)

    def test_canceled_with_a_future_end_keeps_access(self):
        state = ledger()
        state["entitlements"][USER] = {"plan": "nordic", "status": "active", "ends_at": None}
        future = NOW + timedelta(days=10)
        raw = raw_event(
            "evt_cancel",
            "customer.subscription.updated",
            {
                "metadata": {"user_id": USER},
                "status": "canceled",
                "current_period_end": int(future.timestamp()),
            },
        )
        stripe_test.apply_event(state, raw, signed(raw), SECRET, updates_enabled=True, now=NOW)
        ends_at = state["entitlements"][USER]["ends_at"]
        self.assertEqual(state["entitlements"][USER]["status"], "active")
        self.assertEqual(
            granted_plan({"status": "active", "plan_code": "nordic", "ends_at": ends_at}, NOW),
            "nordic",
        )
        self.assertIsNone(
            granted_plan({"status": "active", "plan_code": "nordic", "ends_at": ends_at}, future + timedelta(seconds=1))
        )

    def test_email_alone_does_not_create_a_user(self):
        state = ledger()
        raw = raw_event(
            "evt_email",
            "checkout.session.completed",
            {"customer_email": "new@example.invalid", "metadata": {"email": "new@example.invalid", "plan_code": "nordic"}},
        )
        result = stripe_test.apply_event(state, raw, signed(raw), SECRET, updates_enabled=True, now=NOW)
        self.assertEqual(result.reason, "unknown_user")
        self.assertEqual(set(state["users"]), {USER})
        self.assertEqual(state["events"], {})

"""Fail-closed reading of an entitlement row.

TraderDash still decides access from the legacy plan. This module records
the preview rule that a later iteration can connect to the app. It does not
call Supabase and it does not change the login.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import universes

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def granted_plan(row: dict | None, now: datetime = NOW) -> str | None:
    if row is None:
        return None
    if row.get("status") != "active":
        return None
    ends_at = row.get("ends_at")
    if ends_at is not None and ends_at <= now:
        return None
    plan = row.get("plan_code")
    if plan not in ("free", "nordic", "international"):
        return None
    return plan


def paper_count(row: dict | None, now: datetime = NOW) -> int:
    plan = granted_plan(row, now)
    if plan is None:
        return 0
    return len(universes.stocks_for(plan))


class EntitlementAccessTests(unittest.TestCase):
    def test_free_universe_has_thirty_papers(self):
        self.assertEqual(len(universes.stocks_for("free")), 30)

    def test_active_free_entitlement_grants_thirty_papers(self):
        row = {"status": "active", "plan_code": "free", "ends_at": None}
        self.assertEqual(paper_count(row), 30)

    def test_missing_revoked_suspended_and_expired_grant_nothing(self):
        past = NOW - timedelta(hours=1)
        earlier = NOW - timedelta(hours=2)
        closed = [
            None,
            {"status": "revoked", "plan_code": "free", "ends_at": None},
            {"status": "suspended", "plan_code": "free", "ends_at": None},
            {"status": "expired", "plan_code": "free", "ends_at": None},
            {"status": "active", "plan_code": "free", "ends_at": past},
            {
                "status": "active",
                "plan_code": "international",
                "ends_at": past,
            },
            {"status": "active", "plan_code": "unknown", "ends_at": None},
        ]
        for row in closed:
            self.assertEqual(paper_count(row), 0)
        self.assertEqual(
            paper_count(
                {"status": "active", "plan_code": "free", "ends_at": earlier}
            ),
            0,
        )

    def test_open_ended_or_future_end_keeps_the_plan(self):
        future = NOW + timedelta(days=1)
        self.assertEqual(
            granted_plan(
                {"status": "active", "plan_code": "nordic", "ends_at": future}
            ),
            "nordic",
        )
        self.assertEqual(
            granted_plan(
                {"status": "active", "plan_code": "free", "ends_at": None}
            ),
            "free",
        )

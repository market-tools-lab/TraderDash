"""Pilot migration contract. No network and no secrets."""

from __future__ import annotations

import inspect
import unittest
import uuid
from pathlib import Path

import pilot_fixture
import pilot_migration
import supabase_auth
import universes

ROOT = Path(__file__).resolve().parents[1]
REF = pilot_migration.PREVIEW_PROJECT_REF
URL = pilot_migration.PREVIEW_API_URL


def _request(legacy_id: str = "legacy-1", auth_id: str = "auth-1", **kwargs) -> pilot_migration.MigrationRequest:
    values = {
        "project_ref": REF,
        "api_url": URL,
        "legacy_user_id": legacy_id,
        "auth_user_id": auth_id,
        "migration_reference": "pilot-test",
    }
    values.update(kwargs)
    return pilot_migration.MigrationRequest(**values)


def _pair(gateway: pilot_migration.RecordingGateway, legacy_id: str, auth_id: str, plan: str, status: str, auth_email: str | None = None) -> None:
    email = f"{legacy_id}@example.invalid"
    gateway.legacy[legacy_id] = pilot_migration.LegacyAccount(legacy_id, email, plan, status)
    gateway.auth[auth_id] = pilot_migration.AuthAccount(auth_id, auth_email or email)


class MappingTests(unittest.TestCase):
    def test_known_grants(self):
        self.assertEqual(pilot_migration.map_legacy("free", "free").entitlement_status, "active")
        self.assertEqual(pilot_migration.map_legacy("free", "free").plan_code, "free")
        self.assertTrue(pilot_migration.map_legacy("free", "active").grants_access)
        self.assertEqual(pilot_migration.map_legacy("nordic", "active").plan_code, "nordic")
        self.assertEqual(pilot_migration.map_legacy("international", "active").plan_code, "international")

    def test_closed_statuses_grant_nothing(self):
        for status in ("trialing", "past_due", "cancelled", "canceled", "unpaid", "revoked", "suspended", "incomplete", "expired"):
            mapped = pilot_migration.map_legacy("nordic", status)
            self.assertFalse(mapped.grants_access, status)
            self.assertNotEqual(mapped.entitlement_status, "active", status)
        future_end = pilot_migration.map_legacy("international", "cancelled")
        self.assertFalse(future_end.grants_access)

    def test_unknown_values_are_rejected(self):
        self.assertEqual(pilot_migration.map_legacy("gold", "active").reason, "unknown_plan")
        self.assertEqual(pilot_migration.map_legacy("free", None).reason, "unknown_status")
        self.assertEqual(pilot_migration.map_legacy("free", "comped").reason, "unknown_status")
        self.assertEqual(pilot_migration.map_legacy("nordic", "free").reason, "inconsistent_status")

    def test_universe_sizes_stay_on_the_existing_plans(self):
        self.assertEqual(len(universes.stocks_for("free")), 30)
        self.assertEqual(len(universes.stocks_for("nordic")), 79)
        self.assertEqual(len(universes.stocks_for("international")), 159)


class TargetTests(unittest.TestCase):
    def test_missing_and_wrong_targets_make_no_gateway_call(self):
        gateway = pilot_migration.RecordingGateway()

        def guarded(ref, url):
            try:
                pilot_migration.migrate(_request(project_ref=ref, api_url=url), gateway)
            except pilot_migration.TargetRejected:
                return
            self.fail("target was accepted")

        guarded(None, URL)
        guarded("", URL)
        guarded(REF, None)
        guarded(REF, "")
        guarded("other-project", URL)
        guarded(REF, "https://example.supabase.co")
        self.assertEqual(gateway.writes, [])
        self.assertEqual(gateway.legacy, {})


class MigrationTests(unittest.TestCase):
    def test_free_nordic_and_international_grants(self):
        expected = {"free": 30, "nordic": 79, "international": 159}
        for plan, status in (("free", "free"), ("nordic", "active"), ("international", "active")):
            gateway = pilot_migration.RecordingGateway()
            _pair(gateway, f"legacy-{plan}", f"auth-{plan}", plan, status)
            report = pilot_migration.migrate(_request(f"legacy-{plan}", f"auth-{plan}"), gateway)
            self.assertTrue(report.grants_access)
            self.assertEqual(report.plan_code, plan)
            self.assertEqual(report.entitlement_status, "active")
            self.assertEqual(len(universes.stocks_for(plan)), expected[plan])
            self.assertTrue(supabase_auth.plan_from_entitlements([
                {"status": "active", "starts_at": "2020-01-01T00:00:00Z", "ends_at": None,
                 "products": {"code": "traderdash"}, "plans": {"code": plan}}
            ]))

    def test_negative_statuses_do_not_grant_access(self):
        samples = (
            ("past_due", "suspended"),
            ("cancelled", "expired"),
            ("suspended", "suspended"),
            ("revoked", "revoked"),
            ("unpaid", "revoked"),
            ("trialing", "suspended"),
        )
        for status, entitlement_status in samples:
            gateway = pilot_migration.RecordingGateway()
            _pair(gateway, f"legacy-{status}", f"auth-{status}", "nordic", status)
            report = pilot_migration.migrate(
                _request(f"legacy-{status}", f"auth-{status}", ends_at=object()),
                gateway,
            )
            self.assertEqual(report.outcome, "closed")
            self.assertFalse(report.grants_access)
            self.assertEqual(report.entitlement_status, entitlement_status)
            self.assertTrue(report.ignored_ends_at)
            self.assertIsNone(supabase_auth.plan_from_entitlements([
                {"status": entitlement_status, "starts_at": "2020-01-01T00:00:00Z", "ends_at": None,
                 "products": {"code": "traderdash"}, "plans": {"code": "nordic"}}
            ]))

    def test_rejections_write_nothing(self):
        present = pilot_migration.RecordingGateway()
        _pair(present, "legacy-ok", "auth-ok", "free", "free")
        missing_legacy = pilot_migration.migrate(_request("legacy-missing", "auth-ok"), present)
        missing_auth = pilot_migration.migrate(_request("legacy-ok", "auth-missing"), present)
        mismatch = pilot_migration.migrate(_request("legacy-ok", "auth-ok"), _mismatch_gateway())
        self.assertEqual(missing_legacy.reason, "missing_legacy")
        self.assertEqual(missing_auth.reason, "missing_auth")
        self.assertEqual(mismatch.reason, "email_mismatch")
        self.assertFalse(missing_legacy.wrote or missing_auth.wrote or mismatch.wrote)
        self.assertEqual(present.writes, [])
        self.assertEqual(_mismatch_gateway().writes, [])
        unknown = pilot_migration.RecordingGateway()
        _pair(unknown, "legacy-x", "auth-x", "gold", "active")
        report = pilot_migration.migrate(_request("legacy-x", "auth-x"), unknown)
        self.assertEqual(report.reason, "unknown_plan")
        self.assertEqual(unknown.writes, [])
        unknown_status = pilot_migration.RecordingGateway()
        _pair(unknown_status, "legacy-y", "auth-y", "free", "comp")
        report = pilot_migration.migrate(_request("legacy-y", "auth-y"), unknown_status)
        self.assertEqual(report.reason, "unknown_status")
        self.assertEqual(unknown_status.writes, [])

    def test_second_run_is_idempotent(self):
        gateway = pilot_migration.RecordingGateway()
        _pair(gateway, "legacy-1", "auth-1", "free", "free")
        request = _request()
        first = pilot_migration.migrate(request, gateway)
        second = pilot_migration.migrate(request, gateway)
        self.assertTrue(first.wrote)
        self.assertEqual(second.outcome, "already_migrated")
        self.assertFalse(second.wrote)
        self.assertEqual(len([write for write in gateway.writes if write["kind"] == "link"]), 1)
        self.assertEqual(len([write for write in gateway.writes if write["kind"] == "entitlement"]), 1)
        active = [row for row in gateway.entitlements.values() if row["status"] == "active"]
        self.assertEqual(len(active), 1)

    def test_dry_run_writes_nothing(self):
        gateway = pilot_migration.RecordingGateway()
        _pair(gateway, "legacy-1", "auth-1", "international", "active")
        report = pilot_migration.migrate(_request(), gateway, dry_run=True)
        self.assertEqual(report.outcome, "dry_run")
        self.assertEqual(report.plan_code, "international")
        self.assertTrue(report.grants_access)
        self.assertFalse(report.wrote)
        self.assertEqual(gateway.writes, [])
        self.assertEqual(gateway.links_by_legacy, {})

    def test_password_is_not_part_of_the_migration(self):
        source = inspect.getsource(pilot_migration.migrate)
        module = (ROOT / "pilot_migration.py").read_text(encoding="utf-8")
        self.assertNotIn("password_hash", pilot_migration.LEGACY_FIELDS)
        self.assertNotIn("password_hash", source)
        self.assertNotIn("insert into auth.users", module.lower())
        self.assertNotIn("delete from public.users", module.lower())
        report = pilot_migration.migrate(_request(), pilot_migration.RecordingGateway()).public_dict()
        self.assertNotIn("password", "".join(report))
        self.assertNotIn("email", report)

    def test_sql_contains_no_credentials(self):
        gateway = pilot_migration.RecordingGateway()
        auth_id = str(uuid.uuid4())
        _pair(gateway, "legacy-1", auth_id, "free", "free")
        report = pilot_migration.migrate(_request("legacy-1", auth_id), gateway)
        sql = "\n".join(pilot_migration.sql_for_writes(gateway.writes))
        self.assertTrue(report.wrote)
        self.assertIn("legacy_auth_links", sql)
        self.assertIn("entitlements", sql)
        self.assertNotIn("password", sql)
        self.assertNotIn("@", sql)


def _mismatch_gateway() -> pilot_migration.RecordingGateway:
    gateway = pilot_migration.RecordingGateway()
    gateway.legacy["legacy-ok"] = pilot_migration.LegacyAccount("legacy-ok", "one@example.invalid", "free", "free")
    gateway.auth["auth-ok"] = pilot_migration.AuthAccount("auth-ok", "other@example.invalid")
    return gateway


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.sql = (ROOT / "supabase" / "migrations" / "20261104140000_legacy_auth_links.sql").read_text(encoding="utf-8")

    def test_link_table_is_closed_and_reversible(self):
        self.assertIn("create table public.legacy_auth_links", self.sql)
        self.assertIn("auth_user_id uuid not null references auth.users (id) on delete cascade", self.sql)
        self.assertIn("legacy_auth_links_legacy_user_id_key", self.sql)
        self.assertIn("legacy_auth_links_auth_user_id_key", self.sql)
        self.assertIn("enable row level security", self.sql)
        self.assertIn("force row level security", self.sql)
        self.assertIn("revoke all on table public.legacy_auth_links from public, anon, authenticated", self.sql)
        self.assertNotIn("password", self.sql)
        self.assertNotIn("email", self.sql.lower())
        self.assertIn("drop table public.legacy_auth_links", self.sql)
        self.assertNotIn("grant ", self.sql.lower())


class FixtureTests(unittest.TestCase):
    def test_fixture_rejects_real_addresses_and_the_standing_user(self):
        auth_id = str(uuid.uuid4())
        digest = "$2b$10$" + "a" * 53
        with self.assertRaises(pilot_fixture.FixtureRejected):
            pilot_fixture.auth_user_sql(auth_id, "person@example.com", digest)
        with self.assertRaises(pilot_fixture.FixtureRejected):
            pilot_fixture.cleanup_sql("63ffe985-0e7e-48bd-b41b-d1741330257a", "legacy-mig-a")
        sql = "\n".join(pilot_fixture.auth_user_sql(auth_id, "markettools-mig-a@example.invalid", digest))
        self.assertNotIn("password'", sql)
        self.assertIn("markettools-mig-a@example.invalid", sql)


class AppBoundaryTests(unittest.TestCase):
    def test_app_has_no_migration_control(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("pilot_migration", source)
        self.assertNotIn("legacy_auth_links", source)

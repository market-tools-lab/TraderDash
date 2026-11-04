"""The production pilot inspection is redacted and cannot write."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import pilot_readiness

ROOT = Path(__file__).resolve().parents[1]
EMAIL = pilot_readiness.REFERENCE_EMAIL
LEGACY = {
    "user_id": "legacy-pilot",
    "email": EMAIL,
    "plan": "free",
    "subscription_status": "free",
}


class ConfirmationTests(unittest.TestCase):
    def test_queries_stay_uncalled_without_confirmation(self):
        def fail(statement, params):
            raise AssertionError(statement)

        with self.assertRaises(pilot_readiness.ReadinessRejected) as raised:
            pilot_readiness.dry_run(fail, fail, fail, confirmation="no")
        self.assertEqual(str(raised.exception), "production confirmation is required")

    def test_more_than_one_legacy_row_stops_before_auth(self):
        calls = []

        def legacy(statement, params):
            calls.append("legacy")
            return [dict(LEGACY), dict(LEGACY, user_id="other")]

        def later(statement, params):
            calls.append("later")
            return []

        with self.assertRaises(pilot_readiness.ReadinessRejected):
            pilot_readiness.dry_run(
                legacy,
                later,
                later,
                confirmation=pilot_readiness.CONFIRMATION,
            )
        self.assertEqual(calls, ["legacy"])

    def test_command_never_contacts_production(self):
        self.assertEqual(pilot_readiness.main(["--apply"]), 2)
        source = (ROOT / "pilot_readiness.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("os.environ", source)
        self.assertNotIn("psycopg", source)
        self.assertNotIn("sqlite3", source)
        for statement in (
            pilot_readiness.LEGACY_SELECT,
            pilot_readiness.AUTH_SELECT,
            pilot_readiness.LINK_SELECT,
        ):
            folded = statement.lower()
            for word in ("insert ", "update ", "delete ", "drop ", "alter ", "password"):
                self.assertNotIn(word, folded)
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("pilot_readiness", app)


class ReportTests(unittest.TestCase):
    def test_known_free_account_is_redacted_and_idempotent(self):
        secret = {**LEGACY, "password_hash": "scrypt$16384$secret"}
        with self.assertRaises(pilot_readiness.ReadinessRejected) as raised:
            pilot_readiness.inspect_rows(secret, [], [])
        self.assertNotIn("scrypt", str(raised.exception))

        def query(statement, params):
            if "public.users" in statement:
                return [dict(LEGACY)]
            if "auth.users" in statement:
                return [{"id": "auth-1", "email": EMAIL}]
            return []

        first = pilot_readiness.dry_run(query, query, query, confirmation=pilot_readiness.CONFIRMATION)
        second = pilot_readiness.dry_run(query, query, query, confirmation=pilot_readiness.CONFIRMATION)
        self.assertEqual(first.public_dict(), second.public_dict())
        report = first.public_dict()
        self.assertEqual(report["outcome"], "ready")
        self.assertEqual(report["legacy_user_id"], "legacy-pilot")
        self.assertEqual(report["plan"], "free")
        self.assertEqual(report["subscription_status"], "free")
        self.assertEqual(report["entitlement_plan"], "free")
        self.assertEqual(report["entitlement_status"], "active")
        self.assertTrue(report["grants_access"])
        self.assertEqual(report["expected_papers"], 30)
        self.assertTrue(report["auth_identity_exists"])
        self.assertFalse(report["link_exists"])
        self.assertFalse(report["wrote"])
        self.assertNotIn("password", report)
        self.assertNotIn(EMAIL, report.values())

    def test_existing_link_and_missing_auth_are_distinct(self):
        linked = pilot_readiness.inspect_rows(
            LEGACY,
            [{"id": "auth-1", "email": EMAIL}],
            [{"legacy_user_id": "legacy-pilot", "auth_user_id": "auth-1", "migration_status": "migrated"}],
        )
        self.assertEqual(linked.outcome, "already_linked")
        self.assertFalse(linked.wrote)
        missing = pilot_readiness.inspect_rows(LEGACY, [], [])
        self.assertEqual(missing.outcome, "missing_auth")
        conflict = pilot_readiness.inspect_rows(
            LEGACY,
            [{"id": "auth-1", "email": EMAIL}],
            [{"legacy_user_id": "legacy-pilot", "auth_user_id": "auth-2", "migration_status": "migrated"}],
        )
        self.assertEqual(conflict.outcome, "link_conflict")
        self.assertFalse(conflict.wrote)


class PackageTests(unittest.TestCase):
    def test_manifest_hashes_match_the_files(self):
        manifest = (ROOT / "docs" / "production" / "MIGRATION_MANIFEST.md").read_text(encoding="utf-8")
        # Checksums recorded from the Windows working copies when the files were applied.
        recorded = {
            "20261030160000_accounts.sql": "5f3118ea88414be5ee600ed6d966d05a5800bb40410a3a8752294c4a4ae87235",
            "20261104110000_identity_catalog.sql": "fdf53d809b5811baf43afe577be9c86e5fe475c5e1fab20b3bacfb6421573951",
            "20261104140000_legacy_auth_links.sql": "671d8e9e7cd6d6e87b3e668b3b3bf5048a817093f55e07dd75c922f018c3a0c9",
        }
        # Git stores the same text with LF. Linux CI checks that form out directly.
        repository = {
            "20261030160000_accounts.sql": "31ce87d64216c4c0763842a73e6c74ca5e70712a7d3eff1ff6d0134a30f3b5e3",
            "20261104110000_identity_catalog.sql": "52b0b678d21ef94ba051414f0bcd56cab9c2fe27bed86f09cb5fab2247d071f0",
            "20261104140000_legacy_auth_links.sql": "b8dd0aea069c89a70b0c358dfab742de52719529511b8296b7f59ccb424c4261",
        }
        for name, digest in repository.items():
            body = (ROOT / "supabase" / "migrations" / name).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(hashlib.sha256(body).hexdigest(), digest)
            self.assertIn(recorded[name], manifest)
        rollback = (ROOT / "docs" / "production" / "ROLLBACK.sql").read_text(encoding="utf-8").lower()
        self.assertIn("not for execution", rollback)
        self.assertNotIn("drop table if exists public.users", rollback)
        self.assertNotIn("delete from", rollback)

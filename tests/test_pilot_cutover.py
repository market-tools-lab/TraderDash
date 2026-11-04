"""The named pilot is copied without production data or a password."""

from __future__ import annotations

import unittest
import uuid

import pilot_cutover
import pilot_migration


class PilotCutoverTests(unittest.TestCase):
    def test_preview_fields_are_only_the_migration_input(self):
        fields = pilot_cutover.preview_fields()
        self.assertEqual(set(fields), set(pilot_migration.LEGACY_FIELDS))
        self.assertNotIn("password_hash", fields)
        self.assertNotIn(pilot_cutover.REFERENCE_LABEL, fields.values())
        self.assertEqual(fields["plan"], "free")
        self.assertEqual(fields["subscription_status"], "free")

    def test_forbidden_fields_and_the_reference_address_are_rejected(self):
        fields = pilot_cutover.preview_fields()
        for extra in ("password_hash", "password", "database_url", "access_token", "session"):
            with self.assertRaises(pilot_migration.TargetRejected):
                pilot_cutover.accept_fields({**fields, extra: "not-used"})
        leaked = dict(fields, email=pilot_cutover.REFERENCE_LABEL)
        with self.assertRaises(pilot_migration.TargetRejected):
            pilot_cutover.accept_fields(leaked)

    def test_cutover_grants_free_and_writes_no_secret(self):
        auth_id = str(uuid.uuid4())
        request, legacy, auth = pilot_cutover.request_for(auth_id)
        gateway = pilot_migration.RecordingGateway()
        gateway.legacy[legacy.user_id] = legacy
        gateway.auth[auth.user_id] = auth
        dry = pilot_migration.migrate(request, gateway, dry_run=True)
        self.assertEqual(dry.outcome, "dry_run")
        self.assertFalse(dry.wrote)
        self.assertEqual(gateway.writes, [])
        report = pilot_migration.migrate(request, gateway)
        sql = "\n".join(pilot_migration.sql_for_writes(gateway.writes))
        self.assertTrue(report.grants_access)
        self.assertEqual(report.plan_code, "free")
        self.assertEqual(report.entitlement_status, "active")
        self.assertNotIn("password", sql)
        self.assertNotIn(pilot_cutover.REFERENCE_LABEL, sql)
        self.assertNotIn(pilot_cutover.PREVIEW_EMAIL, sql)
        self.assertNotIn("@", sql)
        self.assertIn(pilot_cutover.PREVIEW_LEGACY_ID, sql)
        self.assertIn("pilot-i7", sql)

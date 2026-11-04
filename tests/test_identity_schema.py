"""Static checks for the prepared identity migration.

These tests read SQL from disk. They do not open a database connection and
they do not contact Supabase. The integration cases at the bottom are
skipped until a non-production database is chosen.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261104110000_identity_catalog.sql"
ACCOUNTS = ROOT / "supabase" / "migrations" / "20261030160000_accounts.sql"

TABLES = ("products", "plans", "profiles", "entitlements")


def _compact(sql: str) -> str:
    without_comments = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"\s+", " ", without_comments).strip().lower()


class IdentitySchemaFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.compact = _compact(cls.sql)

    def test_migration_is_marked_not_applied(self):
        self.assertTrue(MIGRATION.is_file())
        self.assertIn("NOT APPLIED", self.sql)
        self.assertNotIn("database_url", self.compact)
        self.assertNotIn("alter role", self.compact)

    def test_only_the_four_catalog_tables_are_created(self):
        created = re.findall(r"create table public\.(\w+)", self.compact)
        self.assertEqual(created, list(TABLES))

    def test_no_credential_or_mail_column_is_declared(self):
        self.assertNotIn("password", self.compact)
        self.assertNotIn("email", self.compact)
        for name in ("legacy_user_links", "audit_events", "stripe_customers", "subscriptions", "purchases"):
            self.assertNotIn(name, self.compact)
        self.assertNotIn("alter table public.users", self.compact)
        self.assertNotIn("alter table public.stripe_events", self.compact)
        self.assertNotIn("java-co", self.compact)

    def test_identity_uses_auth_users(self):
        self.assertIn("references auth.users (id) on delete cascade", self.compact)
        self.assertEqual(self.compact.count("references auth.users (id)"), 2)
        self.assertIn("insert into public.profiles (id) values (new.id)", self.compact)

    def test_status_and_active_entitlement_are_closed(self):
        self.assertIn("status text not null", self.compact)
        self.assertNotIn("status text not null default", self.compact)
        self.assertIn("status in ('active', 'expired', 'revoked', 'suspended')", self.compact)
        self.assertIn("where status = 'active'", self.compact)
        self.assertIn("ends_at is null or ends_at > starts_at", self.compact)
        self.assertIn("entitlements_reject_plan_product_mismatch", self.compact)

    def test_profile_trigger_does_not_grant_an_entitlement(self):
        body = re.search(
            r"function public\.handle_new_user\(\).*?\$\$(.*?)\$\$",
            self.compact,
        )
        self.assertIsNotNone(body)
        self.assertIn("insert into public.profiles (id)", body.group(1))
        self.assertNotIn("entitlements", body.group(1))

    def test_rls_is_enabled_and_forced(self):
        for table in TABLES:
            self.assertIn(f"alter table public.{table} enable row level security", self.compact)
            self.assertIn(f"alter table public.{table} force row level security", self.compact)
            self.assertIn(
                f"revoke all on table public.{table} from public, anon, authenticated",
                self.compact,
            )

    def test_authenticated_can_read_but_cannot_write_entitlements(self):
        grants = re.findall(r"grant [^;]+;", self.compact)
        self.assertEqual(
            grants,
            [
                "grant select on table public.products to authenticated;",
                "grant select on table public.plans to authenticated;",
                "grant select on table public.profiles to authenticated;",
                "grant update (display_name) on table public.profiles to authenticated;",
                "grant select on table public.entitlements to authenticated;",
            ],
        )
        policies = re.findall(
            r"create policy (\w+) on public\.entitlements for (\w+)",
            self.compact,
        )
        self.assertEqual(policies, [("entitlements_select_own", "select")])
        self.assertIn("using (user_id = auth.uid())", self.compact)

    def test_profile_update_is_limited_to_the_owner(self):
        self.assertIn(
            "create policy profiles_select_own on public.profiles for select to authenticated using (id = auth.uid())",
            self.compact,
        )
        self.assertIn(
            "create policy profiles_update_own on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid())",
            self.compact,
        )
        self.assertIn("profile id is immutable", self.compact)
        self.assertNotIn("create policy profiles_insert", self.compact)

    def test_catalog_is_readable_and_not_writable(self):
        self.assertIn(
            "create policy products_select_active on public.products for select to authenticated using (active)",
            self.compact,
        )
        self.assertIn(
            "create policy plans_select_active on public.plans for select to authenticated using (active)",
            self.compact,
        )
        for table in ("products", "plans"):
            self.assertNotIn(f"on public.{table} for insert", self.compact)
            self.assertNotIn(f"on public.{table} for update", self.compact)
            self.assertNotIn(f"on public.{table} for delete", self.compact)

    def test_seed_is_traderdash_only(self):
        self.assertIn("('traderdash', 'traderdash')", self.compact)
        for code, rank, billing in (
            ("free", "0", "free"),
            ("nordic", "1", "recurring"),
            ("international", "2", "recurring"),
        ):
            self.assertIn(
                f"select id, '{code}', '{code}', {rank}, '{billing}' from public.products where code = 'traderdash'",
                self.compact,
            )

    def test_existing_accounts_migration_is_unchanged(self):
        previous = ACCOUNTS.read_text(encoding="utf-8").lower()
        self.assertIn("create table if not exists public.users", previous)
        self.assertIn("password_hash", previous)
        self.assertNotIn("create table public.profiles", previous)


@unittest.skip(
    "Later integration test. Requires a non-production database with auth.users. Do not run against Production."
)
class IdentitySchemaIntegrationLater(unittest.TestCase):
    def test_apply_and_rollback_only_new_objects(self):
        self.fail("not implemented")

    def test_anon_cannot_read_the_four_tables(self):
        self.fail("not implemented")

    def test_owner_can_update_only_display_name(self):
        self.fail("not implemented")

    def test_authenticated_cannot_write_entitlements(self):
        self.fail("not implemented")

    def test_second_active_entitlement_is_rejected(self):
        self.fail("not implemented")

    def test_plan_from_another_product_is_rejected(self):
        self.fail("not implemented")

    def test_new_auth_user_gets_profile_and_no_entitlement(self):
        self.fail("not implemented")

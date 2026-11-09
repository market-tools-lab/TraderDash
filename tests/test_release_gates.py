"""Cross-cutting gates for a later merge decision.

These checks do not start the app and do not contact Supabase.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import account_privacy
import stripe_test
import supabase_auth
import universes

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class ReleaseGateTests(unittest.TestCase):
    def test_missing_auth_mode_stays_legacy_and_registration_stays_closed(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRADERDASH_AUTH_MODE", None)
            self.assertEqual(supabase_auth.auth_mode(), "legacy")
        app = text("app.py")
        self.assertIn("Ny konto oprettes ikke i denne loginvej.", app)
        self.assertNotIn("Slet konto", app)
        self.assertNotIn("account_privacy", app)
        self.assertNotIn("stripe_test", app)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRADERDASH_PASSWORD_RECOVERY", None)
            os.environ.pop("TRADERDASH_AUTH_EMAIL_DELIVERY", None)
            self.assertFalse(supabase_auth.delivery_enabled())

    def test_stripe_and_privacy_stay_closed(self):
        self.assertFalse(stripe_test.ENTITLEMENT_UPDATES_ENABLED)
        self.assertIn(
            "const ENTITLEMENT_UPDATES_ENABLED = false;",
            text("supabase/functions/stripe-webhook/index.ts"),
        )
        self.assertIn("wxvobyifckbpnqfbnlxl", account_privacy.PROTECTED_REFS)
        self.assertIn("ajbsoudovxstlolojvte", account_privacy.PROTECTED_REFS)

    def test_paper_counts_and_error_details(self):
        self.assertEqual(len(universes.stocks_for("free")), 30)
        self.assertEqual(len(universes.stocks_for("nordic")), 79)
        self.assertEqual(len(universes.stocks_for("international")), 159)
        self.assertIn('showErrorDetails = "none"', text(".streamlit/config.toml"))

    def test_secret_examples_and_historical_audits_stay_out(self):
        example = text(".streamlit/secrets.toml.example")
        ignore = text(".gitignore")
        self.assertNotIn("service_role", example)
        self.assertNotIn("eyJ", example)
        self.assertIn(".streamlit/secrets.toml", ignore)
        for name in (
            "docs/TRADERDASH_ACCOUNT_ACCESS_TEMPLATE.md",
            "docs/TRADERDASH_ARCHITECTURE.mmd",
            "docs/TRADERDASH_DATA_INVENTORY.md",
            "docs/TRADERDASH_DEPLOYMENT_REQUIREMENTS.md",
            "docs/TRADERDASH_EXECUTIVE_SUMMARY.md",
            "docs/TRADERDASH_SECURITY_FINDINGS.md",
            "docs/TRADERDASH_TECHNICAL_AUDIT.md",
        ):
            self.assertIn(name, ignore)

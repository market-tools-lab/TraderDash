"""Preview Auth login. Skipped unless the preview environment is present.

The password and the anon key come from the process environment. They are
not stored in this file. The URL must contain the preview project ref.
"""

from __future__ import annotations

import os
import unittest

import supabase_auth
import universes

PREVIEW_REF = "ajbsoudovxstlolojvte"
EMAIL = "markettools-auth-test@example.invalid"
USER_ID = "32772e00-62a3-4d85-8da6-eeb806cb56c5"


def _preview_ready() -> str | None:
    url = os.environ.get("TRADERDASH_SUPABASE_URL", "")
    if PREVIEW_REF not in url:
        return "preview project ref is not configured"
    if not os.environ.get("TRADERDASH_SUPABASE_ANON_KEY"):
        return "preview anon key is not configured"
    if not os.environ.get("TRADERDASH_PREVIEW_TEST_PASSWORD"):
        return "preview test password is not configured"
    return None


class PreviewAuthTests(unittest.TestCase):
    def setUp(self):
        reason = _preview_ready()
        if reason:
            self.skipTest(reason)

    def test_login_profile_free_entitlement_and_logout(self):
        session = supabase_auth.sign_in(EMAIL, os.environ["TRADERDASH_PREVIEW_TEST_PASSWORD"])
        self.assertIsNotNone(session)
        self.assertEqual(session.user_id, USER_ID)
        self.assertEqual(session.profile_id, USER_ID)
        self.assertEqual(session.plan, "free")
        self.assertEqual(len(universes.stocks_for("free")), 30)
        state = {"login_password": "present-before-remember"}
        supabase_auth.remember(session, state)
        self.assertNotIn("login_password", state)
        self.assertEqual(state[supabase_auth.USER_KEY], USER_ID)
        supabase_auth.logout(state)
        self.assertNotIn(supabase_auth.TOKEN_KEY, state)
        self.assertNotIn(supabase_auth.USER_KEY, state)

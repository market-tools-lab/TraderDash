"""Turnstile checks stay local. They do not call Cloudflare."""

from __future__ import annotations

import unittest

import captcha

HOST = "traderdash-next.streamlit.app"
LIVE = {
    "TRADERDASH_TURNSTILE": "required",
    "TRADERDASH_TURNSTILE_MODE": "live",
    "TRADERDASH_TURNSTILE_SECRET_KEY": "live-secret-not-a-test-key",
    "TRADERDASH_TURNSTILE_HOSTNAME": HOST,
    "TRADERDASH_ENV": "production",
}


class CaptchaTests(unittest.TestCase):
    def setUp(self):
        captcha.reset_seen()

    def test_missing_configuration_and_production_test_key_fail_closed(self):
        with self.assertRaises(captcha.CaptchaRejected) as missing:
            captcha.verify("token-a", env={"TRADERDASH_TURNSTILE": "required"})
        self.assertEqual(missing.exception.reason, "missing_configuration")
        with self.assertRaises(captcha.CaptchaRejected) as refused:
            captcha.verify(
                "token-a",
                env={
                    "TRADERDASH_TURNSTILE": "required",
                    "TRADERDASH_TURNSTILE_MODE": "test",
                    "TRADERDASH_TURNSTILE_SECRET_KEY": captcha.PASS_SECRET,
                    "TRADERDASH_TURNSTILE_HOSTNAME": HOST,
                    "TRADERDASH_ENV": "production",
                },
            )
        self.assertEqual(refused.exception.reason, "test_key_refused")
        self.assertNotIn(captcha.PASS_SECRET, str(refused.exception))

    def test_test_mode_accepts_once_and_rejects_failure_secrets(self):
        env = {
            "TRADERDASH_TURNSTILE": "required",
            "TRADERDASH_TURNSTILE_MODE": "test",
            "TRADERDASH_TURNSTILE_SECRET_KEY": captcha.PASS_SECRET,
            "TRADERDASH_TURNSTILE_HOSTNAME": HOST,
        }
        captcha.verify("token-once", env=env)
        with self.assertRaises(captcha.CaptchaRejected) as reused:
            captcha.verify("token-once", env=env)
        self.assertEqual(reused.exception.reason, "token")
        with self.assertRaises(captcha.CaptchaRejected) as invalid:
            captcha.verify("token-b", env=dict(env, TRADERDASH_TURNSTILE_SECRET_KEY=captcha.FAIL_SECRET))
        self.assertEqual(invalid.exception.reason, "invalid")
        with self.assertRaises(captcha.CaptchaRejected) as spent:
            captcha.verify("token-c", env=dict(env, TRADERDASH_TURNSTILE_SECRET_KEY=captcha.SPENT_SECRET))
        self.assertEqual(spent.exception.reason, "reused")

    def test_live_transport_checks_hostname_action_and_errors(self):
        calls = []

        def transport(url, payload):
            calls.append((url, dict(payload)))
            kind = payload["response"]
            if kind == "timeout":
                raise TimeoutError("timed out")
            if kind == "spent":
                return {"success": False, "error-codes": ["timeout-or-duplicate"]}
            if kind == "bad-host":
                return {"success": True, "hostname": "example.invalid", "action": "registration"}
            if kind == "bad-action":
                return {"success": True, "hostname": HOST, "action": "login"}
            return {"success": True, "hostname": HOST, "action": "registration"}

        captcha.verify("ok-token", env=LIVE, transport=transport)
        self.assertEqual(calls[0][0], captcha.SITEVERIFY_URL)
        self.assertEqual(calls[0][1]["secret"], LIVE["TRADERDASH_TURNSTILE_SECRET_KEY"])
        for token, reason in (
            ("bad-host", "hostname"),
            ("bad-action", "action"),
            ("spent", "reused"),
            ("timeout", "timeout"),
            ("", "token"),
        ):
            with self.assertRaises(captcha.CaptchaRejected) as raised:
                captcha.verify(token, env=LIVE, transport=transport)
            self.assertEqual(raised.exception.reason, reason)
        with self.assertRaises(captcha.CaptchaRejected):
            captcha.verify("ok-token", env=LIVE, transport=transport)
        self.assertNotIn("live-secret", str(raised.exception))

    def test_widget_markup_keeps_the_secret_out(self):
        markup = captcha.widget_markup(captcha.PASS_SITE_KEY)
        self.assertIn(captcha.PASS_SITE_KEY, markup)
        self.assertIn("registration", markup)
        self.assertNotIn(captcha.PASS_SECRET, markup)
        self.assertEqual(captcha.widget_markup('"><script>'), "")
        self.assertEqual(captcha.widget_markup(captcha.PASS_SECRET), "")

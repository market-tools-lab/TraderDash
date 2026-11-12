"""Turnstile checks stay local. They do not call Cloudflare."""

from __future__ import annotations

import unittest
import urllib.error
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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

    def test_missing_live_transport_fails_closed(self):
        with self.assertRaises(captcha.CaptchaRejected) as raised:
            captcha.verify("ok-token", env=LIVE)
        self.assertEqual(raised.exception.reason, "unavailable")
        self.assertEqual(str(raised.exception), "Kontoen kunne ikke oprettes.")

    def test_https_transport_posts_siteverify_without_logging_the_secret(self):
        secret = LIVE["TRADERDASH_TURNSTILE_SECRET_KEY"]
        token = "siteverify-token-value"
        captured = {}

        class Response:
            def read(self):
                return b'{"success": true, "hostname": "traderdash-next.streamlit.app", "action": "registration"}'

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = request.data.decode()
            return Response()

        stream = StringIO()
        with patch("urllib.request.urlopen", opener), redirect_stderr(stream):
            body = captcha.https_transport(captcha.SITEVERIFY_URL, {"secret": secret, "response": token})
            captcha.verify("fresh-live-token", env=LIVE, transport=captcha.https_transport)
        self.assertTrue(body["success"])
        self.assertEqual(captured["url"], captcha.SITEVERIFY_URL)
        self.assertEqual(captured["timeout"], 30)
        self.assertNotIn(secret, stream.getvalue())
        self.assertNotIn(token, stream.getvalue())

        def down(_request, timeout=30):
            raise urllib.error.URLError("down")

        with patch("urllib.request.urlopen", down):
            with self.assertRaises(captcha.CaptchaRejected) as network:
                captcha.verify("network-token", env=LIVE, transport=captcha.https_transport)
        self.assertEqual(network.exception.reason, "timeout")

        def slow(_request, timeout=30):
            raise TimeoutError("slow")

        with patch("urllib.request.urlopen", slow):
            with self.assertRaises(captcha.CaptchaRejected) as timed:
                captcha.verify("slow-token", env=LIVE, transport=captcha.https_transport)
        self.assertEqual(timed.exception.reason, "timeout")

    def test_widget_returns_a_token_and_keeps_the_secret_out(self):
        calls = []

        def component(sitekey, action):
            calls.append((sitekey, action))
            return "a" * 20

        token = captcha.render_widget(
            captcha.PASS_SITE_KEY,
            env={"TRADERDASH_TURNSTILE_MODE": "test"},
            component=component,
        )
        self.assertEqual(token, "a" * 20)
        self.assertEqual(calls, [(captcha.PASS_SITE_KEY, "registration")])
        self.assertIsNone(captcha.render_widget('"><script>', component=component))
        self.assertIsNone(captcha.render_widget(captcha.PASS_SECRET, component=component))
        self.assertIsNone(
            captcha.render_widget(
                captcha.PASS_SITE_KEY,
                env={"TRADERDASH_ENV": "production", "TRADERDASH_TURNSTILE_MODE": "live"},
                component=component,
            )
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            captcha.render_widget(
                captcha.PASS_SITE_KEY,
                env={"TRADERDASH_TURNSTILE_MODE": "test"},
                component=lambda *_args: "short",
            ),
            "",
        )
        self.assertEqual(
            captcha.render_widget(
                captcha.PASS_SITE_KEY,
                env={"TRADERDASH_TURNSTILE_MODE": "test"},
                component=lambda *_args: {"token": "a" * 20},
            ),
            "",
        )
        page = (Path(__file__).resolve().parents[1] / "captcha_component" / "index.html").read_text(encoding="utf-8")
        self.assertIn("streamlit:setComponentValue", page)
        self.assertIn('dataType: "json"', page)
        self.assertIn("streamlit:componentReady", page)
        self.assertIn("streamlit:setFrameHeight", page)
        self.assertIn('var ACTION = "registration"', page)
        self.assertIn("event.source !== window.parent", page)
        self.assertIn("expired-callback", page)
        self.assertIn("error-callback", page)
        self.assertNotIn(captcha.PASS_SECRET, page)
        self.assertNotIn("TRADERDASH_TURNSTILE_SECRET_KEY", page)
        app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        form = app.split("def _render_supabase_registration", 1)[1].split("def _render_signup_verification", 1)[0]
        self.assertLess(form.index('with st.form("auth_register")'), form.index("captcha.render_widget"))
        self.assertLess(form.index("captcha.remember_token"), form.index('st.form_submit_button("Opret konto")'))
        self.assertLess(form.index("if not submitted:"), form.index("captcha.discard_token"))

    def test_session_keeps_a_token_the_form_rerun_no_longer_returns(self):
        state = {}
        token = "a" * 20
        self.assertEqual(captcha.remember_token(state, token), token)
        self.assertEqual(captcha.remember_token(state, ""), token)
        self.assertEqual(captcha.remember_token(state, {"token": token}), token)
        quoted = '"' + ("b" * 20) + '"'
        self.assertEqual(captcha.usable_token(quoted), "b" * 20)
        self.assertEqual(captcha.remember_token(state, quoted), "b" * 20)
        self.assertEqual(state["traderdash_turnstile_token"], "b" * 20)
        captcha.discard_token(state)
        self.assertEqual(captcha.remember_token(state, ""), "")
        self.assertNotIn("traderdash_turnstile_token", state)
        self.assertEqual(captcha.usable_token("short"), "")
        self.assertEqual(captcha.usable_token(None), "")

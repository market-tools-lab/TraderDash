"""App runtime for Supabase Auth. No credentials and no network by default."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request as urlrequest

import pandas as pd
from streamlit.testing.v1 import AppTest

import access
import market_data
import supabase_auth
import universes

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PASSPHRASE = "correct horse battery staple"
PREVIEW = {
    "TRADERDASH_AUTH_MODE": "supabase_auth",
    "TRADERDASH_SUPABASE_URL": "https://ajbsoudovxstlolojvte.supabase.co",
    "TRADERDASH_SUPABASE_ANON_KEY": "test-anon-key",
}
USERS = {
    "free@example.invalid": {"id": "user-free", "plan": "free", "status": "active", "profile": True},
    "nordic@example.invalid": {"id": "user-nordic", "plan": "nordic", "status": "active", "profile": True},
    "international@example.invalid": {"id": "user-international", "plan": "international", "status": "active", "profile": True},
    "none@example.invalid": {"id": "user-none", "plan": None, "status": None, "profile": True},
    "suspended@example.invalid": {"id": "user-suspended", "plan": "nordic", "status": "suspended", "profile": True},
    "revoked@example.invalid": {"id": "user-revoked", "plan": "nordic", "status": "revoked", "profile": True},
    "expired@example.invalid": {"id": "user-expired", "plan": "nordic", "status": "expired", "profile": True},
    "pastdue@example.invalid": {"id": "user-pastdue", "plan": "nordic", "status": "past_due", "profile": True},
    "noprofile@example.invalid": {"id": "user-noprofile", "plan": "free", "status": "active", "profile": False},
}


def _history() -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=60, freq="B")
    close = pd.Series([100 + (3 if index_ % 2 else -2) + (index_ % 5) for index_ in range(60)], index=index, dtype=float)
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1000}
    )


def _transport(method, url, headers, body):
    if "grant_type=password" in url:
        user = USERS.get((body or {}).get("email", ""))
        if user is None or (body or {}).get("password") != PASSPHRASE:
            return 400, {"error": "invalid_grant", "error_description": "https://secret.example/token"}
        return 200, {
            "access_token": "token-" + user["id"],
            "user": {"id": user["id"], "email": body["email"]},
        }
    if url.endswith("/auth/v1/user") and method == "GET":
        token = headers["Authorization"].removeprefix("Bearer ")
        for email, user in USERS.items():
            if token == "token-" + user["id"]:
                return 200, {"id": user["id"], "email": email}
        return 401, {"msg": "bad token"}
    if "/profiles" in url:
        token = headers["Authorization"].removeprefix("Bearer ")
        rows = [
            {"id": user["id"], "display_name": None}
            for user in USERS.values()
            if user["profile"] and token == "token-" + user["id"]
        ]
        return 200, rows
    if "/entitlements" in url:
        token = headers["Authorization"].removeprefix("Bearer ")
        for user in USERS.values():
            if token == "token-" + user["id"] and user["status"]:
                return 200, [
                    {
                        "status": user["status"],
                        "starts_at": "2020-01-01T00:00:00Z",
                        "ends_at": None,
                        "products": {"code": "traderdash"},
                        "plans": {"code": user["plan"]},
                    }
                ]
        return 200, []
    if "/logout" in url or "/recover" in url:
        return 204, {}
    if method == "PUT" and url.endswith("/auth/v1/user"):
        return 200, {}
    return 500, {"message": "https://ajbsoudovxstlolojvte.supabase.co raw failure"}


def _texts(at: AppTest) -> str:
    chunks: list[str] = []
    for name in ("error", "info", "warning", "success", "caption", "text", "markdown", "title", "header", "exception"):
        for item in getattr(at, name):
            chunks.append(str(getattr(item, "value", "")))
    return "\n".join(chunks)


def _click(at: AppTest, label: str) -> None:
    next(button for button in at.button if button.label == label).click()
    at.run()


def _boot() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    return at


def _login(at: AppTest, email: str, password: str = PASSPHRASE) -> AppTest:
    at.text_input(key="login_email").set_value(email)
    at.text_input(key="login_password").set_value(password)
    _click(at, "Log ind")
    return at


class AppAuthFlowTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, PREVIEW, clear=False)
        self.history = patch.object(market_data, "get_history", return_value=_history())
        self.quote = patch.object(market_data, "get_quote", return_value={})
        self.transport = patch.object(supabase_auth, "_urllib_transport", _transport)
        self.env.start()
        self.history.start()
        self.quote.start()
        self.transport.start()
        self.addCleanup(self.transport.stop)
        self.addCleanup(self.quote.stop)
        self.addCleanup(self.history.stop)
        self.addCleanup(self.env.stop)

    def test_login_view_has_reset_and_no_open_registration(self):
        at = _boot()
        labels = [button.label for button in at.button]
        self.assertIn("Log ind", labels)
        self.assertIn("Send nulstillingslink", labels)
        self.assertNotIn("Opret konto", labels)
        self.assertNotIn("Opret konto", _texts(at))
        self.assertIn("Ny konto oprettes ikke", _texts(at))
        self.assertEqual(at.exception, [])

    def test_wrong_login_is_neutral_and_keeps_no_secret(self):
        at = _login(_boot(), "free@example.invalid", "wrong-password-value")
        self.assertIn("Forkert e-mail eller adgangskode.", _texts(at))
        self.assertNotIn(supabase_auth.TOKEN_KEY, at.session_state)
        self.assertNotIn(supabase_auth.USER_KEY, at.session_state)
        self.assertNotIn("login_password", at.session_state)
        self.assertNotIn("wrong-password-value", str(dict(at.session_state)))
        self.assertNotIn("secret.example", _texts(at))
        self.assertEqual(at.exception, [])

    def test_leaky_auth_error_is_replaced(self):
        def leaky(email, password, *, transport=None):
            raise supabase_auth.AuthError("https://ajbsoudovxstlolojvte.supabase.co eyJabc")

        with patch.object(supabase_auth, "sign_in", leaky):
            at = _login(_boot(), "free@example.invalid")
        text = _texts(at)
        self.assertIn("Supabase Auth er ikke tilgængelig.", text)
        self.assertNotIn("supabase.co", text)
        self.assertNotIn("eyJ", text)
        self.assertNotIn("ajbsoudovxstlolojvte", text)

    def test_free_nordic_and_international_open_their_universes(self):
        expected = {
            "free@example.invalid": ("free", 30),
            "nordic@example.invalid": ("nordic", 79),
            "international@example.invalid": ("international", 159),
        }
        for email, (plan, papers) in expected.items():
            at = _login(_boot(), email)
            self.assertEqual(at.session_state["plan"], plan)
            self.assertEqual(len(universes.stocks_for(plan)), papers)
            self.assertEqual(len(access.get_allowed_stocks(at.session_state["plan"])), papers)
            self.assertIn("Enkelt Aktie", [tab.label for tab in at.tabs])
            self.assertIn(f"Plan: {access.PLAN_LABELS[plan]}", _texts(at))
            self.assertEqual(at.exception, [])

    def test_free_can_open_a_free_stock_and_rejects_a_locked_market(self):
        at = _login(_boot(), "free@example.invalid")
        stock = at.selectbox(key="selected_symbol__denmark")
        self.assertIn("Novo Nordisk (NOVO-B.CO)", stock.options)
        self.assertTrue(any(option.endswith("🔒") for option in stock.options))
        self.assertFalse(any("Novo Nordisk" in option and option.endswith("🔒") for option in stock.options))
        at.selectbox(key="selected_market").set_value("united states")
        at.run()
        self.assertIn("Available with TraderDash International", _texts(at))
        self.assertNotIn(supabase_auth.TOKEN_KEY, _texts(at))

    def test_closed_entitlements_stop_before_analysis(self):
        for email in (
            "none@example.invalid",
            "suspended@example.invalid",
            "revoked@example.invalid",
            "expired@example.invalid",
            "pastdue@example.invalid",
        ):
            at = _login(_boot(), email)
            self.assertEqual(at.session_state["plan"], "")
            self.assertIn("Ingen aktiv TraderDash-adgang.", _texts(at))
            self.assertIn("Plan: Ingen adgang", _texts(at))
            self.assertEqual(list(at.tabs), [])
            self.assertNotIn("login_password", at.session_state)

    def test_missing_profile_stops_without_a_universe(self):
        at = _login(_boot(), "noprofile@example.invalid")
        self.assertIn("Kontoen er ikke klar.", _texts(at))
        self.assertEqual(list(at.tabs), [])
        self.assertNotIn("Enkelt Aktie", _texts(at))

    def test_logout_clears_the_session_and_login_works_again(self):
        at = _login(_boot(), "free@example.invalid")
        _click(at, "Log ud")
        self.assertNotIn(supabase_auth.TOKEN_KEY, at.session_state)
        self.assertNotIn(supabase_auth.USER_KEY, at.session_state)
        self.assertNotIn(supabase_auth.EMAIL_KEY, at.session_state)
        self.assertNotIn("plan", at.session_state)
        self.assertNotIn(PASSPHRASE, str(dict(at.session_state)))
        self.assertFalse(at.session_state.get("login_password"))
        self.assertIn("Log ind", [button.label for button in at.button])
        at = _login(at, "free@example.invalid")
        self.assertEqual(at.session_state["plan"], "free")
        self.assertEqual(at.session_state[supabase_auth.USER_KEY], "user-free")

    def test_two_sessions_do_not_share_plan_or_logout(self):
        free = _login(_boot(), "free@example.invalid")
        nordic = _login(_boot(), "nordic@example.invalid")
        self.assertEqual(free.session_state["plan"], "free")
        self.assertEqual(nordic.session_state["plan"], "nordic")
        self.assertNotEqual(free.session_state[supabase_auth.USER_KEY], nordic.session_state[supabase_auth.USER_KEY])
        self.assertIsNot(free.session_state, nordic.session_state)
        _click(free, "Log ud")
        self.assertNotIn(supabase_auth.TOKEN_KEY, free.session_state)
        self.assertEqual(nordic.session_state["plan"], "nordic")
        self.assertEqual(nordic.session_state[supabase_auth.USER_KEY], "user-nordic")

    def test_market_cache_is_not_keyed_by_a_user(self):
        source = (ROOT / "market_data" / "yfinance_provider.py").read_text(encoding="utf-8")
        self.assertIn('("history", ticker, period)', source)
        self.assertIn('("quote", ticker)', source)
        self.assertNotIn("access_token", source)
        self.assertNotIn("session_state", source)

    def test_account_page_can_change_password_without_showing_ids(self):
        with patch.dict(os.environ, {"TRADERDASH_DEV_OVERRIDE": "1"}):
            at = _login(_boot(), "free@example.invalid")
            at.radio(key="main_view").set_value("account")
            at.run()
        labels = [button.label for button in at.button]
        self.assertIn("Skift adgangskode", labels)
        self.assertIn("Ny adgangskode", [item.label for item in at.text_input])
        self.assertIn("Gentag ny adgangskode", [item.label for item in at.text_input])
        text = _texts(at)
        self.assertNotIn("user-free", text)
        self.assertNotIn("ajbsoudovxstlolojvte", text)
        self.assertNotIn("token-user-free", text)

    def test_missing_url_invalid_key_timeout_and_outage_stay_closed(self):
        with patch.dict(os.environ, {"TRADERDASH_SUPABASE_URL": "", "TRADERDASH_SUPABASE_ANON_KEY": ""}):
            missing = _login(_boot(), "free@example.invalid")
        self.assertIn("Supabase Auth er ikke konfigureret.", _texts(missing))
        self.assertEqual(missing.exception, [])

        def invalid_key(method, url, headers, body):
            return 401, {"message": "Invalid API key sb_secret_should_not_show"}

        with patch.object(supabase_auth, "_urllib_transport", invalid_key):
            invalid = _login(_boot(), "free@example.invalid")
        self.assertIn("Supabase Auth er ikke tilgængelig.", _texts(invalid))
        self.assertNotIn("sb_secret", _texts(invalid))
        self.assertNotIn("login_password", invalid.session_state)

        def timed_out(method, url, headers, body):
            raise TimeoutError("timed out talking to https://ajbsoudovxstlolojvte.supabase.co")

        with patch.object(supabase_auth, "_urllib_transport", timed_out):
            timeout = _login(_boot(), "free@example.invalid")
        self.assertIn("Supabase Auth er ikke tilgængelig.", _texts(timeout))
        self.assertNotIn("supabase.co", _texts(timeout))
        self.assertEqual(timeout.exception, [])

        def outage(method, url, headers, body):
            return 503, {"message": "project ajbsoudovxstlolojvte is down"}

        with patch.object(supabase_auth, "_urllib_transport", outage):
            down = _login(_boot(), "free@example.invalid")
        self.assertIn("Supabase Auth er ikke tilgængelig.", _texts(down))
        self.assertNotIn("ajbsoudovxstlolojvte", _texts(down))

    def test_an_active_auth_session_does_not_fall_through_to_legacy(self):
        at = _login(_boot(), "free@example.invalid")
        user_id = at.session_state[supabase_auth.USER_KEY]
        with patch.dict(os.environ, {"TRADERDASH_AUTH_MODE": "legacy"}):
            at.run()
        self.assertIn("Login-måden er ændret. Log ind igen.", _texts(at))
        self.assertNotIn(supabase_auth.TOKEN_KEY, at.session_state)
        self.assertNotEqual(at.session_state.get("auth_user_id"), user_id)
        self.assertNotIn("Opret konto", _texts(at))


class LegacyGateTests(unittest.TestCase):
    def test_legacy_login_renders_without_preview_auth_configuration(self):
        with patch.dict(
            os.environ,
            {"TRADERDASH_AUTH_MODE": "legacy", "TRADERDASH_SUPABASE_URL": "", "TRADERDASH_SUPABASE_ANON_KEY": ""},
        ):
            at = _boot()
        labels = [tab.label for tab in at.tabs]
        self.assertEqual(labels, ["Log ind", "Opret konto"])
        self.assertIn("Opret konto", [button.label for button in at.button])
        self.assertNotIn("Send nulstillingslink", [button.label for button in at.button])
        self.assertEqual(at.exception, [])
        source = APP.read_text(encoding="utf-8")
        self.assertIn("accounts.authenticate(email, password)", source)
        self.assertIn("accounts.create_user(email, password)", source)
        self.assertIn("accounts.get_user(", source)


class PreviewAppFlowTests(unittest.TestCase):
    """Real preview login. Skips unless the temporary fixture is supplied."""

    @classmethod
    def setUpClass(cls):
        path = os.environ.get("TRADERDASH_APP_FIXTURE", "")
        url = os.environ.get("TRADERDASH_SUPABASE_URL", "")
        key = os.environ.get("TRADERDASH_SUPABASE_ANON_KEY", "")
        if not path or not url or not key:
            raise unittest.SkipTest("preview app fixture is not configured")
        if url.rstrip("/") != "https://ajbsoudovxstlolojvte.supabase.co":
            raise unittest.SkipTest("preview app fixture is not the allowed target")
        with open(path, encoding="utf-8") as handle:
            cls.fixture = json.load(handle)

    def setUp(self):
        self.history = patch.object(market_data, "get_history", return_value=_history())
        self.quote = patch.object(market_data, "get_quote", return_value={})
        self.history.start()
        self.quote.start()
        self.addCleanup(self.quote.stop)
        self.addCleanup(self.history.stop)
        os.environ["TRADERDASH_AUTH_MODE"] = "supabase_auth"

    def _user(self, name: str) -> dict:
        return self.fixture["users"][name]

    def _sign_in(self, name: str) -> AppTest:
        user = self._user(name)
        return _login(_boot(), user["email"], self.fixture["password"])

    def test_preview_plans_and_closed_states(self):
        for name, plan, papers in (
            ("free", "free", 30),
            ("nordic", "nordic", 79),
            ("international", "international", 159),
        ):
            at = self._sign_in(name)
            self.assertEqual(at.session_state["plan"], plan)
            self.assertEqual(at.session_state[supabase_auth.USER_KEY], self._user(name)["id"])
            self.assertEqual(len(access.get_allowed_stocks(plan)), papers)
            self.assertIn("Enkelt Aktie", [tab.label for tab in at.tabs])
            self.assertNotIn("login_password", at.session_state)

        for name in ("none", "suspended", "revoked", "expired", "past_due"):
            at = self._sign_in(name)
            self.assertEqual(at.session_state["plan"], "")
            self.assertIn("Ingen aktiv TraderDash-adgang.", _texts(at))
            self.assertEqual(list(at.tabs), [])

        missing = self._sign_in("no_profile")
        self.assertIn("Kontoen er ikke klar.", _texts(missing))
        self.assertEqual(list(missing.tabs), [])

    def test_preview_logout_and_second_login(self):
        at = self._sign_in("free")
        _click(at, "Log ud")
        self.assertNotIn(supabase_auth.TOKEN_KEY, at.session_state)
        self.assertNotIn(supabase_auth.USER_KEY, at.session_state)
        at = _login(at, self._user("free")["email"], self.fixture["password"])
        self.assertEqual(at.session_state["plan"], "free")

    def test_preview_sessions_are_isolated(self):
        free = self._sign_in("free")
        nordic = self._sign_in("nordic")
        self.assertEqual(free.session_state["plan"], "free")
        self.assertEqual(nordic.session_state["plan"], "nordic")
        self.assertIsNot(free.session_state, nordic.session_state)
        _click(free, "Log ud")
        self.assertEqual(nordic.session_state[supabase_auth.USER_KEY], self._user("nordic")["id"])
        free_rows = _own_ids(self._user("free"), "profiles")
        nordic_rows = _own_ids(self._user("nordic"), "profiles")
        self.assertEqual(free_rows, [self._user("free")["id"]])
        self.assertEqual(nordic_rows, [self._user("nordic")["id"]])
        free_entitlements = _own_ids(self._user("free"), "entitlements")
        nordic_entitlements = _own_ids(self._user("nordic"), "entitlements")
        self.assertEqual(free_entitlements, [self._user("free")["id"]])
        self.assertEqual(nordic_entitlements, [self._user("nordic")["id"]])


def _own_ids(user: dict, table: str) -> list[str]:
    session = supabase_auth.sign_in(user["email"], PreviewAppFlowTests.fixture["password"])
    if session is None:
        return ["missing-session"]
    column = "id" if table == "profiles" else "user_id"
    url = f"https://ajbsoudovxstlolojvte.supabase.co/rest/v1/{table}?select={column}"
    req = urlrequest.Request(
        url,
        headers={
            "apikey": os.environ["TRADERDASH_SUPABASE_ANON_KEY"],
            "Authorization": "Bearer " + session.access_token,
        },
    )
    with urlrequest.urlopen(req, timeout=30) as response:
        rows = json.loads(response.read().decode())
    return [str(row.get(column) or "") for row in rows]

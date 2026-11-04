"""Supabase Auth session for TraderDash.

This module is used only when TRADERDASH_AUTH_MODE is supabase_auth.
A missing or unknown mode stays on the legacy login. The module reads the
signed-in user's profile and TraderDash entitlement. It does not write
entitlements, and it does not keep the password.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping, MutableMapping
from datetime import datetime, timezone
from typing import Any

from account_store import User

TRADERDASH_PRODUCT = "traderdash"
PLANS = ("free", "nordic", "international")
TOKEN_KEY = "supabase_access_token"
USER_KEY = "supabase_user_id"
EMAIL_KEY = "supabase_email"
PASSWORD_KEYS = ("login_password", "register_password", "register_confirmation")


class AuthError(Exception):
    """A safe message for a missing setting or an unreachable Auth service."""


def auth_mode() -> str:
    """Return legacy unless the operator explicitly selects Supabase Auth."""
    value = os.environ.get("TRADERDASH_AUTH_MODE", "").strip().lower()
    if value == "supabase_auth":
        return "supabase_auth"
    return "legacy"


def forget_password(state: MutableMapping[str, Any]) -> None:
    for key in PASSWORD_KEYS:
        state.pop(key, None)


def remember(session: "AuthSession", state: MutableMapping[str, Any]) -> None:
    state[TOKEN_KEY] = session.access_token
    state[USER_KEY] = session.user_id
    state[EMAIL_KEY] = session.email
    forget_password(state)


def clear_local(state: MutableMapping[str, Any]) -> None:
    for key in (TOKEN_KEY, USER_KEY, EMAIL_KEY):
        state.pop(key, None)


def plan_from_entitlements(rows: list[dict[str, Any]] | None, now: datetime | None = None) -> str | None:
    """Active TraderDash plan, or None when access must stay closed."""
    moment = now or datetime.now(timezone.utc)
    for row in rows or []:
        plan = _plan_from_row(row, moment)
        if plan is not None:
            return plan
    return None


def sign_in(email: str, password: str, *, transport=None) -> "AuthSession | None":
    """Return a session, or None when the e-mail or password is rejected."""
    client = Client.from_env(transport)
    return client.sign_in(email, password)


def load_saved_session(state: MutableMapping[str, Any], *, transport=None) -> "AuthSession | None":
    token = str(state.get(TOKEN_KEY) or "")
    if not token:
        return None
    try:
        session = Client.from_env(transport).session_from_token(token)
    except AuthError:
        clear_local(state)
        raise
    if session is None:
        clear_local(state)
        return None
    remember(session, state)
    return session


def logout(state: MutableMapping[str, Any], *, transport=None) -> None:
    token = str(state.get(TOKEN_KEY) or "")
    clear_local(state)
    if not token:
        return
    try:
        Client.from_env(transport).logout(token)
    except AuthError:
        return


class AuthSession:
    def __init__(
        self,
        *,
        user_id: str,
        email: str,
        access_token: str,
        plan: str | None,
        profile_id: str | None,
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.access_token = access_token
        self.plan = plan
        self.profile_id = profile_id

    def as_user(self) -> User:
        if self.plan == "free":
            status = "free"
        elif self.plan in PLANS:
            status = "active"
        else:
            status = "expired"
        return User(
            user_id=self.user_id,
            email=self.email,
            plan=self.plan or "",
            subscription_status=status,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            created_at="",
            updated_at="",
        )


class Client:
    def __init__(self, base_url: str, anon_key: str, transport=None) -> None:
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key
        self.transport = transport or _urllib_transport

    @classmethod
    def from_env(cls, transport=None) -> "Client":
        base_url = os.environ.get("TRADERDASH_SUPABASE_URL", "").strip()
        anon_key = os.environ.get("TRADERDASH_SUPABASE_ANON_KEY", "").strip()
        if not base_url or not anon_key:
            raise AuthError("Supabase Auth er ikke konfigureret.")
        return cls(base_url, anon_key, transport)

    def sign_in(self, email: str, password: str) -> AuthSession | None:
        status, body = self._request(
            "POST",
            "/auth/v1/token?grant_type=password",
            {"email": str(email or "").strip(), "password": password},
        )
        if status == 400:
            return None
        if status != 200 or not isinstance(body, dict):
            raise AuthError("Supabase Auth er ikke tilgængelig.")
        token = str(body.get("access_token") or "")
        user = body.get("user") if isinstance(body.get("user"), dict) else {}
        user_id = str(user.get("id") or "")
        if not token or not user_id:
            raise AuthError("Supabase Auth er ikke tilgængelig.")
        return self._session(token, user_id, str(user.get("email") or email or ""))

    def session_from_token(self, token: str) -> AuthSession | None:
        status, body = self._request("GET", "/auth/v1/user", token=token)
        if status in {401, 403}:
            return None
        if status != 200 or not isinstance(body, dict):
            raise AuthError("Supabase Auth er ikke tilgængelig.")
        user_id = str(body.get("id") or "")
        if not user_id:
            return None
        return self._session(token, user_id, str(body.get("email") or ""))

    def logout(self, token: str) -> None:
        self._request("POST", "/auth/v1/logout", token=token)

    def _session(self, token: str, user_id: str, email: str) -> AuthSession:
        profile_status, profiles = self._request(
            "GET",
            "/rest/v1/profiles?select=id,display_name",
            token=token,
        )
        entitlement_status, rows = self._request(
            "GET",
            "/rest/v1/entitlements?select=status,starts_at,ends_at,products(code),plans(code)",
            token=token,
        )
        if profile_status in {401, 403} or entitlement_status in {401, 403}:
            raise AuthError("Supabase Auth er ikke tilgængelig.")
        profile_id = None
        if isinstance(profiles, list):
            for row in profiles:
                if isinstance(row, dict) and row.get("id") == user_id:
                    profile_id = user_id
                    break
        plan = plan_from_entitlements(rows if isinstance(rows, list) else [])
        return AuthSession(
            user_id=user_id,
            email=email,
            access_token=token,
            plan=plan,
            profile_id=profile_id,
        )

    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        token: str | None = None,
    ):
        headers = {
            "apikey": self.anon_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token or self.anon_key}",
        }
        return self.transport(method, self.base_url + path, headers, body)


def _plan_from_row(row: dict[str, Any], now: datetime) -> str | None:
    if _nested_code(row.get("products")) != TRADERDASH_PRODUCT:
        return None
    if row.get("status") != "active":
        return None
    starts_at = _parse_time(row.get("starts_at"))
    ends_at = _parse_time(row.get("ends_at"))
    if starts_at is not None and starts_at > now:
        return None
    if ends_at is not None and ends_at <= now:
        return None
    plan = _nested_code(row.get("plans"))
    if plan not in PLANS:
        return None
    return plan


def _nested_code(value: Any) -> str | None:
    if isinstance(value, dict):
        code = value.get("code")
        return str(code) if code else None
    if isinstance(value, list) and value and isinstance(value[0], dict):
        code = value[0].get("code")
        return str(code) if code else None
    return None


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _urllib_transport(method: str, url: str, headers: Mapping[str, str], body: Mapping[str, Any] | None):
    data = None if body is None else json.dumps(dict(body)).encode()
    request = urllib.request.Request(url, data=data, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, _decode(raw)
    except urllib.error.HTTPError as exc:
        return exc.code, _decode(exc.read())
    except urllib.error.URLError as exc:
        raise AuthError("Supabase Auth er ikke tilgængelig.") from exc


def _decode(raw: bytes):
    if not raw:
        return {}
    try:
        return json.loads(raw.decode())
    except json.JSONDecodeError:
        return {}

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
import urllib.parse
import urllib.request
from collections.abc import Mapping, MutableMapping
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

import password_policy
from account_store import User

TRADERDASH_PRODUCT = "traderdash"
PLANS = ("free", "nordic", "international")
TOKEN_KEY = "supabase_access_token"
USER_KEY = "supabase_user_id"
EMAIL_KEY = "supabase_email"
PASSWORD_KEYS = (
    "login_password",
    "register_password",
    "register_confirmation",
    "next_password",
    "next_confirmation",
    "recovery_password",
    "recovery_confirmation",
)
PREVIEW_ORIGIN = "https://ajbsoudovxstlolojvte.supabase.co"
RESET_MESSAGE = "Hvis der er en konto til e-mailadressen, sender vi en vejledning."
RECOVERY_DONE = "Adgangskoden er opdateret. Log ind igen."
INVALID_EMAIL = "Angiv en gyldig e-mailadresse."
RESET_UNAVAILABLE = "Nulstilling kan ikke sendes."
RESET_INVALID = "Nulstillingen er ikke gyldig."
RESET_COOLDOWN = "Vent et øjeblik, før du beder om et nyt link."
RECOVERY_TOKEN_KEY = "supabase_recovery_token"
RESET_AFTER_KEY = "supabase_reset_not_before"
RECOVERY_QUERY_KEYS = (
    "token_hash",
    "type",
    "ref",
    "code",
    "access_token",
    "refresh_token",
    "token",
    "next",
)
COOLDOWN_SECONDS = 60


class AuthError(Exception):
    """A safe message for a missing setting or an unreachable Auth service."""


def _ops(category: str, **fields) -> None:
    from operations import log_event

    log_event(category, **fields)


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
    forget_password(state)
    if not token:
        return
    try:
        Client.from_env(transport).logout(token)
    except AuthError:
        return


def recovery_requested() -> bool:
    """True only when an operator has explicitly enabled password recovery."""
    return os.environ.get("TRADERDASH_PASSWORD_RECOVERY", "").strip().lower() == "enabled"


def email_delivery_configured() -> bool:
    """True only when an operator asserts that Supabase SMTP is deliberately configured."""
    return os.environ.get("TRADERDASH_AUTH_EMAIL_DELIVERY", "").strip().lower() == "configured"


def delivery_enabled() -> bool:
    """Recovery may contact Auth only when both explicit switches are on."""
    return recovery_requested() and email_delivery_configured()


def project_ref() -> str:
    """Project ref from TRADERDASH_SUPABASE_URL. Empty when the URL is not a Supabase host."""
    host = (urlsplit(os.environ.get("TRADERDASH_SUPABASE_URL", "").strip()).hostname or "").lower()
    if not host.endswith(".supabase.co"):
        return ""
    ref = host.split(".")[0]
    return ref if ref else ""


def email_acceptable(email: str) -> bool:
    """A format check. It does not ask Auth whether the address exists."""
    text = str(email or "").strip()
    if not text or any(character.isspace() for character in text):
        return False
    if text.count("@") != 1 or any(character in text for character in "<>\"'"):
        return False
    local, domain = text.split("@")
    return bool(local and domain and "." in domain and ".." not in domain)


def request_password_reset(
    email: str,
    redirect_url: str,
    *,
    transport=None,
    state: MutableMapping[str, Any] | None = None,
    now: datetime | None = None,
) -> bool:
    """Ask Auth to send a reset. The result does not reveal whether the address exists."""
    if not email_acceptable(email):
        raise AuthError(INVALID_EMAIL)
    if not delivery_enabled():
        raise AuthError(RESET_UNAVAILABLE)
    if not allowed_redirect(redirect_url):
        raise AuthError(RESET_UNAVAILABLE)
    moment = now or datetime.now(timezone.utc)
    if state is not None and _cooldown_active(state, moment):
        raise AuthError(RESET_COOLDOWN)
    Client.from_env(transport).request_password_reset(email, redirect_url)
    if state is not None:
        state[RESET_AFTER_KEY] = (moment + timedelta(seconds=COOLDOWN_SECONDS)).isoformat()
    return True


def verify_recovery_session(token: str, *, transport=None) -> str | None:
    """Return the user id for a recovery session, or None when it is not valid."""
    if not str(token or "").strip():
        return None
    session = Client.from_env(transport).session_from_token(token)
    if session is None:
        return None
    return session.user_id


def update_password(token: str, new_password: str, *, transport=None) -> None:
    """Set a password from a recovery session. The password is not stored."""
    Client.from_env(transport).update_password(token, new_password)


def change_password(token: str, new_password: str, confirmation: str, *, transport=None) -> None:
    """Replace the password for the current session, then leave no copy behind."""
    if not password_policy.matches(new_password, confirmation):
        raise AuthError("Adgangskoderne er ikke ens.")
    Client.from_env(transport).update_password(token, new_password)


def sign_out_all_supported_sessions(state: MutableMapping[str, Any], *, transport=None) -> None:
    """End every Auth session on the configured project, then clear the local copy."""
    token = str(state.get(TOKEN_KEY) or "")
    clear_local(state)
    forget_password(state)
    if not token:
        return
    try:
        Client.from_env(transport).logout_all(token)
    except AuthError:
        return


def allowed_redirect(url: str) -> bool:
    """Accept an exact allowlisted URL. A user-supplied address is never added."""
    candidate = str(url or "").strip()
    if not candidate or not _redirect_structure_is_safe(candidate):
        return False
    return candidate in _redirect_allowlist()


def configured_redirect() -> str:
    """The one redirect this process may send. Missing or unsafe configuration fails closed."""
    candidate = os.environ.get("TRADERDASH_AUTH_REDIRECT_URL", "").strip()
    if not allowed_redirect(candidate):
        raise AuthError(RESET_UNAVAILABLE)
    return candidate


def recovery_link_present(params: Mapping[str, Any]) -> bool:
    """True when the page URL carries a recovery secret that must be handled or discarded."""
    return any(str(params.get(key) or "").strip() for key in ("token_hash", "code", "access_token", "refresh_token"))


def take_recovery_token(params: Mapping[str, Any]) -> str:
    """Return a recovery token hash, or raise when the link cannot be used."""
    token = str(params.get("token_hash") or "").strip()
    kind = str(params.get("type") or "").strip().lower()
    ref = str(params.get("ref") or "").strip()
    implicit = any(str(params.get(key) or "").strip() for key in ("code", "access_token", "refresh_token"))
    if ref and ref != project_ref():
        raise AuthError(RESET_INVALID)
    if not delivery_enabled():
        if token or implicit:
            raise AuthError(RESET_INVALID)
        return ""
    if implicit and not (token and kind == "recovery"):
        raise AuthError(RESET_INVALID)
    if token and kind != "recovery":
        raise AuthError(RESET_INVALID)
    if token and kind == "recovery":
        return token
    return ""


def discard_recovery_query(params: MutableMapping[str, Any]) -> None:
    """Drop recovery material from the page URL. The values are not recorded."""
    for key in RECOVERY_QUERY_KEYS:
        if key in params:
            del params[key]


def clear_recovery(state: MutableMapping[str, Any]) -> None:
    """Remove the recovery token, the cooldown, and any password fields."""
    state.pop(RECOVERY_TOKEN_KEY, None)
    state.pop(RESET_AFTER_KEY, None)
    forget_password(state)


def complete_recovery(
    token_hash: str,
    new_password: str,
    confirmation: str,
    *,
    transport=None,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    """Set a password from a recovery link, end that session, and keep no token."""
    if not password_policy.matches(new_password, confirmation):
        raise AuthError("Adgangskoderne er ikke ens.")
    try:
        password_policy.require(new_password)
    except password_policy.PasswordRejected as exc:
        raise AuthError(str(exc)) from None
    if not delivery_enabled() or not str(token_hash or "").strip():
        raise AuthError(RESET_INVALID)
    client = Client.from_env(transport)
    access_token = client.exchange_recovery(token_hash)
    try:
        client.update_password_from_recovery(access_token, new_password)
    finally:
        try:
            client.logout(access_token)
        except AuthError:
            pass
        if state is not None:
            clear_recovery(state)


def _redirect_allowlist() -> list[str]:
    raw = os.environ.get("TRADERDASH_AUTH_REDIRECT_ALLOWLIST", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _redirect_structure_is_safe(url: str) -> bool:
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower()
    local = host in {"localhost", "127.0.0.1"}
    scheme_ok = parsed.scheme == "https" or (parsed.scheme == "http" and local)
    return bool(
        scheme_ok
        and host
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def _cooldown_active(state: Mapping[str, Any], now: datetime) -> bool:
    raw = str(state.get(RESET_AFTER_KEY) or "")
    if not raw:
        return False
    try:
        deadline = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return deadline > now


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
            _ops("CONFIG_ERROR", where="supabase")
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

    def logout_all(self, token: str) -> None:
        self._refuse_deleted_preview()
        self._request("POST", "/auth/v1/logout?scope=global", token=token)

    def request_password_reset(self, email: str, redirect_url: str) -> None:
        if not delivery_enabled() or not allowed_redirect(redirect_url):
            raise AuthError(RESET_UNAVAILABLE)
        quoted = urllib.parse.quote(redirect_url, safe="")
        status, _body = self._request(
            "POST",
            "/auth/v1/recover?redirect_to=" + quoted,
            {"email": str(email or "").strip()},
        )
        if status >= 500:
            _ops("AUTH_FAILURE", reason="recovery")
            raise AuthError("Supabase Auth er ikke tilgængelig.")
        if status == 429:
            raise AuthError(RESET_UNAVAILABLE)
        _ops("AUTH_RECOVERY_REQUEST")

    def signup(self, email: str, password: str, redirect_url: str, captcha_token: str) -> dict[str, Any]:
        """Create an unconfirmed Auth user. A session in the response is discarded."""
        from registration import registration_open

        if self.base_url.rstrip("/") == PREVIEW_ORIGIN or not registration_open():
            raise AuthError("Kontoen kunne ikke oprettes.")
        quoted = urllib.parse.quote(redirect_url, safe="")
        status, body = self._request(
            "POST",
            "/auth/v1/signup?redirect_to=" + quoted,
            {
                "email": str(email or "").strip(),
                "password": password,
                "gotrue_meta_security": {"captcha_token": str(captcha_token or "")},
            },
        )
        if status in {400, 422}:
            return {"created": False, "confirmed": False, "session_returned": False}
        if status != 200 or not isinstance(body, dict):
            raise AuthError("Kontoen kunne ikke oprettes.")
        session_returned = bool(body.get("access_token"))
        user = body.get("user") if isinstance(body.get("user"), dict) else body
        confirmed = bool(user.get("email_confirmed_at") or user.get("confirmed_at"))
        return {"created": True, "confirmed": confirmed, "session_returned": session_returned}

    def exchange_recovery(self, token_hash: str) -> str:
        """Exchange a recovery token hash for an access token. The refresh token is discarded."""
        if not delivery_enabled() or not str(token_hash or "").strip():
            raise AuthError(RESET_INVALID)
        status, body = self._request(
            "POST",
            "/auth/v1/verify",
            {"type": "recovery", "token_hash": str(token_hash)},
        )
        if status != 200 or not isinstance(body, dict):
            raise AuthError(RESET_INVALID)
        access_token = str(body.get("access_token") or "")
        if not access_token:
            raise AuthError(RESET_INVALID)
        return access_token

    def exchange_signup(self, token_hash: str) -> dict[str, Any]:
        """Confirm an address. The access token from Auth is not returned."""
        from registration import registration_open

        if self.base_url.rstrip("/") == PREVIEW_ORIGIN or not registration_open():
            raise AuthError("Linket er ikke gyldigt længere.")
        if not str(token_hash or "").strip():
            raise AuthError("Linket er ikke gyldigt længere.")
        status, body = self._request(
            "POST",
            "/auth/v1/verify",
            {"type": "signup", "token_hash": str(token_hash)},
        )
        if status != 200 or not isinstance(body, dict):
            raise AuthError("Linket er ikke gyldigt længere.")
        user = body.get("user") if isinstance(body.get("user"), dict) else {}
        user_id = str(user.get("id") or "")
        if not user_id:
            raise AuthError("Linket er ikke gyldigt længere.")
        return {"user_id": user_id, "confirmed": True, "expired": False}

    def update_password_from_recovery(self, token: str, new_password: str) -> None:
        if not delivery_enabled():
            raise AuthError(RESET_INVALID)
        if not str(token or "").strip():
            raise AuthError(RESET_INVALID)
        try:
            password_policy.require(new_password)
        except password_policy.PasswordRejected as exc:
            raise AuthError(str(exc)) from None
        status, _body = self._request("PUT", "/auth/v1/user", {"password": new_password}, token=token)
        if status in {401, 403}:
            raise AuthError(RESET_INVALID)
        if status != 200:
            raise AuthError("Adgangskoden kunne ikke opdateres.")

    def update_password(self, token: str, new_password: str) -> None:
        """Change the password for the current session on the configured project."""
        self._refuse_deleted_preview()
        if not str(token or "").strip():
            raise AuthError("Nulstillingen er ikke gyldig.")
        try:
            password_policy.require(new_password)
        except password_policy.PasswordRejected as exc:
            raise AuthError(str(exc)) from None
        status, _body = self._request("PUT", "/auth/v1/user", {"password": new_password}, token=token)
        if status in {401, 403}:
            raise AuthError("Nulstillingen er ikke gyldig.")
        if status != 200:
            raise AuthError("Adgangskoden kunne ikke opdateres.")

    def _refuse_deleted_preview(self) -> None:
        """The deleted preview project is not a valid Auth target."""
        if self.base_url.rstrip("/") == PREVIEW_ORIGIN:
            raise AuthError("Adgangskoden kunne ikke opdateres.")

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
    except (urllib.error.URLError, TimeoutError):
        _ops("AUTH_FAILURE", reason="unreachable")
        raise AuthError("Supabase Auth er ikke tilgængelig.") from None


def _decode(raw: bytes):
    if not raw:
        return {}
    try:
        return json.loads(raw.decode())
    except json.JSONDecodeError:
        return {}

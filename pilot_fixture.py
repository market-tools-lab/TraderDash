"""Synthetic preview fixtures. Not used by the migration itself.

Auth rows are created by a privileged insert because this preview has no
Auth Admin HTTP tool and public signup rejects the reserved test domain.
The migration module never imports this file and never updates auth.users.
"""

from __future__ import annotations

import re
import uuid

_EMAIL = re.compile(r"markettools-mig-[a-z0-9]+@example\.invalid")
_LEGACY_ID = re.compile(r"legacy-mig-[a-z0-9]+")
_PROTECTED_EMAIL = "markettools-auth-test@example.invalid"
_PROTECTED_USER = "63ffe985-0e7e-48bd-b41b-d1741330257a"


class FixtureRejected(Exception):
    """The fixture would touch a real address or the standing preview user."""


def auth_user_sql(user_id: str, email: str, password_hash: str) -> list[str]:
    checked_id = _checked_uuid(user_id)
    checked_email = _checked_email(email)
    checked_hash = _checked_hash(password_hash)
    return [
        "insert into auth.users ("
        "instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, "
        "raw_app_meta_data, raw_user_meta_data, created_at, updated_at, "
        "confirmation_token, recovery_token, email_change_token_new, email_change, "
        "email_change_token_current, reauthentication_token"
        ") values ("
        "'00000000-0000-0000-0000-000000000000', "
        f"'{checked_id}', 'authenticated', 'authenticated', '{checked_email}', "
        f"'{checked_hash}', now(), "
        """'{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, """
        "now(), now(), '', '', '', '', '', '')",
        "insert into auth.identities ("
        "user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at"
        ") values ("
        f"'{checked_id}', '{checked_id}', "
        f"jsonb_build_object('sub', '{checked_id}', 'email', '{checked_email}', 'email_verified', true), "
        "'email', now(), now(), now())",
    ]


def legacy_user_sql(user_id: str, email: str, password_hash: str, plan: str, status: str) -> str:
    checked_id = _checked_legacy_id(user_id)
    checked_email = _checked_email(email)
    checked_hash = _checked_hash(password_hash)
    if plan not in {"free", "nordic", "international"}:
        raise FixtureRejected("fixture plan is not in the legacy catalogue")
    if status not in {"free", "active", "trialing", "past_due", "incomplete", "cancelled", "expired"}:
        raise FixtureRejected("fixture status is not storable on public.users")
    return (
        "insert into public.users ("
        "user_id, email, password_hash, plan, subscription_status, created_at, updated_at"
        ") values ("
        f"'{checked_id}', '{checked_email}', '{checked_hash}', '{plan}', '{status}', "
        "'2026-11-04T12:00:00Z', '2026-11-04T12:00:00Z')"
    )


def cleanup_sql(auth_user_id: str, legacy_user_id: str) -> list[str]:
    checked_auth = _checked_uuid(auth_user_id)
    checked_legacy = _checked_legacy_id(legacy_user_id)
    if checked_auth == _PROTECTED_USER:
        raise FixtureRejected("refusing to delete the standing preview user")
    return [
        f"delete from auth.users where id = '{checked_auth}'::uuid "
        "and email like 'markettools-mig-%@example.invalid'",
        f"delete from public.users where user_id = '{checked_legacy}' "
        "and email like 'markettools-mig-%@example.invalid'",
    ]


def _checked_email(email: str) -> str:
    text = str(email or "").strip().lower()
    if text == _PROTECTED_EMAIL or not _EMAIL.fullmatch(text):
        raise FixtureRejected("fixture e-mail is not a reserved synthetic address")
    return text


def _checked_legacy_id(user_id: str) -> str:
    text = str(user_id or "")
    if not _LEGACY_ID.fullmatch(text):
        raise FixtureRejected("fixture legacy id is not synthetic")
    return text


def _checked_uuid(user_id: str) -> str:
    try:
        text = str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise FixtureRejected("fixture auth id is not a uuid") from None
    if text == _PROTECTED_USER:
        raise FixtureRejected("refusing to change the standing preview user")
    return text


def _checked_hash(password_hash: str) -> str:
    text = str(password_hash or "")
    if not text.startswith("$2b$") or "'" in text or len(text) > 80:
        raise FixtureRejected("fixture hash is not a bcrypt hash")
    return text

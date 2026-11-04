"""Password rules for the Supabase Auth pilot.

Legacy scrypt passwords are not part of this policy. A long passphrase is
enough. There is no expiry. The messages never repeat the password.
"""

from __future__ import annotations

MIN_LENGTH = 12
MAX_LENGTH = 128
_WEAK = {
    "passwordpassword",
    "123456789012",
    "qwertyuiop12",
    "traderdash123",
    "letmeinletmein",
    "adminadminadmin",
    "welcomewelcome",
    "changeme1234",
}


class PasswordRejected(Exception):
    """A neutral explanation. The message does not contain the password."""


def require(password: str) -> None:
    text = str(password or "")
    if len(text) < MIN_LENGTH or len(text) > MAX_LENGTH:
        raise PasswordRejected("Adgangskoden skal være mellem 12 og 128 tegn.")
    folded = text.strip().lower()
    if folded in _WEAK or len(set(folded)) == 1 or folded.isdigit():
        raise PasswordRejected("Adgangskoden er for svag.")


def matches(password: str, confirmation: str) -> bool:
    return str(password or "") == str(confirmation or "")

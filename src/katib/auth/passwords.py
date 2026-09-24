"""Password hashing with argon2id, plus token helpers for sessions, invites and API tokens."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD = 10
_hasher = PasswordHasher()
# Verifying against this when an account does not exist keeps timing similar for both cases.
_DUMMY_HASH = _hasher.hash("katib-dummy-password")


class WeakPassword(ValueError):
    """The password does not meet the minimum rules. The message is shown to the person."""


def check_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise WeakPassword(f"Use at least {MIN_PASSWORD} characters for the password.")
    if len(password) > 256:
        raise WeakPassword("That password is too long.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    """True when `password` matches `stored`. A missing hash still costs one verification."""
    try:
        return _hasher.verify(stored or _DUMMY_HASH, password) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    return _hasher.check_needs_rehash(stored)


def new_token() -> str:
    """A random value for cookies, invite links and API tokens."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are high-entropy, so a fast hash is enough. Only the hash is stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

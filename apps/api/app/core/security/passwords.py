"""Argon2id password hashing. No hand-rolled crypto (see docs/SECURITY.md §2)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerifyMismatchError

# argon2-cffi defaults are OWASP-reasonable for interactive login.
_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 1024  # guard against DoS via huge inputs


class WeakPasswordError(ValueError):
    """Raised when a password fails baseline policy."""


def validate_password_strength(plain: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(plain) <= MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters"
        )


def hash_password(plain: str) -> str:
    validate_password_strength(plain)
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, Argon2Error):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hashed)
    except (InvalidHashError, Argon2Error):
        return True


# A real hash of a throwaway value. Verify against this on unknown-user login so the
# request does the same argon2 work whether or not the account exists.
TIMING_GUARD_HASH: str = _hasher.hash("cedeon-login-timing-guard")

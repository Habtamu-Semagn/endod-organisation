"""Passwords, tokens, keyed hashes and the sealing of TOTP secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from functools import lru_cache
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_settings

# --- passwords ---------------------------------------------------------------------------

#: NIST SP 800-63B with a mandatory second factor: length, no composition rules.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

#: argon2id with the library's (RFC 9106 low-memory) defaults.
_hasher = PasswordHasher()

#: Very common passwords, refused outright (compared case-insensitively).
COMMON_PASSWORDS = frozenset("""
123456 123456789 12345678 1234567890 1234567 12345 123123 111111 000000 654321
password password1 password12 password123 password! passw0rd p@ssw0rd p@ssword pass1234
qwerty qwerty123 qwertyuiop qwerty12 1q2w3e4r 1q2w3e4r5t 1qaz2wsx zaq12wsx asdfghjk asdf1234
abc12345 abcd1234 abcdefgh iloveyou letmein1 letmein! welcome1 welcome123 welcome! sunshine
princess football baseball superman batman123 trustno1 dragon123 monkey123 starwars
master123 shadow123 michael1 jennifer computer internet whatever freedom1 changeme
changeme1 changeme123 default1 administrator admin123 admin1234 adminadmin root1234
secret123 test1234 testtest guest123 user1234 hello123 helloworld loveyou1 mypassword
11111111 22222222 88888888 12341234 11223344 87654321 00000000 99999999 123qweasd
qazwsxedc 147258369 987654321 1234qwer qwer1234 q1w2e3r4 a1b2c3d4 aa123456 ethiopia
ethiopia1 addisababa endod123 endodadmin endodhealth medpulse hospital1 hospital123
tenacare tenacare1 tenacare123 benefits1 employee1 pharmacy1
""".split())


def password_problem(password: str, email: Optional[str] = None) -> Optional[str]:
    """Why a password is not acceptable, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    lowered = password.strip().lower()
    if lowered in COMMON_PASSWORDS:
        return "This password is too common. Choose another one."
    if email and lowered in {email.strip().lower(), email.strip().lower().split("@")[0]}:
        return "The password must not be your email address."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        return _hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored)
    except InvalidHashError:
        return False


#: Checked against for unknown emails and accounts without a password, so
#: those cost the same one argon2 run as a real account with a wrong password.
DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


# --- tokens and keyed hashes -------------------------------------------------------------

def new_token() -> str:
    """A session token or setup link secret (256 bits)."""
    return secrets.token_urlsafe(32)


@lru_cache(maxsize=8)
def _derived(secret: str, purpose: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"endod-organisation",
                info=purpose.encode()).derive(secret.encode())


def _key(purpose: str) -> bytes:
    return _derived(get_settings().session_secret(), purpose)


def token_hash(token: str) -> str:
    """How session tokens and setup links are stored: HMAC-SHA256 under a key
    derived from SESSION_SECRET (a database copy alone cannot use or test them)."""
    return hmac.new(_key("token"), token.encode(), hashlib.sha256).hexdigest()


def email_fingerprint(email: str) -> str:
    """How an email typed for an unknown account is logged: never the input,
    only ``unknown:`` and 8 hex characters of a keyed hash of it (normalised),
    enough to see repeated attempts at the same name."""
    digest = hmac.new(_key("audit-email"), email.strip().lower().encode(), hashlib.sha256).hexdigest()
    return f"unknown:{digest[:8]}"


# --- recovery codes ----------------------------------------------------------------------

RECOVERY_CODE_COUNT = 10
#: No 0/O, 1/I/L: codes are read off paper.
_RECOVERY_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"


def new_recovery_code() -> str:
    """Like ``7k2m-q9xp-4tnw`` (12 characters, ~59 bits)."""
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.lower() if ch.isalnum())


def recovery_code_hash(code: str) -> str:
    return hmac.new(_key("recovery"), normalize_recovery_code(code).encode(), hashlib.sha256).hexdigest()


# --- TOTP secrets at rest ----------------------------------------------------------------

def seal(plaintext: str) -> str:
    """Encrypt a TOTP secret (AES-256-GCM under a key derived from SESSION_SECRET)."""
    nonce = os.urandom(12)
    sealed = AESGCM(_key("totp")).encrypt(nonce, plaintext.encode(), b"totp")
    return "v1:" + base64.urlsafe_b64encode(nonce + sealed).decode()


def unseal(stored: str) -> str:
    if not stored.startswith("v1:"):
        raise ValueError("unknown sealed format")
    raw = base64.urlsafe_b64decode(stored[3:].encode())
    return AESGCM(_key("totp")).decrypt(raw[:12], raw[12:], b"totp").decode()

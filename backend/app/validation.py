"""Normalising and checking what admins type (or import): phone numbers,
Endod ids, TINs, receipt numbers, payout accounts, names."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from app.models import PayoutMethod


class Invalid(ValueError):
    """A value that cannot be accepted; the message is shown to the admin."""


_SPACES = re.compile(r"\s+")


def text(value: Optional[str], field: str, *, min_len: int = 1, max_len: int = 120) -> str:
    """Printable text, spaces collapsed, NFC. Control characters are refused."""
    value = unicodedata.normalize("NFC", value or "")
    value = _SPACES.sub(" ", value).strip()
    if any(not ch.isprintable() for ch in value):
        raise Invalid(f"{field} contains characters that are not allowed.")
    if len(value) < min_len:
        raise Invalid(f"{field} is required." if min_len == 1 else f"{field} must be at least {min_len} characters.")
    if len(value) > max_len:
        raise Invalid(f"{field} must be at most {max_len} characters.")
    return value


def optional_text(value: Optional[str], field: str, *, max_len: int = 120) -> Optional[str]:
    value = _SPACES.sub(" ", value or "").strip()
    return text(value, field, max_len=max_len) if value else None


_PHONE_DIGITS = re.compile(r"[\s()\-.]")


def phone(value: Optional[str]) -> str:
    """An Ethiopian mobile number as E.164: +2519XXXXXXXX or +2517XXXXXXXX.
    Accepts 0911..., 911..., 251911... and +251911..."""
    raw = _PHONE_DIGITS.sub("", value or "")
    if raw.startswith("+"):
        raw = raw[1:]
        if not raw.startswith("251"):
            raise Invalid("Phone must be an Ethiopian mobile number, like +251911234567.")
    if raw.startswith("251"):
        rest = raw[3:]
    elif raw.startswith("0"):
        rest = raw[1:]
    else:
        rest = raw
    if not re.fullmatch(r"[79][0-9]{8}", rest):
        raise Invalid("Phone must be an Ethiopian mobile number, like +251911234567.")
    return f"+251{rest}"


def endod_id(value: Optional[str]) -> Optional[str]:
    """The Endod health card id: DE followed by 6 digits (spaces and dashes ignored)."""
    raw = re.sub(r"[\s\-]", "", value or "").upper()
    if not raw:
        return None
    if not re.fullmatch(r"DE[0-9]{6}", raw):
        raise Invalid("Endod ID must be DE followed by 6 digits, like DE123456.")
    return raw


def tin(value: Optional[str], field: str = "TIN") -> str:
    """An Ethiopian TIN: 10 digits (spaces and dashes ignored)."""
    raw = re.sub(r"[\s\-]", "", value or "")
    if not re.fullmatch(r"[0-9]{10}", raw):
        raise Invalid(f"{field} must be 10 digits.")
    return raw


def receipt_number(value: Optional[str]) -> str:
    """Upper case, no spaces: "fs 00123" and "FS00123" are the same receipt."""
    raw = re.sub(r"\s", "", value or "").upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9/\-]{0,39}", raw):
        raise Invalid("Receipt number must be 1-40 letters, digits, / or -.")
    return raw


def employee_number(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/\-_.]{0,39}", raw):
        raise Invalid("Employee number must be 1-40 letters, digits, / - _ or .")
    return raw


def payout(method: Optional[str], account: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """(method, account), both or neither. Bank accounts are 8-20 digits;
    Telebirr accounts are the wallet's mobile number (E.164)."""
    method = (method or "").strip().lower() or None
    account = (account or "").strip() or None
    if method is None and account is None:
        return None, None
    if method not in PayoutMethod.ALL:
        raise Invalid(f"Payout method must be one of {', '.join(PayoutMethod.ALL)}.")
    if account is None:
        raise Invalid("Enter the payout account (or the Telebirr phone number).")
    if method == PayoutMethod.TELEBIRR:
        try:
            return method, phone(account)
        except Invalid as exc:
            raise Invalid("Telebirr account must be the wallet's Ethiopian mobile number.") from exc
    digits = re.sub(r"[\s\-]", "", account)
    if not re.fullmatch(r"[0-9]{8,20}", digits):
        raise Invalid("Bank account number must be 8-20 digits.")
    return method, digits

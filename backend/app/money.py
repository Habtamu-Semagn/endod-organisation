"""Money: always an integer number of santim (1 ETB = 100 santim).

Nothing here (or anywhere in this service) uses floats. Amounts arrive from
the web app as integers in santim; text such as "1,234.50" (the CLI, CSV) is
parsed digit by digit.
"""

from __future__ import annotations

import re

SANTIM_PER_ETB = 100
#: The largest single amount accepted anywhere (ETB 100,000,000.00).
MAX_SANTIM = 10_000_000_000

_ETB_TEXT = re.compile(r"^([0-9]{1,12})(?:\.([0-9]{1,2}))?$")


def parse_etb(text: str) -> int:
    """"1,234.5" -> 123450. Refuses negatives, more than 2 decimals, and anything else."""
    cleaned = (text or "").strip().replace(",", "").replace(" ", "")
    if cleaned.upper().startswith("ETB"):
        cleaned = cleaned[3:]
    match = _ETB_TEXT.match(cleaned)
    if not match:
        raise ValueError("Enter an amount in birr, like 1250 or 1,250.50.")
    whole, fraction = match.group(1), (match.group(2) or "").ljust(2, "0")
    santim = int(whole) * SANTIM_PER_ETB + int(fraction)
    if santim > MAX_SANTIM:
        raise ValueError("That amount is too large.")
    return santim


def format_etb(santim: int, with_currency: bool = False) -> str:
    """123450 -> "1,234.50" (or "ETB 1,234.50")."""
    if not isinstance(santim, int) or isinstance(santim, bool):
        raise TypeError("santim must be an int")
    sign = "-" if santim < 0 else ""
    whole, fraction = divmod(abs(santim), SANTIM_PER_ETB)
    text = f"{sign}{whole:,}.{fraction:02d}"
    return f"ETB {text}" if with_currency else text


def plain_etb(santim: int) -> str:
    """123450 -> "1234.50": for bank files (no thousands separator)."""
    whole, fraction = divmod(santim, SANTIM_PER_ETB)
    return f"{whole}.{fraction:02d}"


def percent_of(amount: int, percent: int) -> int:
    """``percent`` % of ``amount`` santim, rounded half up to the santim."""
    if amount < 0 or not 0 <= percent <= 100:
        raise ValueError("amount must be >= 0 and percent 0-100")
    return (amount * percent + 50) // 100


def line_total(quantity: int, unit_price: int) -> int:
    return quantity * unit_price


def split_claim(total: int, copay_percent: int, remaining_limit: int) -> tuple[int, int, int]:
    """How a claim of ``total`` santim is shared, given the employee's co-pay
    and what is left of their annual limit.

    Returns (copay, share, payable): the employee's co-pay, the organisation's
    share before the limit (total - copay), and what the organisation pays
    back (the share, capped at the remaining limit, never below zero).
    """
    copay = percent_of(total, copay_percent)
    share = total - copay
    payable = max(0, min(share, remaining_limit))
    return copay, share, payable

"""Santim arithmetic: integers only, rounding of the co-pay, the limit cap."""

import ast
from pathlib import Path

import pytest

from app import money


@pytest.mark.parametrize("text, santim", [
    ("0", 0), ("1", 100), ("12.5", 1250), ("12.50", 1250), ("12.05", 1205), ("1,234.56", 123456),
    ("ETB 1,000", 100000), (" 99.99 ", 9999), ("0.01", 1), ("100000000", 10_000_000_000),
])
def test_parse_etb(text, santim):
    assert money.parse_etb(text) == santim


@pytest.mark.parametrize("text", ["", "-5", "1.234", "1e3", "abc", "1.2.3", "100000000.01", "nan", "0x10", "١٢"])
def test_parse_etb_refuses(text):
    with pytest.raises(ValueError):
        money.parse_etb(text)


@pytest.mark.parametrize("santim, text", [(0, "0.00"), (1, "0.01"), (99, "0.99"), (100, "1.00"),
                                          (123456, "1,234.56"), (100_000_000_00, "100,000,000.00"),
                                          (-150, "-1.50")])
def test_format_etb(santim, text):
    assert money.format_etb(santim) == text
    assert money.format_etb(santim, True) == f"ETB {text}"


def test_format_refuses_floats_and_bools():
    with pytest.raises(TypeError):
        money.format_etb(12.5)
    with pytest.raises(TypeError):
        money.format_etb(True)


def test_plain_etb_has_no_separators():
    assert money.plain_etb(123456789) == "1234567.89"
    assert money.plain_etb(5) == "0.05"


@pytest.mark.parametrize("amount, percent, expected", [
    (10000, 0, 0), (10000, 100, 10000), (10000, 10, 1000), (10001, 10, 1000),  # 1000.1 -> 1000
    (10005, 10, 1001),  # 1000.5 -> 1001 (half up)
    (1, 50, 1),  # 0.5 -> 1
    (3, 33, 1),  # 0.99 -> 1
    (199, 25, 50),  # 49.75 -> 50
    (10_000_000_000, 15, 1_500_000_000),
])
def test_percent_of_rounds_half_up_in_integers(amount, percent, expected):
    assert money.percent_of(amount, percent) == expected


def test_percent_of_refuses_bad_input():
    with pytest.raises(ValueError):
        money.percent_of(-1, 10)
    with pytest.raises(ValueError):
        money.percent_of(100, 101)


@pytest.mark.parametrize("total, copay_percent, remaining, expected", [
    (100_000, 0, 1_000_000, (0, 100_000, 100_000)),  # all paid back
    (100_000, 10, 1_000_000, (10_000, 90_000, 90_000)),  # co-pay off the top
    (100_000, 10, 90_000, (10_000, 90_000, 90_000)),  # exactly the remaining limit
    (100_000, 10, 89_999, (10_000, 90_000, 89_999)),  # capped by one santim
    (100_000, 0, 1, (0, 100_000, 1)),
    (100_000, 0, 0, (0, 100_000, 0)),  # nothing left
    (100_000, 100, 1_000_000, (100_000, 0, 0)),  # the employee bears it all
    (100_000, 10, -5, (10_000, 90_000, 0)),  # never negative
])
def test_split_claim(total, copay_percent, remaining, expected):
    copay, share, payable = money.split_claim(total, copay_percent, remaining)
    assert (copay, share, payable) == expected
    assert copay + share == total
    assert all(isinstance(v, int) for v in (copay, share, payable))


def test_no_floats_in_the_money_code():
    """No float literals or float() calls where amounts are computed."""
    root = Path(__file__).resolve().parents[1] / "app"
    for name in ("money.py", "policy.py", "claims_intake.py", "api/claims.py", "api/batches.py", "api/reports.py",
                 "api/overview.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), (name, node.lineno)
            assert not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "float"), (name, node.lineno)
            assert not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)), (name, node.lineno)

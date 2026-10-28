"""What a connection may do: technical scope names (the API) and plain words (the portal)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

EMPLOYEES_WRITE = "employees.write"
#: Changing where reimbursements are paid: separate, off by default, and every change is held (app.payout_holds).
EMPLOYEES_PAYOUT_WRITE = "employees.payout.write"
EMPLOYEES_READ = "employees.read"
#: Full payout account numbers in reads (otherwise masked to the last 4 digits).
EMPLOYEES_PAYOUT_READ = "employees.payout.read"
CLAIMS_READ = "claims.read"
PAYMENTS_READ = "payments.read"
WEBHOOKS = "webhooks"

#: scope -> (label in the portal, longer description). In the portal's order.
SCOPES: Dict[str, Tuple[str, str]] = {
    EMPLOYEES_WRITE: ("Sync employees from your HR system",
                      "Add and update employees by employee number, and deactivate them."),
    EMPLOYEES_PAYOUT_WRITE: ("Change employees' payout accounts (bank / Telebirr)",
                             "Set employees' payout method and account in a sync. Every change is held for 24 hours "
                             "before it can be paid, unless an admin confirms it in the portal."),
    EMPLOYEES_READ: ("See employee list", "Read the employees and their dependants (payout accounts masked to the "
                                          "last 4 digits)."),
    EMPLOYEES_PAYOUT_READ: ("See employees' full payout accounts", "Read payout account numbers in full."),
    CLAIMS_READ: ("See claims and their status", "Read claims and whether they are pending, approved, rejected "
                                                 "or paid (never the receipt files)."),
    PAYMENTS_READ: ("See payments", "Read payout batches and their status."),
    WEBHOOKS: ("Get notified when claims are approved or paid",
               "Receive events: claim approved, claim rejected, batch paid, employee changed."),
}
ALL: Tuple[str, ...] = tuple(SCOPES)
#: A scope that only makes sense with another (refused alone).
REQUIRES: Dict[str, str] = {EMPLOYEES_PAYOUT_WRITE: EMPLOYEES_WRITE, EMPLOYEES_PAYOUT_READ: EMPLOYEES_READ}
#: Off by default; the portal warns before granting them.
SENSITIVE: Tuple[str, ...] = (EMPLOYEES_PAYOUT_WRITE, EMPLOYEES_PAYOUT_READ)


def parse(value: Optional[str]) -> List[str]:
    """Space-separated scopes, in order, without repeats (unknown ones kept: the caller checks)."""
    return list(dict.fromkeys((value or "").split()))


def unknown(scopes: List[str]) -> List[str]:
    return [s for s in scopes if s not in SCOPES]


def ordered(scopes) -> List[str]:
    """Known scopes in the portal's order."""
    wanted = set(scopes)
    return [s for s in ALL if s in wanted]


def describe() -> List[Dict[str, str]]:
    return [{"scope": name, "label": label, "description": description}
            for name, (label, description) in SCOPES.items()]

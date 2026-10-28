"""What a connection may do: technical scope names (the API) and plain words (the portal)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

EMPLOYEES_WRITE = "employees.write"
EMPLOYEES_READ = "employees.read"
CLAIMS_READ = "claims.read"
PAYMENTS_READ = "payments.read"
WEBHOOKS = "webhooks"

#: scope -> (label in the portal, longer description). In the portal's order.
SCOPES: Dict[str, Tuple[str, str]] = {
    EMPLOYEES_WRITE: ("Sync employees from your HR system",
                      "Add and update employees by employee number, and deactivate them."),
    EMPLOYEES_READ: ("See employee list", "Read the employees, their dependants and payout details."),
    CLAIMS_READ: ("See claims and their status", "Read claims and whether they are pending, approved, rejected "
                                                 "or paid (never the receipt files)."),
    PAYMENTS_READ: ("See payments", "Read payout batches and their status."),
    WEBHOOKS: ("Get notified when claims are approved or paid",
               "Receive events: claim approved, claim rejected, batch paid, employee changed."),
}
ALL: Tuple[str, ...] = tuple(SCOPES)


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

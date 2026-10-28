"""Holds on payout accounts changed by a connected system.

A system with ``employees.payout.write`` can change where an employee's
reimbursements are paid. Whoever holds its secret could redirect payouts, so
every such change is (app.integrations.data):

* audited, with the accounts masked to their last 4 digits;
* recorded in ``integration_payout_changes`` (masked), listed under the
  connection's Advanced section and announced on the Overview
  ("N payout accounts changed by <connection> in the last 24 h");
* **held**: the employee's approved claims stay out of payout batches until
  24 hours have passed, unless an admin confirms the change in the portal
  first (with a fresh code). An admin who sets the payout details in the
  portal (with a fresh code) confirms any held change of that employee too.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, select, update

from app.db import utcnow
from app.models import IntegrationClient, IntegrationPayoutChange

HOLD = timedelta(hours=24)
#: The Overview's alert looks this far back.
RECENT = timedelta(hours=24)


def held_employee_ids(session, organisation_id: str, now: Optional[datetime] = None) -> Set[str]:
    """Employees whose payout details a connected system changed less than 24 hours ago, unconfirmed."""
    now = now or utcnow()
    return set(session.scalars(select(IntegrationPayoutChange.employee_id).where(
        IntegrationPayoutChange.organisation_id == organisation_id, IntegrationPayoutChange.confirmed_at.is_(None),
        IntegrationPayoutChange.hold_until > now)))


def confirm_for_employee(session, organisation_id: str, employee_id: str, admin_id: str) -> int:
    """An admin set this employee's payout details in the portal (with a fresh code): held changes end."""
    now = utcnow()
    return session.execute(update(IntegrationPayoutChange).where(
        IntegrationPayoutChange.organisation_id == organisation_id, IntegrationPayoutChange.employee_id == employee_id,
        IntegrationPayoutChange.confirmed_at.is_(None), IntegrationPayoutChange.hold_until > now)
        .values(confirmed_at=now, confirmed_by=admin_id)).rowcount or 0


def recent_by_connection(session, organisation_id: str) -> List[Dict[str, Any]]:
    """The Overview's alert: per connection, payout accounts it changed in the last 24 hours."""
    now = utcnow()
    rows = session.execute(
        select(IntegrationClient.id, IntegrationClient.name, func.count(IntegrationPayoutChange.id),
               func.count(IntegrationPayoutChange.id).filter(
                   IntegrationPayoutChange.confirmed_at.is_(None), IntegrationPayoutChange.hold_until > now))
        .join(IntegrationClient, (IntegrationClient.id == IntegrationPayoutChange.client_pk)
              & (IntegrationClient.organisation_id == IntegrationPayoutChange.organisation_id))
        .where(IntegrationPayoutChange.organisation_id == organisation_id,
               IntegrationPayoutChange.created_at > now - RECENT)
        .group_by(IntegrationClient.id, IntegrationClient.name).order_by(IntegrationClient.name)).all()
    return [{"connection_id": cid, "connection": name, "changed": int(changed), "held": int(held)}
            for cid, name, changed, held in rows]

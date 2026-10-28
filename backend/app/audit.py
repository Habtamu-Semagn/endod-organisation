"""The audit log: every sign-in step, enrolment, and change to employees,
policies, claims and payout batches, with the organisation it concerns."""

from __future__ import annotations

import ipaddress
import json
from typing import Any, Dict, Optional

from fastapi import Request

from app import rls
from app.db import PLATFORM_KEY, new_id, utcnow
from app.models import AuditEvent, AuditResult

# Sign-in and accounts.
SIGN_IN = "sign_in"
SIGN_IN_PASSWORD = "sign_in_password"
SIGN_OUT = "sign_out"
LOCKED_OUT = "account_locked"
BACKOFF = "account_backoff"
CODE_BACKOFF = "account_code_backoff"
SETUP_LINK = "setup_link"
SETUP_COMPLETED = "setup_completed"
ENROLMENT_STARTED = "enrolment_started"
ENROLLED = "totp_enrolled"
REAUTH = "reauth"
ORG_CREATED = "organisation_created"
ADMIN_CREATED = "admin_created"
TWO_FACTOR_RESET = "admin_2fa_reset"
ADMIN_DISABLED = "admin_disabled"
# Employees.
EMPLOYEE_CREATED = "employee_created"
EMPLOYEE_UPDATED = "employee_updated"
EMPLOYEE_PAYOUT_CHANGED = "employee_payout_changed"
EMPLOYEE_DEACTIVATED = "employee_deactivated"
EMPLOYEE_ACTIVATED = "employee_activated"
EMPLOYEES_IMPORTED = "employees_imported"
EMPLOYEES_EXPORTED = "employees_exported"
DEPENDANT_ADDED = "dependant_added"
DEPENDANT_REMOVED = "dependant_removed"
# Policies and settings.
POLICY_UPDATED = "policy_updated"
EMPLOYEE_POLICY_UPDATED = "employee_policy_updated"
EMPLOYEE_POLICY_REMOVED = "employee_policy_removed"
PAYOUT_SETTINGS_UPDATED = "payout_settings_updated"
# Claims.
RECEIPT_UPLOADED = "receipt_uploaded"
RECEIPT_VIEWED = "receipt_viewed"
CLAIM_CREATED = "claim_created"
CLAIM_APPROVED = "claim_approved"
CLAIM_REJECTED = "claim_rejected"
# Payouts and reports.
BATCH_CREATED = "batch_created"
BATCH_EXPORTED = "batch_exported"
BATCH_PAID = "batch_paid"
BATCH_CANCELLED = "batch_cancelled"
REPORT_EXPORTED = "report_exported"
# Company applications (docs/company-onboarding.md) and Endod's review of them.
APPLICATION_STARTED = "application_started"
APPLICATION_SAVED = "application_saved"
APPLICATION_DOCUMENT_UPLOADED = "application_document_uploaded"
APPLICATION_SUBMITTED = "application_submitted"
APPLICATION_APPROVED = "application_approved"
APPLICATION_REJECTED = "application_rejected"
APPLICATION_DOCUMENT_VIEWED = "application_document_viewed"
ORG_SUSPENDED = "organisation_suspended"
ORG_REACTIVATED = "organisation_reactivated"
APPLICATION_CLOSED = "application_closed"
APPLICATION_EXPIRED = "application_expired"
SESSIONS_REVOKED = "sessions_revoked"
# The integration API (app/integrations): connections changed by admins, and what connected systems do.
INTEGRATION_CONNECTED = "integration_connected"
INTEGRATION_DISCONNECTED = "integration_disconnected"
INTEGRATION_SECRET_ROTATED = "integration_secret_rotated"
INTEGRATION_IPS_SET = "integration_ips_set"
INTEGRATION_PUBLIC_KEYS_SET = "integration_public_keys_set"
INTEGRATION_WEBHOOK_SET = "integration_webhook_set"
INTEGRATION_WEBHOOK_REMOVED = "integration_webhook_removed"
INTEGRATION_WEBHOOK_SECRET_ROTATED = "integration_webhook_secret_rotated"
INTEGRATION_WEBHOOK_TESTED = "integration_webhook_tested"
INTEGRATION_TOKEN_ISSUED = "integration_token_issued"
INTEGRATION_CALL_REFUSED = "integration_call_refused"
INTEGRATION_DATA_READ = "integration_data_read"
INTEGRATION_EMPLOYEES_SYNCED = "integration_employees_synced"
INTEGRATION_ACTIONS = (
    INTEGRATION_CONNECTED, INTEGRATION_DISCONNECTED, INTEGRATION_SECRET_ROTATED, INTEGRATION_IPS_SET,
    INTEGRATION_PUBLIC_KEYS_SET, INTEGRATION_WEBHOOK_SET, INTEGRATION_WEBHOOK_REMOVED,
    INTEGRATION_WEBHOOK_SECRET_ROTATED, INTEGRATION_WEBHOOK_TESTED, INTEGRATION_TOKEN_ISSUED, INTEGRATION_CALL_REFUSED,
    INTEGRATION_DATA_READ, INTEGRATION_EMPLOYEES_SYNCED,
)

ACTIONS = (
    APPLICATION_STARTED, APPLICATION_SAVED, APPLICATION_DOCUMENT_UPLOADED, APPLICATION_SUBMITTED,
    APPLICATION_APPROVED, APPLICATION_REJECTED, APPLICATION_DOCUMENT_VIEWED, ORG_SUSPENDED, ORG_REACTIVATED,
    APPLICATION_CLOSED, APPLICATION_EXPIRED, SESSIONS_REVOKED,
    SIGN_IN, SIGN_IN_PASSWORD, SIGN_OUT, LOCKED_OUT, BACKOFF, CODE_BACKOFF, SETUP_LINK, SETUP_COMPLETED, ENROLMENT_STARTED,
    ENROLLED, REAUTH, ORG_CREATED, ADMIN_CREATED, TWO_FACTOR_RESET, ADMIN_DISABLED,
    EMPLOYEE_CREATED, EMPLOYEE_UPDATED, EMPLOYEE_PAYOUT_CHANGED, EMPLOYEE_DEACTIVATED, EMPLOYEE_ACTIVATED, EMPLOYEES_IMPORTED,
    EMPLOYEES_EXPORTED, DEPENDANT_ADDED, DEPENDANT_REMOVED,
    POLICY_UPDATED, EMPLOYEE_POLICY_UPDATED, EMPLOYEE_POLICY_REMOVED, PAYOUT_SETTINGS_UPDATED,
    RECEIPT_UPLOADED, RECEIPT_VIEWED, CLAIM_CREATED, CLAIM_APPROVED, CLAIM_REJECTED,
    BATCH_CREATED, BATCH_EXPORTED, BATCH_PAID, BATCH_CANCELLED, REPORT_EXPORTED,
    *INTEGRATION_ACTIONS,
)


def record(session, action: str, result: str, *, organisation_id: Optional[str] = None,
           admin_id: Optional[str] = None, admin_email: Optional[str] = None, ip: Optional[str] = None,
           target_type: Optional[str] = None, target_id: Optional[str] = None, target_name: Optional[str] = None,
           detail: Optional[Dict[str, Any]] = None) -> None:
    assert result in AuditResult.ALL
    assert action in ACTIONS, action
    event = AuditEvent(
        id=new_id(), at=utcnow(), action=action, result=result, organisation_id=organisation_id, admin_id=admin_id,
        admin_email=(admin_email or "")[:254] or None, ip=(ip or "")[:64] or None,
        target_type=target_type, target_id=(target_id or "")[:64] or None,
        target_name=(target_name or "")[:200] or None,
        detail=json.dumps(detail, ensure_ascii=False)[:4000] if detail else None,
    )
    if organisation_id is None and not session.info.get(PLATFORM_KEY) and rls.postgres(session):
        # A tenant appends only its own organisation's events (row-level
        # security); one that concerns no organisation goes through the one
        # function that may append it (organisation and admin always empty).
        assert admin_id is None, "an event of an admin names the admin's organisation"
        session.flush()  # keep the order of the events before it
        rls.record_orgless_event(session, event)
        return
    session.add(event)


def by(session, principal, action: str, result: str = AuditResult.SUCCESS, **kwargs) -> None:
    """An event done by the signed-in admin (app.auth.Principal), in their organisation."""
    record(session, action, result, organisation_id=principal.organisation_id, admin_id=principal.admin_id,
           admin_email=principal.email, ip=principal.ip, **kwargs)


CLIENT_IP_HEADER = "x-endod-client-ip"


def client_address(request: Request) -> str:
    """The visitor's address, as the web app's BFF says (X-Endod-Client-IP,
    which our nginx sets and the BFF passes on). Only requests carrying the
    BFF secret get this far (app.main), so nobody else can choose it.
    X-Forwarded-For is ignored."""
    value = request.headers.get(CLIENT_IP_HEADER, "").strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return "unknown"

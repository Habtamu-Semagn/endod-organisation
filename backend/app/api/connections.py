"""`/connections`: a company's own systems connected to the integration API,
managed in the portal ("Connect your system"). Admins of approved
organisations only (``current_admin``: an organisation still applying, or
suspended, gets nothing).

Connecting a system, rotating its secret, disconnecting it and every change
under Advanced (addresses, public keys, the webhook and its secret) need a
fresh authenticator code (``fresh_admin``), and are audited (ids, names,
scopes and addresses; never a secret). Secrets are shown once, in the answer
that creates them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app import audit
from app.auth import Principal, current_admin, fresh_admin
from app.db import ensure_aware, iso, tenant_session, utcnow
from app.errors import ApiError
from app.integrations import clients, jose, scopes as S, tokens, webhooks
from app.models import (
    DeliveryStatus, Employee, IntegrationAuth, IntegrationClient, IntegrationMode, IntegrationPayoutChange,
    IntegrationRequest, OrgAdmin, WebhookDelivery,
)
from app.tenancy import owned

router = APIRouter(prefix="/connections", tags=["connections"])

MAX_CONNECTIONS = 20
RECENT = 50


class NewConnection(BaseModel):
    name: str = Field(max_length=200)
    scopes: List[str] = Field(min_length=1, max_length=len(S.ALL))
    mode: str = Field(default=IntegrationMode.LIVE, max_length=8)
    webhook_url: Optional[str] = Field(default=None, max_length=600)


class IpRestriction(BaseModel):
    #: Addresses or ranges; empty: any address.
    allowed_ips: List[str] = Field(default_factory=list, max_length=clients.MAX_CIDRS)


class PublicKeys(BaseModel):
    #: A JWKS, as JSON text or an object.
    jwks: Union[str, Dict[str, Any]]


class Webhook(BaseModel):
    #: null removes the webhook.
    url: Optional[str] = Field(default=None, max_length=600)


def bad(message: str) -> ApiError:
    return ApiError(400, message, "VALIDATION_ERROR")


def _payload(session, c: IntegrationClient) -> Dict[str, Any]:
    granted = S.ordered(S.parse(c.scopes))
    author = session.scalar(select(OrgAdmin.name).where(OrgAdmin.id == c.created_by,
                                                        OrgAdmin.organisation_id == c.organisation_id)) \
        if c.created_by else None
    keys = 0
    if c.jwks and c.auth_method == IntegrationAuth.PRIVATE_KEY_JWT:
        try:
            keys = len(jose.parse_jwks(c.jwks))
        except jose.JoseError:
            keys = 0
    return {
        "id": c.id, "name": c.name, "client_id": c.client_id, "mode": c.mode, "scopes": granted,
        "abilities": [S.SCOPES[s][0] for s in granted], "auth_method": c.auth_method,
        "allowed_ips": clients.stored_cidrs(c.allowed_cidrs), "webhook_url": c.webhook_url,
        "public_keys": keys, "created_at": iso(c.created_at), "created_by": author,
        "last_used_at": iso(c.last_used_at), "revoked_at": iso(c.revoked_at),
    }


def _about() -> Dict[str, Any]:
    base = tokens.public_url()
    return {"api_url": base, "token_url": tokens.token_url(), "docs_url": f"{base}/docs",
            "openapi_url": f"{base}/openapi.json", "jwks_url": f"{base}/.well-known/jwks.json",
            "scopes": S.describe()}


def _client(session, principal: Principal, connection_id: str, lock: bool = True) -> IntegrationClient:
    return owned(session, IntegrationClient, connection_id, principal.organisation_id, lock=lock)


def _live(client: IntegrationClient) -> None:
    if client.revoked_at is not None:
        raise ApiError(409, "This system was disconnected.", "DISCONNECTED")


def _webhook_url(url: Optional[str]) -> str:
    try:
        return clients.check_webhook_url(url or "")
    except clients.WebhookUrlError as exc:
        raise bad(str(exc)) from exc


def _name(value: str) -> str:
    from app import validation

    try:
        return validation.text(value, "The name", min_len=2, max_len=80)
    except validation.Invalid as exc:
        raise bad(str(exc)) from exc


def _record(session, principal: Principal, action: str, client: IntegrationClient, **detail) -> None:
    audit.by(session, principal, action, target_type="integration", target_id=client.id, target_name=client.name,
             detail={"client_id": client.client_id, **detail})


@router.get("")
def list_connections(principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        rows = session.scalars(select(IntegrationClient).where(
            IntegrationClient.organisation_id == principal.organisation_id, IntegrationClient.revoked_at.is_(None))
            .order_by(IntegrationClient.created_at.desc()))
        return {"items": [_payload(session, c) for c in rows], **_about()}


@router.post("", status_code=201)
def connect(body: NewConnection, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    """A new connection. The answer holds the client secret (and the webhook
    secret, if any): shown this once, never again."""
    name = _name(body.name)
    unknown = S.unknown(body.scopes)
    if unknown:
        raise bad(f"Unknown abilities: {', '.join(unknown)[:200]}.")
    if body.mode not in IntegrationMode.ALL:
        raise bad("Choose Live or Test.")
    granted = S.ordered(body.scopes)
    for scope, needs in S.REQUIRES.items():
        if scope in granted and needs not in granted:
            raise bad(f"\"{S.SCOPES[scope][0]}\" needs \"{S.SCOPES[needs][0]}\" too.")
    webhook_url = None
    if S.WEBHOOKS in granted:
        webhook_url = _webhook_url(body.webhook_url)
    elif body.webhook_url:
        raise bad("An address for notifications needs \"Get notified when claims are approved or paid\".")
    secret = clients.new_secret()
    webhook_secret = clients.new_webhook_secret() if webhook_url else None
    with tenant_session(principal.organisation_id) as session:
        active = session.scalar(select(func.count()).select_from(IntegrationClient).where(
            IntegrationClient.organisation_id == principal.organisation_id,
            IntegrationClient.revoked_at.is_(None))) or 0
        if active >= MAX_CONNECTIONS:
            raise ApiError(409, f"At most {MAX_CONNECTIONS} systems can be connected; disconnect one first.",
                           "TOO_MANY_CONNECTIONS")
        client = IntegrationClient(
            organisation_id=principal.organisation_id, client_id=clients.new_client_id(body.mode), name=name,
            scopes=" ".join(granted), mode=body.mode, auth_method=IntegrationAuth.SECRET,
            secret_hash=clients.hash_secret(secret), webhook_url=webhook_url,
            webhook_secret=clients.seal_webhook_secret(webhook_secret) if webhook_secret else None,
            created_by=principal.admin_id)
        session.add(client)
        session.flush()
        _record(session, principal, audit.INTEGRATION_CONNECTED, client, scopes=granted, mode=client.mode,
                webhook=clients.audit_url(webhook_url))
        return {"connection": _payload(session, client), "client_secret": secret, "webhook_secret": webhook_secret,
                **_about()}


@router.get("/{connection_id}")
def read_connection(connection_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id, lock=False)
        return {"connection": _payload(session, client), **_about()}


@router.post("/{connection_id}/disconnect")
def disconnect(connection_id: str, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    """Stops the system at once: no new tokens, and its current token is refused on the next call."""
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id)
        _live(client)
        client.revoked_at = utcnow()
        client.secret_hash = None
        client.webhook_secret = None
        # Events waiting for it are dropped (bodies too).
        session.execute(update(WebhookDelivery).where(
            WebhookDelivery.organisation_id == principal.organisation_id, WebhookDelivery.client_pk == client.id,
            WebhookDelivery.status == DeliveryStatus.PENDING)
            .values(status=DeliveryStatus.FAILED, body=None, next_attempt_at=None,
                    last_error="the connection was removed"))
        _record(session, principal, audit.INTEGRATION_DISCONNECTED, client)
        return {"connection": _payload(session, client)}


@router.post("/{connection_id}/rotate-secret")
def rotate_secret(connection_id: str, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    """A new client secret (shown once); the old one, and tokens issued with it,
    stop working at once. On a connection using public keys, this switches it
    back to a secret."""
    secret = clients.new_secret()
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id)
        _live(client)
        previous = client.auth_method
        client.auth_method, client.secret_hash, client.jwks = IntegrationAuth.SECRET, clients.hash_secret(secret), None
        client.credentials_changed_at = utcnow()
        _record(session, principal, audit.INTEGRATION_SECRET_ROTATED, client, previous_method=previous)
        return {"connection": _payload(session, client), "client_secret": secret}


@router.post("/{connection_id}/ip-restriction")
def ip_restriction(connection_id: str, body: IpRestriction, principal: Principal = Depends(fresh_admin)) \
        -> Dict[str, Any]:
    try:
        cidrs = clients.parse_cidrs(body.allowed_ips)
    except clients.CidrError as exc:
        raise bad(str(exc)) from exc
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id)
        _live(client)
        client.allowed_cidrs = ",".join(cidrs) or None
        _record(session, principal, audit.INTEGRATION_IPS_SET, client, allowed_ips=cidrs)
        return {"connection": _payload(session, client)}


@router.post("/{connection_id}/public-key")
def public_key(connection_id: str, body: PublicKeys, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    """Switch to public-key authentication (private_key_jwt), or replace the
    keys. The client secret stops working, and so do tokens issued before."""
    try:
        keys = jose.parse_jwks(body.jwks)
    except jose.JoseError as exc:
        raise bad(f"The public keys are not usable: {exc}.") from exc
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id)
        _live(client)
        client.auth_method, client.jwks, client.secret_hash = IntegrationAuth.PRIVATE_KEY_JWT, jose.jwks_json(keys), None
        client.credentials_changed_at = utcnow()
        _record(session, principal, audit.INTEGRATION_PUBLIC_KEYS_SET, client,
                keys=[jose.thumbprint(k.jwk) for k in keys])
        return {"connection": _payload(session, client)}


@router.post("/{connection_id}/webhook")
def set_webhook(connection_id: str, body: Webhook, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    """Set (or remove, with null) where events go. A new webhook gets a signing
    secret, shown once."""
    url = _webhook_url(body.url) if body.url else None
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id)
        _live(client)
        granted = S.parse(client.scopes)
        secret = None
        if url:
            if not client.webhook_secret:
                secret = clients.new_webhook_secret()
                client.webhook_secret = clients.seal_webhook_secret(secret)
            granted = S.ordered(granted + [S.WEBHOOKS])
        else:
            client.webhook_secret = None
            granted = [s for s in granted if s != S.WEBHOOKS]
        if not granted:
            raise bad("A connection must be able to do something.")
        client.webhook_url, client.scopes = url, " ".join(granted)
        _record(session, principal, audit.INTEGRATION_WEBHOOK_SET if url else audit.INTEGRATION_WEBHOOK_REMOVED,
                client, url=clients.audit_url(url))
        return {"connection": _payload(session, client), "webhook_secret": secret}


@router.post("/{connection_id}/webhook/rotate-secret")
def rotate_webhook_secret(connection_id: str, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    secret = clients.new_webhook_secret()
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id)
        _live(client)
        if not client.webhook_url:
            raise ApiError(409, "This connection has no address for notifications.", "NO_WEBHOOK")
        client.webhook_secret = clients.seal_webhook_secret(secret)
        _record(session, principal, audit.INTEGRATION_WEBHOOK_SECRET_ROTATED, client)
        return {"connection": _payload(session, client), "webhook_secret": secret}


@router.post("/{connection_id}/webhook/test", status_code=202)
def send_test_event(connection_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id)
        _live(client)
        if not client.webhook_url:
            raise ApiError(409, "This connection has no address for notifications.", "NO_WEBHOOK")
        delivery = webhooks.send_test(session, client)
        session.flush()
        _record(session, principal, audit.INTEGRATION_WEBHOOK_TESTED, client, event_id=delivery.event_id)
        return {"delivery_id": delivery.id, "event_id": delivery.event_id}


@router.get("/{connection_id}/requests")
def recent_requests(connection_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id, lock=False)
        rows = session.scalars(select(IntegrationRequest).where(
            IntegrationRequest.organisation_id == principal.organisation_id, IntegrationRequest.client_pk == client.id)
            .order_by(IntegrationRequest.at.desc()).limit(RECENT))
        return {"items": [{"at": iso(r.at), "method": r.method, "path": r.path, "status": r.status,
                           "duration_ms": r.duration_ms, "ip": r.ip} for r in rows]}


@router.get("/{connection_id}/deliveries")
def recent_deliveries(connection_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id, lock=False)
        rows = session.scalars(select(WebhookDelivery).where(
            WebhookDelivery.organisation_id == principal.organisation_id, WebhookDelivery.client_pk == client.id)
            .order_by(WebhookDelivery.created_at.desc()).limit(RECENT))
        return {"items": [{"id": d.id, "event_id": d.event_id, "event_type": d.event_type, "status": d.status,
                           "attempts": d.attempts, "last_status_code": d.last_status_code,
                           "last_error": d.last_error, "created_at": iso(d.created_at),
                           "last_attempt_at": iso(d.last_attempt_at), "next_attempt_at": iso(d.next_attempt_at),
                           "delivered_at": iso(d.delivered_at)} for d in rows]}


# --- payout changes made by a connected system (app.payout_holds) ----------------------------------

def _change_payload(change: IntegrationPayoutChange, employee: Optional[Employee], now) -> Dict[str, Any]:
    held = change.confirmed_at is None and ensure_aware(change.hold_until) > now
    return {"id": change.id, "employee_id": change.employee_id,
            "employee_name": employee.name if employee else None,
            "employee_number": employee.employee_number if employee else None,
            "before": {"method": change.before_method, "account": change.before_account},
            "after": {"method": change.after_method, "account": change.after_account},
            "created_at": iso(change.created_at), "hold_until": iso(change.hold_until),
            "confirmed_at": iso(change.confirmed_at), "held": held}


@router.get("/{connection_id}/payout-changes")
def payout_changes(connection_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    """Payout accounts this connection changed (masked), newest first; held ones can be confirmed."""
    now = utcnow()
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id, lock=False)
        rows = session.execute(
            select(IntegrationPayoutChange, Employee).outerjoin(
                Employee, (Employee.id == IntegrationPayoutChange.employee_id)
                & (Employee.organisation_id == IntegrationPayoutChange.organisation_id))
            .where(IntegrationPayoutChange.organisation_id == principal.organisation_id,
                   IntegrationPayoutChange.client_pk == client.id)
            .order_by(IntegrationPayoutChange.created_at.desc()).limit(RECENT)).all()
        return {"items": [_change_payload(change, employee, now) for change, employee in rows]}


@router.post("/{connection_id}/payout-changes/{change_id}/confirm")
def confirm_payout_change(connection_id: str, change_id: str, principal: Principal = Depends(fresh_admin)) \
        -> Dict[str, Any]:
    """The admin checked the new payout details: the employee's claims can be batched again now."""
    now = utcnow()
    with tenant_session(principal.organisation_id) as session:
        client = _client(session, principal, connection_id, lock=False)
        change = owned(session, IntegrationPayoutChange, change_id, principal.organisation_id, lock=True)
        if change.client_pk != client.id:
            raise ApiError(404, "Not found.", "NOT_FOUND")
        if change.confirmed_at is None and ensure_aware(change.hold_until) > now:
            change.confirmed_at, change.confirmed_by = now, principal.admin_id
            employee = session.scalar(select(Employee).where(Employee.id == change.employee_id,
                                                             Employee.organisation_id == principal.organisation_id))
            _record(session, principal, audit.INTEGRATION_PAYOUT_CONFIRMED, client, change_id=change.id,
                    employee_id=change.employee_id, employee=employee.name if employee else None,
                    after={"method": change.after_method, "account": change.after_account})
        employee = session.scalar(select(Employee).where(Employee.id == change.employee_id,
                                                         Employee.organisation_id == principal.organisation_id))
        return _change_payload(change, employee, now)

"""The token endpoint (OAuth 2.0 client credentials) and access-token checks.

A client authenticates with its secret (``client_secret_basic`` or
``client_secret_post``) or with a client assertion signed by one of its keys
(``private_key_jwt``: ``iss`` = ``sub`` = client_id, ``aud`` = the token URL,
``exp`` at most 5 minutes ahead, a ``jti`` used once and kept until it
expires).

It gets an access token: a JWT signed ES256 with the service's key (its
``kid`` in the header, the key at ``/.well-known/jwks.json``), valid 5
minutes, naming the organisation, the client and the granted scopes.

Refused: unknown or disconnected clients, wrong credentials, addresses
outside the client's allow-list, organisations not approved by Endod (or
suspended), and scopes not granted. Every API call checks the token AND the
client again in the database, so disconnecting a client, rotating its
credentials or suspending its organisation stops it at once.

Token requests for a known client are audited (issued or refused, with the
reason); API calls refused for the address or the organisation too.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import audit, rls
from app.config import get_settings
from app.db import ensure_aware, session_scope, tenant_session, utcnow
from app.integrations import clients, jose, ratelimit, scopes as scope_names, signing
from app.models import (
    ApplicationStatus, AuditResult, IntegrationAssertion, IntegrationAuth, IntegrationClient, Organisation,
    OrganisationApplication, OrgStatus,
)

TOKEN_LIFETIME = 300
#: The longest a client assertion may live (``exp`` - now).
ASSERTION_MAX_LIFETIME = 300
#: Clock skew allowed between a client and this service.
LEEWAY = 30
ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
TOKEN_TYPE = "at+jwt"
#: last_used_at is written at most this often per client.
TOUCH_EVERY = timedelta(seconds=60)
UNKNOWN_CLIENT = "Unknown client or wrong credentials."


class OAuthError(Exception):
    """An RFC 6749 error from the token endpoint."""

    def __init__(self, error: str, description: str, status_code: int = 400, headers: Optional[Dict[str, str]] = None,
                 reason: Optional[str] = None):
        super().__init__(description)
        self.error, self.description, self.status_code = error, description, status_code
        self.headers = headers or {}
        #: For the audit log (never shown).
        self.reason = reason or error


class TokenRejected(Exception):
    """An API call refused (RFC 6750): 401 invalid_token, 403 insufficient_scope or forbidden, 429."""

    def __init__(self, status_code: int, error: str, description: str, headers: Optional[Dict[str, str]] = None):
        super().__init__(description)
        self.status_code, self.error, self.description = status_code, error, description
        self.headers = headers or {}


def public_url() -> str:
    return get_settings().INTEGRATIONS_PUBLIC_URL.rstrip("/")


def token_url() -> str:
    return f"{public_url()}/oauth/token"


@dataclass
class Caller:
    """Who called (filled in as soon as it is known: the request log uses it)."""

    organisation_id: Optional[str] = None
    client_pk: Optional[str] = None
    client_id: Optional[str] = None
    mode: Optional[str] = None
    name: Optional[str] = None
    ip: Optional[str] = None
    scopes: List[str] = field(default_factory=list)

    @property
    def test(self) -> bool:
        return self.mode == "test"


def organisation_open(session, organisation_id: str) -> bool:
    """Approved by Endod (onboarding passed, or made by Endod) and not suspended."""
    organisation = session.get(Organisation, organisation_id)
    if organisation is None or organisation.status != OrgStatus.ACTIVE:
        return False
    application = session.get(OrganisationApplication, organisation_id)
    return application is None or application.status == ApplicationStatus.APPROVED


def record(session, caller: Caller, action: str, result: str = AuditResult.SUCCESS, **kwargs) -> None:
    """An audit event done by a connected system (no admin): the client is in ``detail``."""
    detail = {"client_id": caller.client_id, "connection": caller.name, "mode": caller.mode,
              **(kwargs.pop("detail", None) or {})}
    audit.record(session, action, result, organisation_id=caller.organisation_id, ip=caller.ip, detail=detail,
                 **kwargs)


# --- the token endpoint ------------------------------------------------------------------------

def _basic(authorization: Optional[str]) -> Optional[Tuple[str, str]]:
    if not authorization:
        return None
    scheme, _, value = authorization.strip().partition(" ")
    if scheme.lower() != "basic":
        raise OAuthError("invalid_client", "Use HTTP Basic authentication with the client_id and secret.", 401,
                         {"WWW-Authenticate": 'Basic realm="endod"'})
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise OAuthError("invalid_client", "The Basic credentials are malformed.", 401) from None
    client_id, sep, secret = decoded.partition(":")
    if not sep:
        raise OAuthError("invalid_client", "The Basic credentials are malformed.", 401)
    # RFC 6749, 2.3.1: both are form-urlencoded before Basic encoding.
    return unquote(client_id), unquote(secret)


def _one(form: Dict[str, List[str]], name: str) -> Optional[str]:
    values = form.get(name) or []
    if len(values) > 1:
        raise OAuthError("invalid_request", f"{name} is given more than once.")
    return values[0] if values else None


def issue(form: Dict[str, List[str]], authorization: Optional[str], address: str, caller: Caller) -> Dict[str, Any]:
    """Handle a token request (the parsed form body). Raises OAuthError."""
    if _one(form, "grant_type") != "client_credentials":
        raise OAuthError("unsupported_grant_type", "grant_type must be client_credentials.")
    basic = _basic(authorization)
    form_id, form_secret = _one(form, "client_id"), _one(form, "client_secret")
    assertion_type, assertion = _one(form, "client_assertion_type"), _one(form, "client_assertion")
    methods = [m for m, present in (("basic", basic), ("post", form_secret is not None),
                                    ("jwt", assertion is not None or assertion_type is not None)) if present]
    if len(methods) != 1:
        raise OAuthError("invalid_request" if methods else "invalid_client",
                         "Authenticate with exactly one method: HTTP Basic, client_secret in the form, or a "
                         "client assertion.", 400 if methods else 401)
    parsed: Optional[jose.Parsed] = None
    if methods[0] == "jwt":
        if assertion_type != ASSERTION_TYPE or not assertion:
            raise OAuthError("invalid_request", f"client_assertion_type must be {ASSERTION_TYPE}, with a "
                                                "client_assertion.")
        try:
            parsed = jose.parse(assertion)
        except jose.JoseError as exc:
            raise OAuthError("invalid_client", f"The client assertion is malformed: {exc}.", 401) from None
        client_id = parsed.claims.get("iss")
        if not isinstance(client_id, str) or (form_id is not None and form_id != client_id):
            raise OAuthError("invalid_client", "The assertion's iss must be the client_id.", 401)
        secret = None
    elif methods[0] == "basic":
        client_id, secret = basic
        if form_id is not None and form_id != client_id:
            raise OAuthError("invalid_request", "client_id differs from the Basic credentials.")
    else:
        client_id, secret = form_id, form_secret
    if not client_id or len(client_id) > 64 or (secret is not None and len(secret) > 200):
        raise OAuthError("invalid_client", UNKNOWN_CLIENT, 401)
    # Per client and address: the client_id is public, so nobody elsewhere can use up a client's quota.
    wait = ratelimit.TOKENS_PER_CLIENT.hit(f"{client_id}|{address}")
    if wait:
        raise OAuthError("slow_down", "Too many token requests for this client; try again shortly.", 429,
                         {"Retry-After": str(wait)})
    requested = scope_names.parse(_one(form, "scope"))
    try:
        key = signing.signing_key()
    except signing.SigningKeyMissing:
        raise OAuthError("temporarily_unavailable", "The integration API is not available.", 503) from None
    return _authenticate_and_issue(client_id, secret, parsed, requested, address, key, caller)


def _authenticate_and_issue(client_id: str, secret: Optional[str], parsed: Optional[jose.Parsed],
                            requested: List[str], address: str, key: signing.SigningKey,
                            caller: Caller) -> Dict[str, Any]:
    with session_scope() as session:
        # One SECURITY DEFINER look-up (app.rls): the organisation; everything else is read as it.
        organisation_id = rls.integration_client_organisation(session, client_id)
    if organisation_id is None:
        if parsed is None:
            clients.verify_secret(secret, None)  # the same work as a wrong secret
        raise OAuthError("invalid_client", UNKNOWN_CLIENT, 401)
    now = utcnow()
    failure: Optional[OAuthError] = None
    with tenant_session(organisation_id) as session:
        client = session.scalar(select(IntegrationClient).where(
            IntegrationClient.client_id == client_id, IntegrationClient.organisation_id == organisation_id))
        if client is None:
            raise OAuthError("invalid_client", UNKNOWN_CLIENT, 401)
        caller.organisation_id, caller.client_pk, caller.client_id = organisation_id, client.id, client.client_id
        caller.mode, caller.name, caller.ip = client.mode, client.name, address
        try:
            answer = _issue_for(session, client, secret, parsed, requested, address, key, caller, now)
            record(session, caller, audit.INTEGRATION_TOKEN_ISSUED, target_type="integration", target_id=client.id,
                   target_name=client.name, detail={"scopes": caller.scopes})
            return answer
        except OAuthError as exc:
            failure = exc
            # Refusals for a known client are kept (committed): guessing shows in the log.
            record(session, caller, audit.INTEGRATION_TOKEN_ISSUED, AuditResult.FAILURE, target_type="integration",
                   target_id=client.id, target_name=client.name, detail={"reason": exc.reason})
    raise failure


def _issue_for(session, client: IntegrationClient, secret: Optional[str], parsed: Optional[jose.Parsed],
               requested: List[str], address: str, key: signing.SigningKey, caller: Caller,
               now: datetime) -> Dict[str, Any]:
    if parsed is None:
        stored = client.secret_hash if client.auth_method == IntegrationAuth.SECRET else None
        if not clients.verify_secret(secret, stored):
            raise OAuthError("invalid_client", UNKNOWN_CLIENT, 401, reason="wrong_secret")
        if client.revoked_at is not None:
            raise OAuthError("invalid_client", UNKNOWN_CLIENT, 401, reason="disconnected")
    else:
        if client.revoked_at is not None:
            raise OAuthError("invalid_client", UNKNOWN_CLIENT, 401, reason="disconnected")
        if client.auth_method != IntegrationAuth.PRIVATE_KEY_JWT:
            raise OAuthError("invalid_client", UNKNOWN_CLIENT, 401, reason="no_public_key")
        _check_assertion(session, client, parsed, now)
    if not clients.address_allowed(address, clients.stored_cidrs(client.allowed_cidrs)):
        raise OAuthError("invalid_client", "This client may not be used from this address.", 401,
                         reason="address_not_allowed")
    if not organisation_open(session, client.organisation_id):
        raise OAuthError("unauthorized_client", "The organisation is not approved by Endod, or is suspended.",
                         reason="organisation_not_open")
    granted = scope_names.parse(client.scopes)
    missing = [s for s in requested if s not in granted]
    if missing:
        raise OAuthError("invalid_scope", f"Not granted to this client: {' '.join(missing)[:300]}.")
    scopes = requested or granted
    caller.scopes = scopes
    _touch(client, now)
    issued = int(now.timestamp())
    claims = {
        "iss": public_url(), "aud": public_url(), "sub": client.client_id, "client_id": client.client_id,
        "organisation_id": client.organisation_id, "mode": client.mode, "scope": " ".join(scopes),
        "iat": issued, "nbf": issued, "exp": issued + TOKEN_LIFETIME, "jti": secrets.token_hex(16),
        "cv": credentials_version(client),
    }
    token = jose.sign_es256(key.private, {"kid": key.kid, "typ": TOKEN_TYPE}, claims)
    return {"access_token": token, "token_type": "Bearer", "expires_in": TOKEN_LIFETIME, "scope": " ".join(scopes)}


def _number(claims: Dict[str, Any], name: str) -> Optional[int]:
    value = claims.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OAuthError("invalid_client", f"The assertion's {name} must be a number.", 401, reason="bad_assertion")
    return int(value)


def _check_assertion(session, client: IntegrationClient, parsed: jose.Parsed, now: datetime) -> None:
    def bad(description: str, reason: str = "bad_assertion") -> OAuthError:
        return OAuthError("invalid_client", description, 401, reason=reason)

    try:
        keys = jose.parse_jwks(client.jwks or "")
        jose.verify_signature(parsed, jose.select_key(parsed, keys))
    except jose.JoseError as exc:
        raise bad(f"The client assertion does not verify: {exc}.") from None
    claims = parsed.claims
    if claims.get("iss") != client.client_id or claims.get("sub") != client.client_id:
        raise bad("The assertion's iss and sub must both be the client_id.")
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if token_url() not in audiences:
        raise bad(f"The assertion's aud must be the token URL, {token_url()}.", "wrong_audience")
    stamp = int(now.timestamp())
    exp = _number(claims, "exp")
    if exp is None:
        raise bad("The assertion has no exp.")
    if exp <= stamp - LEEWAY:
        raise bad("The assertion has expired.", "expired_assertion")
    if exp > stamp + ASSERTION_MAX_LIFETIME + LEEWAY:
        raise bad("The assertion's exp must be at most 5 minutes ahead.")
    for name in ("iat", "nbf"):
        value = _number(claims, name)
        if value is not None and value > stamp + LEEWAY:
            raise bad(f"The assertion's {name} is in the future.")
    jti = claims.get("jti")
    if not isinstance(jti, str) or not 0 < len(jti) <= 255:
        raise bad("The assertion needs a jti (at most 255 characters).")
    if session.scalar(select(IntegrationAssertion.id).where(
            IntegrationAssertion.client_pk == client.id, IntegrationAssertion.jti == jti)) is not None:
        raise bad("This assertion was already used (jti).", "replayed_assertion")
    try:
        with session.begin_nested():
            session.add(IntegrationAssertion(organisation_id=client.organisation_id, client_pk=client.id, jti=jti,
                                             expires_at=datetime.fromtimestamp(exp + LEEWAY, timezone.utc)))
            session.flush()
    except IntegrityError:
        raise bad("This assertion was already used (jti).", "replayed_assertion") from None


def credentials_version(client: IntegrationClient) -> str:
    """Names the client's current credentials: a token issued under older ones is refused."""
    changed = ensure_aware(client.credentials_changed_at)
    return str(int(changed.timestamp() * 1_000_000)) if changed is not None else "0"


def _touch(client: IntegrationClient, now: datetime) -> None:
    if client.last_used_at is None or ensure_aware(client.last_used_at) < now - TOUCH_EVERY:
        client.last_used_at = now


# --- access tokens on API calls ------------------------------------------------------------------

def _invalid(description: str) -> TokenRejected:
    return TokenRejected(401, "invalid_token", description,
                         {"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{description}"'})


def authenticate(authorization: Optional[str], address: str, caller: Caller) -> Caller:
    """The client behind a Bearer access token, checked again in the database. Raises TokenRejected."""
    scheme, _, token = (authorization or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise TokenRejected(401, "invalid_request", "An access token is required.",
                            {"WWW-Authenticate": 'Bearer realm="endod"'})
    try:
        key = signing.signing_key()
    except signing.SigningKeyMissing:
        raise TokenRejected(503, "temporarily_unavailable", "The integration API is not available.") from None
    try:
        parsed = jose.parse(token.strip())
        if parsed.header.get("kid") != key.kid or parsed.header.get("typ") != TOKEN_TYPE:
            raise jose.JoseError("not a token of this service")
        jose.verify_signature(parsed, key.public)
    except jose.JoseError:
        raise _invalid("The access token is not valid.") from None
    claims = parsed.claims
    stamp = int(utcnow().timestamp())
    exp, iat = claims.get("exp"), claims.get("iat")
    if claims.get("iss") != public_url() or claims.get("aud") != public_url():
        raise _invalid("The access token is not for this API.")
    if not isinstance(exp, int) or not isinstance(iat, int) or exp <= stamp:
        raise _invalid("The access token has expired.")
    organisation_id, client_id = claims.get("organisation_id"), claims.get("client_id")
    if not isinstance(organisation_id, str) or not isinstance(client_id, str) or not organisation_id:
        raise _invalid("The access token is not valid.")
    now = utcnow()
    failure: Optional[TokenRejected] = None
    with tenant_session(organisation_id) as session:
        client = session.scalar(select(IntegrationClient).where(
            IntegrationClient.client_id == client_id, IntegrationClient.organisation_id == organisation_id))
        if client is None or client.revoked_at is not None:
            raise _invalid("This client was disconnected.")
        if claims.get("cv") != credentials_version(client):
            raise _invalid("The client's credentials changed; get a new token.")
        caller.organisation_id, caller.client_pk, caller.client_id = organisation_id, client.id, client.client_id
        caller.mode, caller.name, caller.ip = client.mode, client.name, address
        if not clients.address_allowed(address, clients.stored_cidrs(client.allowed_cidrs)):
            failure, reason = TokenRejected(403, "forbidden", "This client may not be used from this address."), \
                "address_not_allowed"
        elif not organisation_open(session, organisation_id):
            failure, reason = TokenRejected(403, "forbidden", "The organisation is not approved by Endod, or is "
                                                              "suspended."), "organisation_not_open"
        if failure is not None:
            record(session, caller, audit.INTEGRATION_CALL_REFUSED, AuditResult.FAILURE, target_type="integration",
                   target_id=client.id, target_name=client.name, detail={"reason": reason})
        else:
            granted = set(scope_names.parse(client.scopes))
            scope_claim = claims.get("scope") if isinstance(claims.get("scope"), str) else ""
            caller.scopes = [s for s in scope_names.parse(scope_claim) if s in granted]
            _touch(client, now)
    if failure is not None:
        raise failure
    wait = ratelimit.REQUESTS_PER_CLIENT.hit(caller.client_pk)
    if wait:
        raise TokenRejected(429, "rate_limited", "Too many requests for this client; try again shortly.",
                            {"Retry-After": str(wait)})
    return caller


def require(caller: Caller, scope: str) -> None:
    if scope not in caller.scopes:
        raise TokenRejected(403, "insufficient_scope", f"This needs the scope {scope}.",
                            {"WWW-Authenticate": f'Bearer error="insufficient_scope", scope="{scope}"'})

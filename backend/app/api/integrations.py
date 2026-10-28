"""The integration API, served under /integrations/v1 (published by nginx at
INTEGRATIONS_PUBLIC_URL, e.g. https://api.endod-health.com/organisation/v1).

A FastAPI application of its own (mounted by app.main), so it has its own
OpenAPI document (``/openapi.json``), its own docs page (``/docs``, with the
guide, docs/integrations.md) and its own errors: OAuth errors from the token
endpoint, ``{"error": ..., "error_code": ...}`` everywhere else. It does not
take the BFF secret: callers are companies' systems, through our nginx, which
proves itself with X-Endod-Edge-Key (EDGE_SHARED_SECRET) and names the
caller's address in X-Endod-Client-IP. Every call is written to the request
log (method, path, status, client, time, duration, address; never a body or
a query string), once the client is known.
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import AwareDatetime
from starlette.exceptions import HTTPException

from app.audit import CLIENT_IP_HEADER
from app.config import get_settings
from app.db import tenant_session
from app.errors import ApiError
from app.integrations import data, ratelimit, scopes as S, signing, tokens
from app.integrations.tokens import Caller
from app.models import IntegrationRequest

logger = logging.getLogger("organisation.integrations")

PREFIX = "/integrations/v1"
MAX_TOKEN_REQUEST = 16 * 1024
EDGE_HEADER = "x-endod-edge-key"
GUIDE = Path(__file__).resolve().parents[1] / "integrations" / "guide.md"
#: Without nginx's key (development and test only): the caller's address as given, or the TCP peer.
TRUSTING_ENVIRONMENTS = ("development", "test")


def _error(status_code: int, message: str, code: str, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content={"error": message, "error_code": code}, headers=headers)
    response.headers["Cache-Control"] = "no-store"
    return response


def _no_store(response: JSONResponse) -> JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _valid_ip(value: Optional[str]) -> Optional[str]:
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def edge_address(request: Request) -> tuple[Optional[str], Optional[JSONResponse]]:
    """(the caller's address, None), or (None, a refusal). With EDGE_SHARED_SECRET
    set, only a request carrying it (our nginx) is served, and its
    X-Endod-Client-IP is the address; anything else on the edge network is
    refused. Without it: refused (503) unless the environment is development or test."""
    settings = get_settings()
    secret = settings.edge_secret()
    if secret:
        given = request.headers.get(EDGE_HEADER, "").encode()
        if not hmac.compare_digest(given, secret.encode()):
            return None, _error(403, "Forbidden.", "EDGE_REQUIRED")
        return _valid_ip(request.headers.get(CLIENT_IP_HEADER)) or "unknown", None
    if settings.ORG_ENVIRONMENT not in TRUSTING_ENVIRONMENTS or settings.is_production:
        return None, _error(503, "The integration API is not configured (EDGE_SHARED_SECRET).", "NOT_CONFIGURED")
    peer = request.client.host if request.client else None
    return _valid_ip(request.headers.get(CLIENT_IP_HEADER)) or _valid_ip(peer) or "unknown", None


def _log_request(caller: Caller, method: str, path: str, status: int, duration_ms: int, ip: Optional[str]) -> None:
    with tenant_session(caller.organisation_id) as session:
        session.add(IntegrationRequest(organisation_id=caller.organisation_id, client_pk=caller.client_pk,
                                       method=method[:8], path=path[:300], status=status, duration_ms=duration_ms,
                                       ip=ip[:64] if ip else None))


def _guide() -> str:
    try:
        return GUIDE.read_text(encoding="utf-8")
    except OSError:
        return "The guide is docs/integrations.md in the endod-organisation repository."


async def _read_body(request: Request, limit: int) -> bytes:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > limit:
        raise ApiError(413, f"A request can be at most {limit // (1024 * 1024)} MB.", "TOO_LARGE")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise ApiError(413, f"A request can be at most {limit // (1024 * 1024)} MB.", "TOO_LARGE")
    return bytes(body)


def create_app() -> FastAPI:
    api = FastAPI(
        title="Endod Organisation Integration API", version="1.0.0", description=_guide(),
        docs_url=None, redoc_url=None, openapi_url="/openapi.json",
        # Its server is the public URL (nginx), never the path it is mounted at here.
        root_path_in_servers=False,
    )

    @api.middleware("http")
    async def edge_and_request_log(request: Request, call_next):
        started = time.perf_counter()
        address, refused = edge_address(request)
        if refused is not None:
            return refused
        caller = Caller(ip=address)
        request.state.caller = caller
        request.state.address = address
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        path = request.url.path
        # Never the body, the query string or a header: method, path, status, client, time, address.
        logger.info("integration_request method=%s path=%s status=%s client=%s ms=%s", request.method, path,
                    response.status_code, caller.client_id or "-", duration_ms)
        if caller.client_pk and caller.organisation_id:
            try:
                await run_in_threadpool(_log_request, caller, request.method, path, response.status_code,
                                        duration_ms, address)
            except Exception:  # noqa: BLE001 -- the answer stands even if the log row cannot be written
                logger.exception("integration_request_log_failed client=%s", caller.client_id)
        return response

    @api.exception_handler(tokens.OAuthError)
    async def oauth_error(_request: Request, exc: tokens.OAuthError):
        return _no_store(JSONResponse(status_code=exc.status_code, headers=exc.headers,
                                      content={"error": exc.error, "error_description": exc.description}))

    @api.exception_handler(tokens.TokenRejected)
    async def token_rejected(_request: Request, exc: tokens.TokenRejected):
        return _error(exc.status_code, exc.description, exc.error, exc.headers)

    @api.exception_handler(ApiError)
    async def api_error(_request: Request, exc: ApiError):
        return _error(exc.status_code, exc.message, exc.code)

    @api.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        message = "Not found." if exc.status_code == 404 else (
            exc.detail if isinstance(exc.detail, str) else "Request failed.")
        return _error(exc.status_code, message, f"HTTP_{exc.status_code}", getattr(exc, "headers", None))

    @api.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(part) for part in first.get("loc", [])[1:]) or "request"
        # Never echo the input back.
        return _error(422, f"{where}: {first.get('msg', 'invalid value')}", "VALIDATION_ERROR")

    @api.exception_handler(Exception)
    async def unexpected(request: Request, _exc: Exception):
        logger.exception("integration_unhandled_error path=%s", request.url.path)
        return _error(500, "Internal server error.", "INTERNAL")

    # --- discovery -----------------------------------------------------------------------------

    @api.get("/.well-known/jwks.json", tags=["auth"], summary="The keys that sign access tokens",
             openapi_extra={"security": []})
    def jwks() -> JSONResponse:
        try:
            keys = signing.jwks()
        except signing.SigningKeyMissing:
            return _error(503, "The integration API is not available.", "UNAVAILABLE")
        return JSONResponse(keys, headers={"Cache-Control": "public, max-age=300"})

    @api.get("/docs", include_in_schema=False)
    def docs() -> HTMLResponse:
        # Relative: right both here and behind nginx at the public URL.
        return get_swagger_ui_html(openapi_url="openapi.json", title="Endod Organisation Integration API")

    # --- the token endpoint ----------------------------------------------------------------------

    @api.post("/oauth/token", tags=["auth"], summary="Get an access token (OAuth 2.0 client credentials)",
              openapi_extra={"security": [], "requestBody": {"required": True, "content": {
                  "application/x-www-form-urlencoded": {"schema": {"type": "object", "properties": {
                      "grant_type": {"type": "string", "enum": ["client_credentials"]},
                      "scope": {"type": "string", "description": "Space-separated; default: every granted scope."},
                      "client_id": {"type": "string"}, "client_secret": {"type": "string"},
                      "client_assertion_type": {"type": "string", "enum": [tokens.ASSERTION_TYPE]},
                      "client_assertion": {"type": "string"}}, "required": ["grant_type"]}}}}})
    async def token(request: Request) -> JSONResponse:
        """Authenticate with the client secret (HTTP Basic, or client_id and
        client_secret in the form) or a client assertion (private_key_jwt).
        Answers an access token valid 5 minutes."""
        address = request.state.address
        wait = ratelimit.TOKENS_PER_ADDRESS.hit(address)
        if wait:
            raise tokens.OAuthError("slow_down", "Too many token requests from this address; try again shortly.",
                                    429, {"Retry-After": str(wait)})
        if not (request.headers.get("content-type") or "").lower().startswith("application/x-www-form-urlencoded"):
            raise tokens.OAuthError("invalid_request", "Send the form as application/x-www-form-urlencoded.")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_TOKEN_REQUEST:
                raise tokens.OAuthError("invalid_request", "The token request is too large.", 413)
        try:
            form = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=20)
        except (UnicodeDecodeError, ValueError):
            raise tokens.OAuthError("invalid_request", "The form could not be read.") from None
        result = await run_in_threadpool(tokens.issue, form, request.headers.get("authorization"), address,
                                         request.state.caller)
        return _no_store(JSONResponse(result))

    # --- calls with an access token --------------------------------------------------------------

    def caller(request: Request, authorization: Optional[str] = Header(default=None, include_in_schema=False)) \
            -> Caller:
        return tokens.authenticate(authorization, request.state.address, request.state.caller)

    def needs(scope: str):
        def check(who: Caller = Depends(caller)) -> Caller:
            tokens.require(who, scope)
            return who
        return check

    page_limit = Query(default=100, ge=1, le=data.MAX_PAGE, description=f"At most {data.MAX_PAGE}.")
    page_offset = Query(default=0, ge=0, le=1_000_000)

    @api.get("/employees", tags=["employees"], summary="The employees (employees.read)")
    def list_employees(status: str = Query(default="all", pattern="^(active|inactive|all)$"),
                       updated_since: Optional[AwareDatetime] = None, limit: int = page_limit,
                       offset: int = page_offset, who: Caller = Depends(needs(S.EMPLOYEES_READ))) -> Dict[str, Any]:
        """By employee number, with their active dependants and payout details."""
        return data.list_employees(who, status, updated_since, limit, offset)

    @api.get("/employees/{employee_number:path}", tags=["employees"], summary="One employee (employees.read)")
    def get_employee(employee_number: str, who: Caller = Depends(needs(S.EMPLOYEES_READ))) -> Dict[str, Any]:
        return data.get_employee(who, employee_number)

    async def _write(request: Request, who: Caller, key: Optional[str], work) -> JSONResponse:
        key = data.check_idempotency_key(key)
        fingerprint = data.request_hash(request.method, request.url.path, request.state.body)
        status, content, headers = await run_in_threadpool(data.run_write, who, key, fingerprint, work)
        return _no_store(JSONResponse(status_code=status, content=content, headers=headers))

    sync_doc = {"requestBody": {"required": True, "content": {"application/json": {"schema": {
        "type": "object", "required": ["employees"], "properties": {"employees": {
            "type": "array", "maxItems": data.MAX_EMPLOYEES, "items": {"type": "object", "required": ["employee_number"],
                                                                     "properties": {
                "employee_number": {"type": "string"}, "name": {"type": "string"}, "phone": {"type": "string"},
                "department": {"type": "string"}, "endod_id": {"type": "string", "nullable": True},
                "active": {"type": "boolean"},
                "payout_method": {"type": "string", "nullable": True, "enum": [*data.PayoutMethod.ALL, None]},
                "payout_account": {"type": "string", "nullable": True},
                "dependants": {"type": "array", "items": {"type": "object", "properties": {
                    "name": {"type": "string"}, "relationship": {"type": "string",
                                                                 "enum": list(data.Relationship.ALL)},
                    "birth_date": {"type": "string", "format": "date", "nullable": True}}}}}}}}}}}}}

    @api.post("/employees", tags=["employees"], summary="Add or update employees by employee number (employees.write)",
              openapi_extra=sync_doc)
    async def sync_employees(request: Request, who: Caller = Depends(needs(S.EMPLOYEES_WRITE)),
                             idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")) \
            -> JSONResponse:
        """At most 500 employees. All or nothing: with any error, nothing
        changes (422 with every row's errors). Sending the same employees
        again changes nothing. A test connection gets the same answer and
        nothing is stored."""
        if not (request.headers.get("content-type") or "").lower().startswith("application/json"):
            raise ApiError(415, "Send application/json.", "UNSUPPORTED_MEDIA_TYPE")
        request.state.body = await _read_body(request, data.MAX_BODY_BYTES)
        rows = data.parse_sync(request.state.body)
        return await _write(request, who, idempotency_key, data.sync_employees(who, rows))

    @api.post("/employees/{employee_number:path}/deactivate", tags=["employees"],
              summary="Deactivate an employee (employees.write)")
    async def deactivate_employee(employee_number: str, request: Request,
                                  who: Caller = Depends(needs(S.EMPLOYEES_WRITE)),
                                  idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")) \
            -> JSONResponse:
        """Their claims stay; they can no longer claim. Deactivating an inactive employee changes nothing."""
        request.state.body = await _read_body(request, 1024)
        return await _write(request, who, idempotency_key, data.deactivate_employee(who, employee_number))

    @api.get("/claims", tags=["claims"], summary="Claims and their status (claims.read)")
    def list_claims(status: Optional[str] = Query(default=None, max_length=16),
                    employee_number: Optional[str] = Query(default=None, max_length=40),
                    receipt_from: Optional[date] = Query(default=None, alias="from"),
                    receipt_to: Optional[date] = Query(default=None, alias="to"),
                    limit: int = page_limit, offset: int = page_offset,
                    who: Caller = Depends(needs(S.CLAIMS_READ))) -> Dict[str, Any]:
        """Newest first. Never the receipt files."""
        return data.list_claims(who, status, employee_number, receipt_from, receipt_to, limit, offset)

    @api.get("/claims/{claim_id}", tags=["claims"], summary="One claim with its medicines (claims.read)")
    def get_claim(claim_id: str, who: Caller = Depends(needs(S.CLAIMS_READ))) -> Dict[str, Any]:
        return data.get_claim(who, claim_id)

    @api.get("/payments/batches", tags=["payments"], summary="Payout batches and their status (payments.read)")
    def list_batches(status: Optional[str] = Query(default=None, max_length=16), limit: int = page_limit,
                     offset: int = page_offset, who: Caller = Depends(needs(S.PAYMENTS_READ))) -> Dict[str, Any]:
        return data.list_batches(who, status, limit, offset)

    @api.get("/payments/batches/{batch_id}", tags=["payments"], summary="One batch and its claims (payments.read)")
    def get_batch(batch_id: str, who: Caller = Depends(needs(S.PAYMENTS_READ))) -> Dict[str, Any]:
        return data.get_batch(who, batch_id)

    def openapi() -> Dict[str, Any]:
        if api.openapi_schema:
            return api.openapi_schema
        schema = get_openapi(title=api.title, version=api.version, description=api.description, routes=api.routes,
                             servers=[{"url": tokens.public_url()}])
        schema.setdefault("components", {})["securitySchemes"] = {"endod": {
            "type": "oauth2", "description": "Client credentials: a client secret or a signed client assertion "
                                             "(private_key_jwt).",
            "flows": {"clientCredentials": {"tokenUrl": tokens.token_url(), "scopes": {
                name: label for name, (label, _d) in S.SCOPES.items()}}}}}
        schema["security"] = [{"endod": []}]
        api.openapi_schema = schema
        return schema

    api.openapi = openapi
    return api

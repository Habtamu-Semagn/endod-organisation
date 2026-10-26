"""The TenaCare organisation portal API (run with ``uvicorn app.main:app``).

Only the portal web app calls it (its server side, on the compose network,
with X-BFF-Secret); browsers never do, so there is no CORS. Sessions travel in
the Authorization header from the web app, which keeps them in an httpOnly
cookie. Every route but sign-in works only within the signed-in admin's
organisation (app.tenancy).

The one exception is ``/platform/*`` (app.api.platform): Endod's super admin
calls it over the endod-bus network with X-Platform-Key instead of the BFF's
secret; the BFF never passes those paths on.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api import (
    application, auth, batches, claims, employees, overview, platform, receipts, reports, settings as settings_api,
)
from app.config import Settings, get_settings
from app.errors import ApiError

logger = logging.getLogger("organisation")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Fail at start, not at the first sign-in, when the secret is missing in production.
    settings.session_secret()
    bff_secret = settings.bff_secret().encode()
    app = FastAPI(
        title="TenaCare Organisation Portal",
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    @app.middleware("http")
    async def only_the_bff(request: Request, call_next):
        """Everything but /health needs the BFF's shared secret: other peers on
        the networks are refused, and only the BFF names the client. The
        platform API needs the platform key instead (and its router checks it
        again)."""
        if _is_platform(request):
            refused = platform.check_platform_key(request.headers.get("x-platform-key"))
            if refused is not None:
                return JSONResponse(status_code=refused.status_code, headers={"Cache-Control": "no-store"},
                                    content=_body(request, refused.message, refused.code))
        elif request.url.path != "/health":
            given = request.headers.get("x-bff-secret", "").encode()
            if not hmac.compare_digest(given, bff_secret):
                return JSONResponse(status_code=403, content={"error": "Forbidden.", "error_code": "BFF_REQUIRED"},
                                    headers={"Cache-Control": "no-store"})
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content=_body(request, exc.message, exc.code),
                            headers={"Cache-Control": "no-store"})

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        if exc.status_code == 404:
            message = "Not found."
        return JSONResponse(status_code=exc.status_code, headers=getattr(exc, "headers", None),
                            content=_body(request, message, f"HTTP_{exc.status_code}"))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", [])[1:]) or "request"
        # Never echo the input back (it may be a password).
        return JSONResponse(status_code=422, content=_body(
            request, f"{field}: {first.get('msg', 'invalid value')}", "VALIDATION_ERROR"))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        logger.exception("unhandled_error path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"error": "Internal server error.", "error_code": "INTERNAL"})

    @app.get("/health", tags=["service"])
    def health():
        return {"status": "ok", "service": "organisation"}

    app.include_router(auth.router)
    app.include_router(overview.router)
    app.include_router(employees.router)
    app.include_router(settings_api.router)
    app.include_router(receipts.router)
    app.include_router(claims.router)
    app.include_router(batches.router)
    app.include_router(reports.router)
    app.include_router(application.router)
    app.include_router(platform.router)
    return app


def _is_platform(request: Request) -> bool:
    path = request.url.path
    return path == "/platform" or path.startswith("/platform/")


def _body(request: Request, message: str, code: str) -> dict:
    """The error shape; the platform API's also carries ``detail`` (its contract)."""
    body = {"error": message, "error_code": code}
    if _is_platform(request):
        body["detail"] = message
    return body


app = create_app()

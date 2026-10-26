"""`/auth`: sign-in (password, then TOTP or enrolment), setup links,
re-authentication, sign-out, and the current admin and their organisation.

Answers that open a session carry ``session_token``: the web app moves it
into its httpOnly cookie and strips it before anything reaches the page.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator

from app import auth
from app.auth import Principal
from app.db import iso

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class CodeRequest(BaseModel):
    code: Optional[str] = Field(default=None, max_length=20)
    recovery_code: Optional[str] = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _one(self):
        if not (self.code or self.recovery_code):
            raise ValueError("enter a code")
        return self


class TotpRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)


class SetupCheck(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class SetupRequest(SetupCheck):
    password: str = Field(min_length=1, max_length=256)


def _ua(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


@router.post("/login")
def login(body: LoginRequest, request: Request, ip: str = Depends(auth.client_ip)) -> Dict[str, Any]:
    return auth.opened_payload(auth.login(body.email, body.password, ip, _ua(request)))


@router.post("/totp")
def totp(body: CodeRequest, request: Request,
         principal: Principal = Depends(auth.signed_in_any_stage)) -> Dict[str, Any]:
    opened, extra = auth.complete_sign_in(principal, body.code, body.recovery_code, _ua(request))
    return auth.opened_payload(opened, **extra)


@router.post("/enroll/start")
def enroll_start(principal: Principal = Depends(auth.signed_in_any_stage)) -> Dict[str, Any]:
    return auth.enrolment_start(principal)


@router.post("/enroll/confirm")
def enroll_confirm(body: TotpRequest, request: Request,
                   principal: Principal = Depends(auth.signed_in_any_stage)) -> Dict[str, Any]:
    opened, codes = auth.enrolment_confirm(principal, body.code, _ua(request))
    return auth.opened_payload(opened, recovery_codes=codes)


@router.post("/reauth")
def reauth(body: TotpRequest, principal: Principal = Depends(auth.current_admin)) -> Dict[str, Any]:
    return {"reauth_valid_until": iso(auth.reauthenticate(principal, body.code))}


@router.post("/logout")
def logout(principal: Principal = Depends(auth.signed_in_any_stage)) -> Dict[str, bool]:
    auth.logout(principal)
    return {"ok": True}


@router.get("/me")
def me(principal: Principal = Depends(auth.signed_in_any_stage)) -> Dict[str, Any]:
    until = auth.reauth_valid_until(principal)
    return {
        "stage": principal.stage,
        "admin": {"id": principal.admin_id, "email": principal.email, "name": principal.name},
        "organisation": {"id": principal.organisation_id, "name": principal.organisation_name,
                         "application_status": principal.application_status},
        "reauth_valid_until": iso(until),
    }


@router.post("/setup/check")
def setup_check(body: SetupCheck, ip: str = Depends(auth.client_ip)) -> Dict[str, Any]:
    return auth.setup_check(body.token, ip)


@router.post("/setup")
def setup(body: SetupRequest, request: Request, ip: str = Depends(auth.client_ip)) -> Dict[str, Any]:
    return auth.opened_payload(auth.setup_complete(body.token, body.password, ip, _ua(request)))

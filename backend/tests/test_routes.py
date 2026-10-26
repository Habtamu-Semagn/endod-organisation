"""Every route but the sign-in steps needs a session; every portal route needs
a full one; every route but /health and the platform API needs the BFF's
secret (the platform API needs its own key: tests/test_platform.py)."""

import re

import pytest
from conftest import BFF_SECRET, bearer, make_admin, password_step

#: Reachable without a session (they check a password or a setup link themselves).
PUBLIC = {("POST", "/auth/login"), ("POST", "/auth/setup/check"), ("POST", "/auth/setup"), ("GET", "/health"),
          ("POST", "/application/start")}
#: Reachable with a half-finished sign-in.
SIGN_IN_STEPS = {("POST", "/auth/totp"), ("POST", "/auth/enroll/start"), ("POST", "/auth/enroll/confirm"),
                 ("POST", "/auth/logout"), ("GET", "/auth/me")}

SAMPLE_ID = "a1" * 16


def _routes():
    from app.main import create_app

    found = []
    for template, operations in create_app().openapi()["paths"].items():
        for method in operations:
            found.append((method.upper(), template, re.sub(r"\{[a-z_]+\}", SAMPLE_ID, template)))
    return found


ROUTES = _routes()
#: Endod's super admin only, with X-Platform-Key instead of a session (tests/test_platform.py).
PLATFORM = {(m, t) for m, t, _ in ROUTES if t.startswith("/platform/")}


def test_the_route_list_is_complete():
    assert len(ROUTES) >= 40


@pytest.mark.parametrize("method, template, path", [r for r in ROUTES if (r[0], r[1]) not in PUBLIC | PLATFORM])
def test_needs_a_session(client, method, template, path):
    resp = client.request(method, path, json={})
    assert resp.status_code == 401, (method, path, resp.text)
    resp = client.request(method, path, json={}, headers={"Authorization": "Bearer not-a-session"})
    assert resp.status_code == 401


@pytest.mark.parametrize("method, template, path",
                         [r for r in ROUTES if (r[0], r[1]) not in PUBLIC | SIGN_IN_STEPS | PLATFORM])
def test_needs_a_full_session(client, method, template, path):
    make_admin()
    pending = password_step(client)
    resp = client.request(method, path, json={}, headers=bearer(pending["session_token"]))
    assert resp.status_code == 403 and resp.json()["error_code"] == "SESSION_INCOMPLETE", (method, path)


@pytest.mark.parametrize("method, template, path", ROUTES)
def test_every_route_but_health_needs_the_bff_secret(db, method, template, path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    bare = TestClient(create_app())
    for headers in ({}, {"X-BFF-Secret": "wrong"}, {"X-BFF-Secret": BFF_SECRET[:-1]}):
        resp = bare.request(method, path, json={}, headers=headers)
        if template == "/health":
            assert resp.status_code == 200
        elif template.startswith("/platform/"):
            # Its own key instead (unset here: switched off).
            assert resp.status_code == 503 and resp.json()["detail"], (method, path)
        else:
            assert resp.status_code == 403 and resp.json()["error_code"] == "BFF_REQUIRED", (method, path)


def test_production_needs_a_bff_secret(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ORG_ENVIRONMENT", "production")
    monkeypatch.setenv("SESSION_SECRET", "s" * 40)
    monkeypatch.delenv("BFF_SHARED_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="BFF_SHARED_SECRET"):
        get_settings().bff_secret()


def test_unknown_routes_answer_the_generic_not_found(client):
    resp = client.get("/nothing-here")
    assert resp.status_code == 404 and resp.json()["error"] == "Not found."

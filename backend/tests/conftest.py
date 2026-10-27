import os
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PASSWORD = "Correct-Horse-42"
BFF_SECRET = "test-bff-secret-0123456789abcdefghijklmnopqrst"
CLIENT_IP = "198.51.100.10"
#: "Today" in every test (Addis Ababa): the policy year is the calendar year 2026 by default.
TODAY = date(2026, 10, 20)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def from_ip(ip):
    """Headers of a request the BFF passes on for a visitor at ``ip``."""
    return {"X-Endod-Client-IP": ip}


class Clock:
    """The TOTP clock, moved by hand (a code is good for one 30-second step)."""

    def __init__(self, start: float):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float = 30) -> None:
        self.now += seconds


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh database per test: SQLite by default, or the PostgreSQL
    database in ORG_TEST_DATABASE_URL (emptied before every test)."""
    from app import db as dbmod
    from app import models  # noqa: F401  (registers the tables)

    url = os.environ.get("ORG_TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'organisation.db'}"
    monkeypatch.setenv("ORG_DATABASE_URL", url)
    monkeypatch.setenv("ORG_ENVIRONMENT", "development")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdefghijklmnop")
    monkeypatch.setenv("SITE_ORIGIN", "https://organisation.example")
    monkeypatch.setenv("BFF_SHARED_SECRET", BFF_SECRET)
    monkeypatch.setenv("ORG_RECEIPTS_DIR", str(tmp_path / "receipts"))
    dbmod.reset_engine()
    dbmod.Base.metadata.drop_all(dbmod.get_engine())
    dbmod.create_all()
    yield
    dbmod.reset_engine()


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    import time

    from app import totp

    fake = Clock(float(int(time.time()) // 30 * 30 + 5))
    monkeypatch.setattr(totp, "_clock", fake)
    return fake


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    from app.api import common

    monkeypatch.setattr(common, "_today", lambda: TODAY)
    return TODAY


@pytest.fixture
def client(db):
    """The API as the BFF calls it: with the shared secret and the visitor's address."""
    from app.main import create_app

    return TestClient(create_app(), headers={"X-BFF-Secret": BFF_SECRET, "X-Endod-Client-IP": CLIENT_IP})


# --- helpers -----------------------------------------------------------------------------

_tins = iter(range(1000000001, 1999999999))


def make_org(name="Tena Logistics PLC", tin=None):
    from app import cli

    return cli.create_org(name, tin or str(next(_tins)))


def make_admin(email="hr@tena.example", name="Selam Tesfaye", password=PASSWORD, enrolled=True, active=True,
               organisation_id=None):
    """An admin (of a new organisation unless one is given); returns (id, TOTP secret or None)."""
    from app import security, totp
    from app.db import session_scope
    from app.models import OrgAdmin

    organisation_id = organisation_id or make_org()
    secret = totp.new_secret() if enrolled else None
    with session_scope() as session:
        admin = OrgAdmin(organisation_id=organisation_id, email=email, name=name, active=active,
                         password_hash=security.hash_password(password) if password else None,
                         totp_secret=security.seal(secret) if secret else None)
        session.add(admin)
        session.flush()
        return admin.id, secret


def admin_org(admin_id):
    from app.db import session_scope
    from app.models import OrgAdmin

    with session_scope() as session:
        return session.get(OrgAdmin, admin_id).organisation_id


def code(secret, clock, offset=0):
    from app import totp

    return totp.code_at(secret, totp.current_step(clock.now) + offset)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def password_step(client, email="hr@tena.example", password=PASSWORD, headers=None):
    resp = client.post("/auth/login", json={"email": email, "password": password}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def sign_in(client, clock, secret, email="hr@tena.example", password=PASSWORD, ip=CLIENT_IP):
    """Password and TOTP; returns the full session's headers. Moves the clock
    on a step so the next code is a new one."""
    pending = password_step(client, email, password, headers=from_ip(ip))
    assert pending["stage"] == "totp"
    resp = client.post("/auth/totp", json={"code": code(secret, clock)},
                       headers={**bearer(pending["session_token"]), **from_ip(ip)})
    assert resp.status_code == 200, resp.text
    clock.advance()
    return bearer(resp.json()["session_token"])


def reauth(client, clock, secret, headers):
    resp = client.post("/auth/reauth", json={"code": code(secret, clock)}, headers=headers)
    assert resp.status_code == 200, resp.text
    clock.advance()


def setup_token(link):
    return link.split("#", 1)[1]


def enrol_via_link(client, clock, link, password=PASSWORD):
    """Open the setup link with ``password`` (sets or confirms it), enrol;
    returns (full session headers, TOTP secret, recovery codes)."""
    resp = client.post("/auth/setup", json={"token": setup_token(link), "password": password})
    assert resp.status_code == 200, resp.text
    headers = bearer(resp.json()["session_token"])
    secret = client.post("/auth/enroll/start", headers=headers).json()["secret"]
    done = client.post("/auth/enroll/confirm", json={"code": code(secret, clock)}, headers=headers)
    assert done.status_code == 200, done.text
    clock.advance()
    return bearer(done.json()["session_token"]), secret, done.json()["recovery_codes"]


def events(action=None):
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import AuditEvent

    with session_scope() as session:
        query = select(AuditEvent).order_by(AuditEvent.at)
        if action:
            query = query.where(AuditEvent.action == action)
        return [(e.action, e.result, e.admin_email, e.target_id, e.detail) for e in session.scalars(query)]


class Portal:
    """A signed-in admin of one organisation, with helpers for the portal API."""

    def __init__(self, client, clock, email="hr@tena.example", org_name="Tena Logistics PLC"):
        self.client = client
        self.clock = clock
        self.org_id = make_org(org_name)
        self.admin_id, self.secret = make_admin(email=email, organisation_id=self.org_id)
        self.email = email
        self.headers = sign_in(client, clock, self.secret, email=email)
        self._numbers = iter(range(1, 100000))

    # Plain calls with this admin's session.
    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path, **kw):
        return self.client.post(path, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def put(self, path, **kw):
        return self.client.put(path, headers=self.headers, **kw)

    def patch(self, path, **kw):
        return self.client.patch(path, headers=self.headers, **kw)

    def delete(self, path, **kw):
        return self.client.delete(path, headers=self.headers, **kw)

    def reauth(self):
        reauth(self.client, self.clock, self.secret, self.headers)

    def forget_reauth(self):
        """As if the last fresh code were older than 10 minutes."""
        from sqlalchemy import update

        from app.db import session_scope
        from app.models import AdminSession

        with session_scope() as session:
            session.execute(update(AdminSession).values(reauth_at=None))

    def employee(self, **fields):
        n = next(self._numbers)
        body = {"employee_number": f"ET-{n:04d}", "name": f"Employee {n}", "phone": f"+25191100{n:04d}",
                "department": "Engineering", "payout_method": "cbe", "payout_account": f"10000{n:08d}", **fields}
        resp = self.post("/employees", json=body)
        if resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED":  # payout details
            self.reauth()
            resp = self.post("/employees", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()

    def receipt(self, data=PNG, filename="receipt.png"):
        resp = self.post("/receipts", content=data, headers={"X-Filename": filename,
                                                              "Content-Type": "application/octet-stream"})
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    def claim_body(self, employee_id, items=None, receipt_number=None, receipt_date=None, tin="0012345678",
                   dependant_id=None, pharmacy="Kenema Pharmacy Bole"):
        return {
            "employee_id": employee_id, "dependant_id": dependant_id, "pharmacy_name": pharmacy, "pharmacy_tin": tin,
            "receipt_number": receipt_number or f"FS-{next(self._numbers):05d}",
            "receipt_date": (receipt_date or date(2026, 10, 15)).isoformat(),
            "items": items or [{"medicine": "Metformin 500mg", "quantity": 2, "unit_price_santim": 50_000}],
            "receipt_file_id": self.receipt(),
        }

    def claim(self, employee_id, **kw):
        resp = self.post("/claims", json=self.claim_body(employee_id, **kw))
        assert resp.status_code == 201, resp.text
        return resp.json()

    def approve(self, claim_id):
        return self.post(f"/claims/{claim_id}/approve")

    def set_policy(self, **changes):
        body = {"annual_limit_santim": 1_000_000, "copay_percent": 0, "dependants_covered": True,
                "excluded_medicines": [], "year_start_month": 1, "year_start_day": 1, **changes}
        resp = self.put("/policy", json=body)
        if resp.status_code == 403:
            self.reauth()
            resp = self.put("/policy", json=body)
        assert resp.status_code == 200, resp.text
        return resp.json()


@pytest.fixture
def portal(client, clock):
    return Portal(client, clock)


@pytest.fixture
def other_portal(client, clock):
    return Portal(client, clock, email="hr@other.example", org_name="Other Org PLC")


# --- company applications (app.api.application, app.api.platform) -------------------------

PLATFORM_KEY = "test-platform-key-0123456789abcdefghijklmnop"
COMPANY = {
    "legal_name": "Abyssinia Textiles PLC", "trade_name": "Abyssinia Tex", "tin": "0045671234",
    "business_license_number": "AA/14/123456", "sector": "manufacturing", "employee_count": 240,
    "city": "Addis Ababa", "address": "Bole Sub-city, Woreda 3, House 512", "phone": "011 551 2345",
    "email": "info@abyssinia-tex.example",
}
_applicant_numbers = iter(range(1, 100000))


@pytest.fixture
def platform_key(monkeypatch):
    monkeypatch.setenv("ORG_PLATFORM_KEY", PLATFORM_KEY)
    return {"X-Platform-Key": PLATFORM_KEY}


def start_application(client, email=None, ip=CLIENT_IP, **fields):
    """POST /application/start; returns the response."""
    n = next(_applicant_numbers)
    body = {"legal_name": f"Applicant {n} PLC", "full_name": "Meron Alemu", "title": "HR Manager",
            "phone": "0911223344", "email": email or f"applicant{n}@company.example", "password": PASSWORD, **fields}
    return client.post("/application/start", json=body, headers=from_ip(ip))


class Applicant:
    """A company applying: its account made, signed in with the password only
    (an ``applicant`` session). ``enrolled``: an applicant who enrolled an
    authenticator anyway (as every applicant had to before), signed in with a code."""

    def __init__(self, client, clock, email=None, enrolled=False, **fields):
        self.client = client
        self.clock = clock
        resp = start_application(client, email=email, **fields)
        assert resp.status_code == 200, resp.text
        assert resp.json()["stage"] == "applicant"
        self.headers = bearer(resp.json()["session_token"])
        me = client.get("/auth/me", headers=self.headers).json()
        assert me["stage"] == "applicant"
        self.email = me["admin"]["email"]
        self.org_id = me["organisation"]["id"]
        self.secret = None
        if enrolled:
            self.secret = enrol_directly(self.email)
            self.headers = sign_in(client, clock, self.secret, email=self.email)

    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def put(self, path, **kw):
        return self.client.put(path, headers=self.headers, **kw)

    def post(self, path, **kw):
        return self.client.post(path, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def company(self, **changes):
        resp = self.put("/application/company", json={**COMPANY, **changes})
        assert resp.status_code == 200, resp.text
        return resp.json()

    def upload(self, kind, data=PDF, filename=None):
        return self.post(f"/application/documents/{kind}", content=data,
                         headers={"X-Filename": filename or f"{kind}.pdf", "Content-Type": "application/octet-stream"})

    def upload_all(self):
        for kind in ("trade_license", "tin_certificate", "authorization_letter"):
            resp = self.upload(kind)
            assert resp.status_code == 201, resp.text

    def submit(self):
        return self.post("/application/submit")

    def complete(self, **company):
        """Every step filled in and submitted."""
        self.company(**company)
        self.upload_all()
        resp = self.submit()
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "submitted"
        return resp.json()

    def sign_in_again(self):
        """Password only (or password and code, once enrolled)."""
        if self.secret:
            self.headers = sign_in(self.client, self.clock, self.secret, email=self.email)
        else:
            self.headers = applicant_sign_in(self.client, self.email)
        return self.headers

    def enrol_after_approval(self):
        """The first sign-in after approval: password, then the forced enrolment.
        Returns the recovery codes; ``headers`` is the full session."""
        opened = password_step(self.client, email=self.email)
        assert opened["stage"] == "enroll", opened
        headers = bearer(opened["session_token"])
        self.secret = self.client.post("/auth/enroll/start", headers=headers).json()["secret"]
        done = self.client.post("/auth/enroll/confirm", json={"code": code(self.secret, self.clock)}, headers=headers)
        assert done.status_code == 200, done.text
        self.clock.advance()
        self.headers = bearer(done.json()["session_token"])
        return done.json()["recovery_codes"]


def applicant_sign_in(client, email, ip=CLIENT_IP):
    """An applicant's password-only sign-in; returns the session's headers."""
    opened = password_step(client, email=email, headers=from_ip(ip))
    assert opened["stage"] == "applicant", opened
    return bearer(opened["session_token"])


def enrol_directly(email):
    """Give an admin a confirmed authenticator (as the enrolment does); returns its secret."""
    from app import security, totp
    from app.db import session_scope, utcnow
    from app.models import OrgAdmin
    from sqlalchemy import select

    secret = totp.new_secret()
    with session_scope() as session:
        admin = session.scalar(select(OrgAdmin).where(OrgAdmin.email == email))
        admin.totp_secret = security.seal(secret)
        admin.totp_enrolled_at = utcnow()
    return secret


def approve_application(client, headers, org_id, reviewer="reviewer@endod.example"):
    """Approve as the super admin does: the version from the detail it just read."""
    seen = client.get(f"/platform/applications/{org_id}", headers=headers).json()["updated_at"]
    return client.post(f"/platform/applications/{org_id}/approve", headers=headers,
                       json={"reviewer": reviewer, "expected_updated_at": seen})


@pytest.fixture
def applicant(client, clock):
    return Applicant(client, clock)

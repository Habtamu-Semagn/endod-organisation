import json
import threading
from datetime import timedelta

from conftest import (
    make_org, CLIENT_IP, PASSWORD, bearer, code, enrol_via_link, events, from_ip, make_admin, password_step, reauth, sign_in,
    setup_token,
)
from sqlalchemy import select, update

from app.auth import INVALID_LOGIN
from app.db import session_scope, utcnow
from app.models import OrgAdmin, AdminSession, AuditEvent, LoginThrottle, RecoveryCode

OTHER_IP = "203.0.113.50"


def _login(client, password=PASSWORD, email="hr@tena.example", ip=CLIENT_IP):
    return client.post("/auth/login", json={"email": email, "password": password}, headers=from_ip(ip))


# --- password step ------------------------------------------------------------------------

def test_sign_in_with_password_and_totp(client, clock):
    _, secret = make_admin()
    pending = password_step(client)
    assert pending["stage"] == "totp" and pending["session_max_age"] == 15 * 60
    # The pending session reaches nothing but the sign-in steps.
    assert client.get("/claims", headers=bearer(pending["session_token"])).status_code == 403
    assert client.get("/auth/me", headers=bearer(pending["session_token"])).json()["stage"] == "totp"

    resp = client.post("/auth/totp", json={"code": code(secret, clock)}, headers=bearer(pending["session_token"]))
    assert resp.status_code == 200, resp.text
    full = resp.json()
    assert full["stage"] == "full" and full["session_max_age"] == 12 * 3600
    # Rotated: a new token, and the pending one is dead.
    assert full["session_token"] != pending["session_token"]
    assert client.get("/auth/me", headers=bearer(pending["session_token"])).status_code == 401
    me = client.get("/auth/me", headers=bearer(full["session_token"])).json()
    assert me["stage"] == "full" and me["admin"]["email"] == "hr@tena.example"
    assert me["reauth_valid_until"] is None
    assert [e[:2] for e in events("sign_in")] == [("sign_in", "success")]


def test_wrong_email_and_wrong_password_answer_the_same(client):
    make_admin()
    make_admin(email="off@endod.example", active=False)
    make_admin(email="nopass@endod.example", password=None, enrolled=False)
    make_admin(email="notyet@endod.example", enrolled=False)
    answers = [
        _login(client, email="Nobody@Endod.example"),
        _login(client, password="Wrong-password-1"),
        _login(client, email="off@endod.example"),
        _login(client, email="nopass@endod.example"),
        # Right password, but no authenticator yet: only the setup link enrols.
        _login(client, email="notyet@endod.example"),
    ]
    assert {(a.status_code, a.json()["error"], a.json()["error_code"]) for a in answers} == {
        (401, INVALID_LOGIN, "INVALID_LOGIN")}
    failures = events("sign_in")
    assert len(failures) == 5 and all(result == "failure" for _, result, *_ in failures)
    reasons = [json.loads(f[4])["reason"] for f in failures]
    assert reasons == ["unknown_email", "wrong_password", "account_disabled", "not_enrolled", "not_enrolled"]


def test_unknown_emails_are_logged_only_as_a_keyed_hash(client):
    _login(client, email="  Someone.Typed@This.example ")
    _login(client, email="someone.typed@this.example")
    logged = events("sign_in")
    assert logged[0][2] == logged[1][2]  # the same name, recognisable
    assert logged[0][2].startswith("unknown:") and len(logged[0][2]) == len("unknown:") + 8
    with session_scope() as session:
        dump = repr([(e.admin_email, e.detail, e.target_name) for e in session.scalars(select(AuditEvent))])
    assert "someone" not in dump.lower() and "this.example" not in dump.lower()


def test_email_is_case_insensitive(client):
    make_admin()
    assert password_step(client, email="  HR@Tena.Example ")["stage"] == "totp"


# --- throttling -------------------------------------------------------------------------------

def test_password_failures_never_sign_anyone_out(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    for n in range(8):
        assert _login(client, password=f"wrong-{n}", ip=OTHER_IP).status_code in (200, 401)
    assert client.get("/auth/me", headers=headers).status_code == 200


def test_five_failures_lock_that_address_for_that_account_only(client, clock):
    _, secret = make_admin()
    make_admin(email="two@endod.example")
    for n in range(3):
        assert _login(client, password=f"wrong-{n}").status_code == 401
    # Now in backoff: wrong passwords go on to the code step, where failures count.
    for n in range(2):
        decoy = _login(client, password=f"wrong-again-{n}")
        assert decoy.status_code == 200
        resp = client.post("/auth/totp", json={"code": "000000"}, headers=bearer(decoy.json()["session_token"]))
    assert resp.status_code == 401 and resp.json()["error_code"] == "LOCKED"
    # The pair is locked: even the right password is refused, with the same answer.
    resp = _login(client)
    assert resp.status_code == 401 and resp.json()["error"] == INVALID_LOGIN
    assert "address_locked_for_account" in events("sign_in")[-1][4]
    locks = events("account_locked")
    assert len(locks) == 1 and json.loads(locks[0][4])["scope"] == "account_and_address"
    # Another account from the same address is not affected.
    assert password_step(client, email="two@endod.example")["stage"] == "totp"
    # The admin, from another address, still signs in with password and code.
    sign_in(client, clock, secret, ip=OTHER_IP)
    # And the lock ends after 15 minutes.
    with session_scope() as session:
        session.execute(update(LoginThrottle).values(locked_until=utcnow() - timedelta(seconds=1)))
    assert password_step(client)["stage"] == "totp"


def test_backoff_hides_whether_a_password_is_right(client, clock):
    _, secret = make_admin()
    for n in range(3):
        assert _login(client, password=f"wrong-{n}").status_code == 401
    backoffs = events("account_backoff")
    assert [json.loads(b[4])["seconds"] for b in backoffs] == [30]
    # In backoff, a wrong password from anywhere goes on to the code step too...
    decoy = _login(client, password="still-wrong", ip=OTHER_IP)
    assert decoy.status_code == 200 and decoy.json()["stage"] == "totp"
    # ...where no code completes it, not even the right one.
    resp = client.post("/auth/totp", json={"code": code(secret, clock)},
                       headers={**bearer(decoy.json()["session_token"]), **from_ip(OTHER_IP)})
    assert resp.status_code == 400 and resp.json()["error_code"] == "INVALID_CODE"
    assert "wrong_password_during_backoff" in events("sign_in")[-1][4]
    # The right password and a code still work, from a new address.
    headers = sign_in(client, clock, secret, ip="192.0.2.77")
    assert client.get("/auth/me", headers=headers).status_code == 200
    with session_scope() as session:
        admin = session.scalar(select(OrgAdmin))
        assert admin.backoff_until is None and admin.failed_attempts == 0


def test_backoff_grows_and_is_capped():
    from app.auth import backoff_seconds
    from app.config import Settings

    settings = Settings()
    assert [backoff_seconds(n, settings) for n in range(1, 10)] == [0, 0, 30, 60, 120, 240, 480, 900, 900]
    assert backoff_seconds(1000, settings) == 900


def test_wrong_totp_codes_lock_only_that_sign_in(client, clock):
    _, secret = make_admin()
    other = sign_in(client, clock, secret, ip=OTHER_IP)
    pending = password_step(client)
    headers = bearer(pending["session_token"])
    for _ in range(4):
        resp = client.post("/auth/totp", json={"code": "000000"}, headers=headers)
        assert resp.status_code == 400 and resp.json()["error_code"] == "INVALID_CODE"
    resp = client.post("/auth/totp", json={"code": "000000"}, headers=headers)
    assert resp.status_code == 401 and resp.json()["error_code"] == "LOCKED"
    # That half-finished sign-in is gone; the admin's other session is not.
    assert client.post("/auth/totp", json={"code": code(secret, clock)}, headers=headers).status_code == 401
    assert client.get("/auth/me", headers=other).status_code == 200


def test_address_rate_limit(client, monkeypatch):
    monkeypatch.setenv("ORG_IP_FAILURE_LIMIT", "3")
    make_admin()
    for n in range(3):
        assert _login(client, email=f"x{n}@endod.example", password="whatever-1").status_code == 401
    resp = _login(client)
    assert resp.status_code == 429 and resp.json()["error_code"] == "RATE_LIMITED"
    assert "address_rate_limited" in events("sign_in")[-1][4]
    # Another address is fine.
    assert _login(client, ip=OTHER_IP).status_code == 200


def test_the_client_address_comes_only_from_the_bff_header(client, monkeypatch):
    monkeypatch.setenv("ORG_IP_FAILURE_LIMIT", "2")
    for n in range(2):
        client.post("/auth/login", json={"email": f"x{n}@endod.example", "password": "whatever-1"},
                    headers={"X-Forwarded-For": f"203.0.113.{n}"})
    # X-Forwarded-For is ignored: both failures came from the BFF's client address.
    assert client.post("/auth/login", json={"email": "x@endod.example", "password": "whatever-1"},
                       headers={"X-Forwarded-For": "198.51.100.7"}).status_code == 429
    with session_scope() as session:
        assert {e.ip for e in session.scalars(select(AuditEvent))} == {CLIENT_IP}
    # Not an address: recorded as unknown, never as the text sent.
    client.post("/auth/login", json={"email": "y@endod.example", "password": "whatever-1"},
                headers={"X-Endod-Client-IP": "<script>"})
    assert events("sign_in")[-1][2].startswith("unknown:")
    with session_scope() as session:
        assert "unknown" in {e.ip for e in session.scalars(select(AuditEvent))}


# --- TOTP replay ---------------------------------------------------------------------------

def test_a_totp_code_works_only_once(client, clock):
    _, secret = make_admin()
    used = code(secret, clock)
    first = password_step(client)
    assert client.post("/auth/totp", json={"code": used},
                       headers=bearer(first["session_token"])).status_code == 200
    second = password_step(client)
    resp = client.post("/auth/totp", json={"code": used}, headers=bearer(second["session_token"]))
    assert resp.status_code == 400 and resp.json()["error_code"] == "INVALID_CODE"
    # An older step is refused too; the next one works.
    assert client.post("/auth/totp", json={"code": code(secret, clock, -1)},
                       headers=bearer(second["session_token"])).status_code == 400
    assert client.post("/auth/totp", json={"code": code(secret, clock, +1)},
                       headers=bearer(second["session_token"])).status_code == 200


def test_codes_outside_the_window_are_refused(client, clock):
    _, secret = make_admin()
    pending = password_step(client)
    for offset in (-2, 2):
        assert client.post("/auth/totp", json={"code": code(secret, clock, offset)},
                           headers=bearer(pending["session_token"])).status_code == 400


# --- enrolment and recovery codes ------------------------------------------------------------

def test_enrolment_through_the_setup_link(client, clock):
    from app import cli

    link = cli.create_admin(make_org(), "new@endod.example", "New Admin")
    resp = client.post("/auth/setup", json={"token": setup_token(link), "password": PASSWORD})
    assert resp.status_code == 200 and resp.json()["stage"] == "enroll"
    headers = bearer(resp.json()["session_token"])
    # Nothing else is reachable before enrolling.
    assert client.get("/overview", headers=headers).status_code == 403
    assert client.post("/auth/totp", json={"code": "123456"}, headers=headers).status_code == 409

    start = client.post("/auth/enroll/start", headers=headers).json()
    assert start["issuer"] == "TenaCare" and start["account"] == "new@endod.example"
    assert start["otpauth_uri"].startswith("otpauth://totp/TenaCare:new%40endod.example?")
    # Asking again shows the same secret until it is confirmed.
    assert client.post("/auth/enroll/start", headers=headers).json()["secret"] == start["secret"]

    bad = client.post("/auth/enroll/confirm", json={"code": code(start["secret"], clock, 5)}, headers=headers)
    assert bad.status_code == 400
    resp = client.post("/auth/enroll/confirm", json={"code": code(start["secret"], clock)}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stage"] == "full" and len(body["recovery_codes"]) == 10
    assert len(set(body["recovery_codes"])) == 10
    assert client.get("/overview", headers=bearer(body["session_token"])).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401  # rotated

    with session_scope() as session:
        admin = session.scalar(select(OrgAdmin).where(OrgAdmin.email == "new@endod.example"))
        assert admin.totp_pending_secret is None and start["secret"] not in admin.totp_secret
        stored = [r.code_hash for r in session.scalars(select(RecoveryCode))]
    assert len(stored) == 10 and not set(body["recovery_codes"]) & set(stored)
    assert [e[:2] for e in events("totp_enrolled")] == [("totp_enrolled", "failure"), ("totp_enrolled", "success")]
    assert [e[1] for e in events("enrolment_started")] == ["success"]
    # Enrolled: the password now opens the code step.
    assert password_step(client, "new@endod.example")["stage"] == "totp"


def test_recovery_code_signs_in_once(client, clock):
    from app import cli

    _, _, recovery_codes = enrol_via_link(client, clock, cli.create_admin(make_org(), "new@endod.example", "New"))
    recovery = recovery_codes[0]
    pending = password_step(client, "new@endod.example")
    resp = client.post("/auth/totp", json={"recovery_code": recovery.upper()},
                       headers=bearer(pending["session_token"]))
    assert resp.status_code == 200 and resp.json()["recovery_codes_left"] == 9
    pending = password_step(client, "new@endod.example")
    assert client.post("/auth/totp", json={"recovery_code": recovery},
                       headers=bearer(pending["session_token"])).status_code == 400
    assert "recovery_code" in events("sign_in")[-2][4]


def test_enrolment_cannot_be_restarted_after_it_is_done(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    assert client.post("/auth/enroll/start", headers=headers).status_code == 409


# --- sessions -------------------------------------------------------------------------------

def test_idle_timeout(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    assert client.get("/auth/me", headers=headers).status_code == 200
    with session_scope() as session:
        session.execute(update(AdminSession).values(last_seen_at=utcnow() - timedelta(minutes=31)))
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 401 and resp.json()["error_code"] == "SESSION_ENDED"


def test_activity_keeps_the_session_alive(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    with session_scope() as session:
        session.execute(update(AdminSession).values(last_seen_at=utcnow() - timedelta(minutes=29)))
    assert client.get("/auth/me", headers=headers).status_code == 200


def test_absolute_limit(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    with session_scope() as session:
        session.execute(update(AdminSession).values(expires_at=utcnow() - timedelta(seconds=1)))
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_pending_session_expires(client):
    make_admin()
    pending = password_step(client)
    with session_scope() as session:
        session.execute(update(AdminSession).values(expires_at=utcnow() - timedelta(seconds=1)))
    assert client.post("/auth/totp", json={"code": "123456"},
                       headers=bearer(pending["session_token"])).status_code == 401


def test_sign_out_revokes(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert [e[1] for e in events("sign_out")] == ["success"]


def test_a_disabled_admin_is_signed_out(client, clock):
    admin_id, secret = make_admin()
    headers = sign_in(client, clock, secret)
    with session_scope() as session:
        session.execute(update(OrgAdmin).where(OrgAdmin.id == admin_id).values(active=False))
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_garbage_tokens(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


# --- re-authentication ------------------------------------------------------------------------

POLICY = {"annual_limit_santim": 500_000, "copay_percent": 10, "dependants_covered": True,
          "excluded_medicines": [], "year_start_month": 1, "year_start_day": 1}


def test_reauth_is_needed_for_sensitive_actions(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    resp = client.put("/policy", json=POLICY, headers=headers)
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    assert client.get("/policy", headers=headers).json()["copay_percent"] == 0  # nothing changed

    bad = client.post("/auth/reauth", json={"code": "000000"}, headers=headers)
    assert bad.status_code == 400
    reauth(client, clock, secret, headers)
    me = client.get("/auth/me", headers=headers).json()
    assert me["reauth_valid_until"] is not None
    assert client.put("/policy", json=POLICY, headers=headers).status_code == 200
    assert [e[1] for e in events("reauth")] == ["failure", "success"]


def test_reauth_lasts_ten_minutes(client, clock):
    _, secret = make_admin()
    headers = sign_in(client, clock, secret)
    reauth(client, clock, secret, headers)
    with session_scope() as session:
        session.execute(update(AdminSession).values(reauth_at=utcnow() - timedelta(minutes=10, seconds=1)))
    resp = client.put("/policy", json=POLICY, headers=headers)
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"


def test_reauth_refuses_a_replayed_code(client, clock):
    _, secret = make_admin()
    pending = password_step(client)
    used = code(secret, clock)
    resp = client.post("/auth/totp", json={"code": used}, headers=bearer(pending["session_token"]))
    headers = bearer(resp.json()["session_token"])
    assert client.post("/auth/reauth", json={"code": used}, headers=headers).status_code == 400


def test_reauth_belongs_to_one_session(client, clock):
    _, secret = make_admin()
    first = sign_in(client, clock, secret)
    second = sign_in(client, clock, secret)
    reauth(client, clock, secret, first)
    assert client.put("/policy", json=POLICY, headers=second).status_code == 403


def test_failed_reauth_codes_end_only_that_session(client, clock):
    _, secret = make_admin()
    other = sign_in(client, clock, secret, ip=OTHER_IP)
    headers = sign_in(client, clock, secret)
    for _ in range(4):
        assert client.post("/auth/reauth", json={"code": "000000"}, headers=headers).status_code == 400
    assert client.post("/auth/reauth", json={"code": "000000"}, headers=headers).status_code == 401
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/me", headers=other).status_code == 200


# --- setup links --------------------------------------------------------------------------------

def test_setup_link(client, clock):
    from app import cli

    link = cli.create_admin(make_org(), "fresh@endod.example", "Fresh Admin")
    assert link.startswith("https://organisation.example/setup#")
    token = setup_token(link)
    check = client.post("/auth/setup/check", json={"token": token})
    assert check.status_code == 200 and check.json()["email"] == "fresh@endod.example"
    assert check.json()["mode"] == "set"

    weak = client.post("/auth/setup", json={"token": token, "password": "password1"})
    assert weak.status_code == 400 and weak.json()["error_code"] == "WEAK_PASSWORD"
    resp = client.post("/auth/setup", json={"token": token, "password": "a long passphrase"})
    assert resp.status_code == 200 and resp.json()["stage"] == "enroll"
    # One use only.
    assert client.post("/auth/setup/check", json={"token": token}).status_code == 400
    assert client.post("/auth/setup", json={"token": token, "password": "another passphrase"}).status_code == 400
    headers = bearer(resp.json()["session_token"])
    secret = client.post("/auth/enroll/start", headers=headers).json()["secret"]
    done = client.post("/auth/enroll/confirm", json={"code": code(secret, clock)}, headers=headers)
    assert done.status_code == 200 and len(done.json()["recovery_codes"]) == 10
    assert [e[1] for e in events("setup_completed")] == ["success"]


def test_setup_link_for_an_admin_with_a_password_asks_for_it(client, clock):
    from app import cli

    link = cli.create_admin(make_org(), "pw@endod.example", "Pw Admin", password=PASSWORD)
    token = setup_token(link)
    assert client.post("/auth/setup/check", json={"token": token}).json()["mode"] == "confirm"
    wrong = client.post("/auth/setup", json={"token": token, "password": "not the password"})
    assert wrong.status_code == 400 and wrong.json()["error_code"] == "WRONG_PASSWORD"
    # A wrong password does not use the link up; the right one does.
    assert client.post("/auth/setup/check", json={"token": token}).status_code == 200
    headers, secret, _ = enrol_via_link(client, clock, link)
    with session_scope() as session:
        assert session.scalar(select(OrgAdmin.password_hash)).startswith("$argon2id$")
    assert sign_in(client, clock, secret, email="pw@endod.example")


def test_setup_link_password_guesses_are_throttled(client):
    from app import cli

    token = setup_token(cli.create_admin(make_org(), "pw@endod.example", "Pw Admin", password=PASSWORD))
    for n in range(5):
        assert client.post("/auth/setup", json={"token": token, "password": f"guess-{n}"}).status_code == 400
    locked = client.post("/auth/setup", json={"token": token, "password": PASSWORD})
    assert locked.status_code == 401 and locked.json()["error_code"] == "LOCKED"
    assert client.post("/auth/setup", json={"token": token, "password": PASSWORD},
                       headers=from_ip(OTHER_IP)).status_code == 200


def test_a_setup_link_is_claimed_once_under_concurrency(client):
    """Two uses of one link at the same moment: exactly one session."""
    from app import auth, cli

    token = setup_token(cli.create_admin(make_org(), "race@endod.example", "Race"))
    barrier = threading.Barrier(4)
    results = []

    def use(n):
        barrier.wait()
        try:
            auth.setup_complete(token, f"a long passphrase {n}", f"192.0.2.{n + 1}", None)
            results.append("ok")
        except Exception as exc:  # the loser: invalid link, or the database refusing the second writer
            results.append(type(exc).__name__)

    threads = [threading.Thread(target=use, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert results.count("ok") == 1, results
    with session_scope() as session:
        sessions = list(session.scalars(select(AdminSession)))
    assert len(sessions) == 1
    assert len(events("setup_completed")) == 1


def test_expired_setup_link(client):
    from app import cli
    from app.models import SetupToken

    token = setup_token(cli.create_admin(make_org(), "fresh@endod.example", "Fresh Admin"))
    with session_scope() as session:
        session.execute(update(SetupToken).values(expires_at=utcnow() - timedelta(seconds=1)))
    resp = client.post("/auth/setup/check", json={"token": token})
    assert resp.status_code == 400 and resp.json()["error_code"] == "INVALID_SETUP_LINK"
    assert client.post("/auth/setup/check", json={"token": "x" * 43}).status_code == 400
    assert [e[1] for e in events("setup_link")] == ["failure", "failure"]


def test_setup_link_is_valid_for_24_hours(client):
    from app import cli
    from app.models import SetupToken

    cli.create_admin(make_org(), "fresh@endod.example", "Fresh Admin")
    with session_scope() as session:
        link = session.scalar(select(SetupToken))
        lifetime = link.expires_at - link.created_at
    assert timedelta(hours=23, minutes=59) < lifetime <= timedelta(hours=24)


def test_no_public_sign_up(client):
    paths = set(client.app.openapi()["paths"])
    assert not any("signup" in p or "register" in p for p in paths)
    for path in ("/admins", "/organisations", "/auth/register", "/auth/signup"):
        assert client.post(path, json={"email": "x@y.z"}).status_code in (401, 404, 405)


# --- organisations ------------------------------------------------------------------------------

def test_me_names_the_admins_organisation(client, clock):
    org_id = make_org("Awash Breweries")
    _, secret = make_admin(organisation_id=org_id)
    headers = sign_in(client, clock, secret)
    me = client.get("/auth/me", headers=headers).json()
    assert me["organisation"] == {"id": org_id, "name": "Awash Breweries", "application_status": "approved"}


def test_a_suspended_organisation_cannot_sign_in_and_its_sessions_end(client, clock):
    from app.models import Organisation

    org_id = make_org()
    _, secret = make_admin(organisation_id=org_id)
    headers = sign_in(client, clock, secret)
    with session_scope() as session:
        session.execute(update(Organisation).where(Organisation.id == org_id).values(status="suspended"))
    assert client.get("/auth/me", headers=headers).status_code == 401
    resp = _login(client)
    assert resp.status_code == 401 and resp.json()["error"] == INVALID_LOGIN
    assert "organisation_suspended" in events("sign_in")[-1][4]

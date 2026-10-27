import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import enrol_via_link, events, password_step
from sqlalchemy import select

from app import cli
from app.db import platform_session
from app.models import AdminSession, BenefitPolicy, Organisation, OrgAdmin


def run(*argv, stdin=""):
    out = io.StringIO()
    status = cli.main(list(argv), stdin=io.StringIO(stdin), stdout=out)
    return status, out.getvalue()


def new_org(name="Tena Logistics PLC", tin="0012345678"):
    status, out = run("create-org", "--name", name, "--tin", tin)
    assert status == 0
    return out.strip().splitlines()[-1]


def test_create_org_prints_its_id_and_gives_it_the_default_policy(db):
    status, out = run("create-org", "--name", "  Tena   Logistics PLC ", "--tin", "001-234-5678",
                      "--contact-email", "HR@Tena.example", "--contact-phone", "0911223344")
    assert status == 0
    org_id = out.strip().splitlines()[-1]
    assert len(org_id) == 32
    with platform_session() as session:
        org = session.get(Organisation, org_id)
        assert (org.name, org.tin, org.status, org.contact_email, org.contact_phone) == (
            "Tena Logistics PLC", "0012345678", "active", "hr@tena.example", "+251911223344")
        policy = session.scalar(select(BenefitPolicy).where(BenefitPolicy.organisation_id == org_id))
        assert policy.employee_id is None and policy.annual_limit_santim == 1_000_000
    assert [e[:2] for e in events("organisation_created")] == [("organisation_created", "success")]


def test_create_org_refuses_bad_or_duplicate_tins(db):
    new_org(tin="0012345678")
    with pytest.raises(SystemExit, match="already exists"):
        run("create-org", "--name", "Again", "--tin", "0012345678")
    with pytest.raises(SystemExit, match="10 digits"):
        run("create-org", "--name", "Bad", "--tin", "12345")
    with pytest.raises(SystemExit, match="--name"):
        run("create-org", "--name", "x", "--tin", "0099999999")


def test_create_admin_prints_a_setup_link(client):
    org_id = new_org()
    status, out = run("create-admin", "--org", org_id, "--email", "Hr@Tena.Example", "--name", "Selam  Tesfaye")
    assert status == 0
    link = out.strip().splitlines()[-1]
    assert link.startswith("https://organisation.example/setup#") and len(link.split("#")[1]) >= 40
    with platform_session() as session:
        admin = session.scalar(select(OrgAdmin))
        assert (admin.email, admin.name, admin.organisation_id, admin.password_hash, admin.totp_secret) == (
            "hr@tena.example", "Selam Tesfaye", org_id, None, None)
    assert client.post("/auth/setup/check", json={"token": link.split("#")[1]}).status_code == 200
    assert client.post("/auth/login", json={"email": "hr@tena.example", "password": "anything-at-all"}
                       ).status_code == 401
    assert [e[:2] for e in events("admin_created")] == [("admin_created", "success")]


def test_create_admin_needs_a_real_organisation(db):
    with pytest.raises(SystemExit, match="No organisation"):
        run("create-admin", "--org", "a1" * 16, "--email", "hr@tena.example", "--name", "Selam")
    with pytest.raises(SystemExit, match="No organisation"):
        run("create-admin", "--org", "../../etc", "--email", "hr@tena.example", "--name", "Selam")
    with pytest.raises(SystemExit):
        run("create-admin", "--email", "hr@tena.example", "--name", "Selam")


def test_create_admin_with_password_from_stdin(client, clock):
    org_id = new_org()
    status, out = run("create-admin", "--org", org_id, "--email", "hr@tena.example", "--name", "Selam",
                      "--password-stdin", stdin="a long passphrase\n")
    assert status == 0
    assert "a long passphrase" not in out
    link = out.strip().splitlines()[-1]
    assert "/setup#" in link
    with platform_session() as session:
        assert session.scalar(select(OrgAdmin.password_hash)).startswith("$argon2id$")
    refused = client.post("/auth/login", json={"email": "hr@tena.example", "password": "a long passphrase"})
    assert refused.status_code == 401 and refused.json()["error"] == "Incorrect email or password."
    assert client.post("/auth/setup/check", json={"token": link.split("#")[1]}).json()["mode"] == "confirm"
    headers, secret, codes = enrol_via_link(client, clock, link, password="a long passphrase")
    assert len(codes) == 10 and client.get("/overview", headers=headers).status_code == 200
    assert password_step(client, "hr@tena.example", "a long passphrase")["stage"] == "totp"


def test_password_stdin_follows_the_policy(db):
    org_id = new_org()
    base = ("create-admin", "--org", org_id, "--email", "hr@tena.example", "--name", "Selam", "--password-stdin")
    with pytest.raises(SystemExit, match="too common"):
        run(*base, stdin="password1\n")
    with pytest.raises(SystemExit, match="email"):
        run(*base, stdin="hr@tena.example")
    with pytest.raises(SystemExit, match="at least 8"):
        run(*base, stdin="short\n")
    with pytest.raises(SystemExit, match="No password"):
        run(*base, stdin="")
    with platform_session() as session:
        assert session.scalar(select(OrgAdmin)) is None


def test_there_is_no_password_argument(db):
    with pytest.raises(SystemExit):
        run("create-admin", "--org", "x", "--email", "hr@tena.example", "--name", "Selam", "--password", "pw")


def test_duplicate_and_invalid_email(db):
    org_id = new_org()
    run("create-admin", "--org", org_id, "--email", "hr@tena.example", "--name", "Selam")
    with pytest.raises(SystemExit, match="already exists"):
        run("create-admin", "--org", org_id, "--email", "HR@tena.example", "--name", "Selam")
    with pytest.raises(SystemExit, match="not a valid email"):
        run("create-admin", "--org", org_id, "--email", "not-an-email", "--name", "Selam")


def test_reset_2fa(client, clock):
    org_id = new_org()
    _, out = run("create-admin", "--org", org_id, "--email", "hr@tena.example", "--name", "Selam",
                 "--password-stdin", stdin="a long passphrase")
    full, _, _ = enrol_via_link(client, clock, out.strip().splitlines()[-1], password="a long passphrase")
    status, out = run("reset-2fa", "--email", "hr@tena.example")
    assert status == 0 and "setup#" in out
    assert client.get("/auth/me", headers=full).status_code == 401
    assert client.post("/auth/login", json={"email": "hr@tena.example", "password": "a long passphrase"}
                       ).status_code == 401
    token = out.strip().splitlines()[-1].split("#")[1]
    assert client.post("/auth/setup/check", json={"token": token}).json()["mode"] == "set"
    resp = client.post("/auth/setup", json={"token": token, "password": "a new passphrase"})
    assert resp.status_code == 200 and resp.json()["stage"] == "enroll"
    assert [e[1] for e in events("admin_2fa_reset")] == ["success"]


def test_disable(client, clock):
    org_id = new_org()
    _, out = run("create-admin", "--org", org_id, "--email", "hr@tena.example", "--name", "Selam",
                 "--password-stdin", stdin="a long passphrase")
    full, _, _ = enrol_via_link(client, clock, out.strip().splitlines()[-1], password="a long passphrase")
    status, out = run("disable", "--email", "hr@tena.example")
    assert status == 0 and "disabled" in out
    assert client.get("/auth/me", headers=full).status_code == 401
    with platform_session() as session:
        assert all(s.revoked_at is not None for s in session.scalars(select(AdminSession)))
    with pytest.raises(SystemExit, match="No admin"):
        run("disable", "--email", "nobody@tena.example")


def test_list_orgs_and_admins(db):
    assert run("list-orgs")[1].strip() == "No organisations."
    assert run("list-admins")[1].strip() == "No admins."
    first = new_org("Alpha PLC", "0000000001")
    second = new_org("Beta PLC", "0000000002")
    run("create-admin", "--org", first, "--email", "a@alpha.example", "--name", "Alpha Admin")
    run("create-admin", "--org", second, "--email", "b@beta.example", "--name", "Beta Admin")
    run("disable", "--email", "b@beta.example")
    orgs = run("list-orgs")[1].strip().splitlines()
    assert orgs[0].startswith(first) and "Alpha PLC" in orgs[0] and "admins 1" in orgs[0]
    lines = run("list-admins")[1].strip().splitlines()
    assert lines[0].startswith("a@alpha.example") and "no-2fa" in lines[0] and "(Alpha PLC)" in lines[0]
    assert "disabled" in lines[1]
    only = run("list-admins", "--org", second)[1].strip().splitlines()
    assert len(only) == 1 and only[0].startswith("b@beta.example")


def test_runs_as_a_module(db, tmp_path):
    """`python -m app.cli` with the password on stdin, as an operator would run it."""
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ}
    made = subprocess.run([sys.executable, "-m", "app.cli", "create-org", "--name", "Module Org", "--tin",
                           "0011223344"], capture_output=True, text=True, cwd=backend, env=env, timeout=60)
    assert made.returncode == 0, made.stderr
    org_id = made.stdout.strip().splitlines()[-1]
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "create-admin", "--org", org_id, "--email", "cli@tena.example",
         "--name", "Cli", "--password-stdin"],
        input="a long passphrase\n", capture_output=True, text=True, cwd=backend, env=env, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "a long passphrase" not in result.stdout + result.stderr
    with platform_session() as session:
        assert session.scalar(select(OrgAdmin.email)) == "cli@tena.example"

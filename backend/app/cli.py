"""Operator commands, run by Endod (companies can also apply themselves through
the web app: app.api.application; organisations made here are approved).

    python -m app.cli create-org --name "Ethio Telecom" --tin 0000030603

prints the new organisation's id. Then, for each HR / benefits admin:

    python -m app.cli create-admin --org <organisation id> --email hr@example.et --name "Selam Tesfaye"

prints a one-time setup link (valid 24 hours) to set a password and enrol an
authenticator. With ``--password-stdin`` the password is read from standard
input instead (never from the command line); a setup link is still printed,
and the admin enrols through it (the link asks for that password). Until an
admin has enrolled, signing in with the password alone is refused:

    printf '%s' "$PASSWORD" | python -m app.cli create-admin --org ... --email ... --name ... --password-stdin

    python -m app.cli reset-2fa --email hr@example.et   # new setup link; password and authenticator void
    python -m app.cli disable --email hr@example.et     # signs them out everywhere
    python -m app.cli list-orgs
    python -m app.cli list-admins [--org <organisation id>]
    python -m app.cli sweep-drafts                      # delete expired drafts now (cron; the API also does it)
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Optional, TextIO

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import delete, func, select

from app import audit, auth, security, validation
from app.db import ensure_aware, platform_session, utcnow
from app.models import AuditResult, BenefitPolicy, Organisation, OrganisationApplication, OrgAdmin, RecoveryCode
from app.policy import DEFAULT_ANNUAL_LIMIT_SANTIM

CLI_DETAIL = {"via": "cli"}


def _email(value: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise SystemExit(f"--email is not a valid email: {exc}") from exc


def _find(session, email: str) -> OrgAdmin:
    admin = session.scalar(select(OrgAdmin).where(OrgAdmin.email == _email(email)))
    if admin is None:
        raise SystemExit(f"No admin with email {email.strip().lower()}.")
    return admin


def read_password(stream: TextIO) -> str:
    """The password from standard input: the first line, without its line ending."""
    line = stream.readline()
    return line[:-1] if line.endswith("\n") else line


def create_org(name: str, tin: str, contact_name: Optional[str] = None, contact_email: Optional[str] = None,
               contact_phone: Optional[str] = None) -> str:
    """Create an organisation with the default benefit policy; returns its id."""
    try:
        name = validation.text(name, "--name", min_len=2, max_len=200)
        tin = validation.tin(tin, "--tin")
        contact_name = validation.optional_text(contact_name, "--contact-name")
        contact_phone = validation.phone(contact_phone) if contact_phone else None
    except validation.Invalid as exc:
        raise SystemExit(str(exc)) from exc
    contact_email = _email(contact_email) if contact_email else None
    with platform_session() as session:
        if session.scalar(select(Organisation.id).where(Organisation.tin == tin)) is not None:
            raise SystemExit(f"An organisation with TIN {tin} already exists.")
        org = Organisation(name=name, tin=tin, contact_name=contact_name, contact_email=contact_email,
                           contact_phone=contact_phone)
        session.add(org)
        session.flush()
        session.add(BenefitPolicy(organisation_id=org.id, employee_id=None,
                                  annual_limit_santim=DEFAULT_ANNUAL_LIMIT_SANTIM, copay_percent=0,
                                  dependants_covered=True, excluded_medicines="[]",
                                  year_start_month=1, year_start_day=1))
        audit.record(session, audit.ORG_CREATED, AuditResult.SUCCESS, organisation_id=org.id,
                     target_type="organisation", target_id=org.id, target_name=name, detail={**CLI_DETAIL, "tin": tin})
        return org.id


def create_admin(organisation_id: str, email: str, name: str, password: Optional[str] = None) -> str:
    """Create an admin of one organisation. Returns the one-time setup link
    (it sets the password, or, when one was given, asks for it)."""
    email = _email(email)
    name = " ".join(name.split())
    if not 2 <= len(name) <= 120:
        raise SystemExit("--name must be 2-120 characters.")
    if password is not None:
        problem = security.password_problem(password, email)
        if problem:
            raise SystemExit(problem)
    with platform_session() as session:
        if not re.fullmatch(r"[0-9a-f]{32}", organisation_id or "") or session.get(Organisation, organisation_id) is None:
            raise SystemExit(f"No organisation with id {organisation_id}. See list-orgs.")
        if session.scalar(select(OrgAdmin).where(OrgAdmin.email == email)) is not None:
            raise SystemExit(f"An admin with email {email} already exists.")
        admin = OrgAdmin(organisation_id=organisation_id, email=email, name=name,
                         password_hash=security.hash_password(password) if password is not None else None)
        session.add(admin)
        session.flush()
        audit.record(session, audit.ADMIN_CREATED, AuditResult.SUCCESS, organisation_id=organisation_id,
                     admin_id=admin.id, admin_email=email,
                     detail={**CLI_DETAIL, "with_password": password is not None})
        return auth.issue_setup_link(session, admin)


def reset_2fa(email: str) -> str:
    """Void the admin's authenticator, recovery codes, password and sessions;
    return a new setup link (the only way back in)."""
    now = utcnow()
    with platform_session() as session:
        admin = _find(session, email)
        admin.totp_secret = admin.totp_pending_secret = None
        admin.totp_last_step = admin.totp_enrolled_at = None
        admin.password_hash = None
        admin.failed_attempts, admin.last_failed_at, admin.backoff_until = 0, None, None
        session.execute(delete(RecoveryCode).where(RecoveryCode.admin_id == admin.id))
        auth.revoke_all(session, admin.id, now)
        audit.record(session, audit.TWO_FACTOR_RESET, AuditResult.SUCCESS, organisation_id=admin.organisation_id,
                     admin_id=admin.id, admin_email=admin.email, detail=CLI_DETAIL)
        return auth.issue_setup_link(session, admin, now)


def disable(email: str) -> None:
    now = utcnow()
    with platform_session() as session:
        admin = _find(session, email)
        admin.active = False
        auth.revoke_all(session, admin.id, now)
        audit.record(session, audit.ADMIN_DISABLED, AuditResult.SUCCESS, organisation_id=admin.organisation_id,
                     admin_id=admin.id, admin_email=admin.email, detail=CLI_DETAIL)


def list_orgs(out: TextIO) -> None:
    with platform_session() as session:
        counts = dict(session.execute(select(OrgAdmin.organisation_id, func.count())
                                      .group_by(OrgAdmin.organisation_id)).all())
        applying = dict(session.execute(select(OrganisationApplication.organisation_id, OrganisationApplication.status)
                                        .where(OrganisationApplication.status != "approved")).all())
        orgs = list(session.scalars(select(Organisation).order_by(Organisation.created_at)))
        if not orgs:
            print("No organisations.", file=out)
        for o in orgs:
            # A company still applying has no TIN of its own yet (see the platform API).
            tin = o.tin if o.id not in applying else "-".ljust(10)
            note = f"  (application {applying[o.id]})" if o.id in applying else ""
            print(f"{o.id}  {tin}  {o.status:9} admins {counts.get(o.id, 0):<3} {o.name}{note}", file=out)


def list_admins(out: TextIO, organisation_id: Optional[str] = None) -> None:
    now = utcnow()
    with platform_session() as session:
        query = select(OrgAdmin, Organisation.name).join(Organisation, Organisation.id == OrgAdmin.organisation_id)
        if organisation_id:
            query = query.where(OrgAdmin.organisation_id == organisation_id)
        rows = session.execute(query.order_by(Organisation.name, OrgAdmin.created_at)).all()
        if not rows:
            print("No admins.", file=out)
        for a, org_name in rows:
            state = "active" if a.active else "disabled"
            if a.backoff_until and ensure_aware(a.backoff_until) > now:
                state = "backoff"
            two_factor = "2fa" if a.totp_secret else "no-2fa"
            last = ensure_aware(a.last_login_at).strftime("%Y-%m-%d %H:%M UTC") if a.last_login_at else "never"
            print(f"{a.email:40} {state:9} {two_factor:7} last sign-in {last:21} {a.name} ({org_name})", file=out)


def main(argv: list[str] | None = None, stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    org = commands.add_parser("create-org", help="create an organisation (prints its id)")
    org.add_argument("--name", required=True)
    org.add_argument("--tin", required=True)
    org.add_argument("--contact-name")
    org.add_argument("--contact-email")
    org.add_argument("--contact-phone")
    create = commands.add_parser("create-admin", help="create an organisation admin (prints a one-time setup link)")
    create.add_argument("--org", required=True, help="the organisation's id (see list-orgs)")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--password-stdin", action="store_true",
                        help="read the initial password from standard input (TOTP is enrolled through the link)")
    for name, help_text in (("reset-2fa", "void an admin's authenticator and password; print a new setup link"),
                            ("disable", "disable an admin and end their sessions")):
        cmd = commands.add_parser(name, help=help_text)
        cmd.add_argument("--email", required=True)
    commands.add_parser("list-orgs", help="list organisations")
    commands.add_parser("sweep-drafts", help="delete company drafts not submitted in time (prints how many)")
    admins = commands.add_parser("list-admins", help="list admins")
    admins.add_argument("--org", help="only this organisation's")
    args = parser.parse_args(argv)

    if args.command == "create-org":
        org_id = create_org(args.name, args.tin, args.contact_name, args.contact_email, args.contact_phone)
        print(f"Organisation created. Its id (for create-admin --org):", file=stdout)
        print(org_id, file=stdout)
        return 0
    if args.command == "create-admin":
        password = read_password(stdin) if args.password_stdin else None
        if args.password_stdin and not password:
            raise SystemExit("No password on standard input.")
        link = create_admin(args.org, args.email, args.name, password)
        email = _email(args.email)
        if password is not None:
            print(f"Admin {email} created with the password given. They must open this one-time setup "
                  f"link (valid 24 hours), enter that password and enrol an authenticator app; "
                  f"until then, signing in is refused:", file=stdout)
        else:
            print(f"Admin {email} created. One-time setup link (valid 24 hours):", file=stdout)
        print(link, file=stdout)
        return 0
    if args.command == "reset-2fa":
        link = reset_2fa(args.email)
        print(f"Two-factor sign-in and password reset for {_email(args.email)}; their sessions are ended. "
              f"New one-time setup link (valid 24 hours):", file=stdout)
        print(link, file=stdout)
        return 0
    if args.command == "disable":
        disable(args.email)
        print(f"Admin {_email(args.email)} disabled; their sessions are ended.", file=stdout)
        return 0
    if args.command == "list-orgs":
        list_orgs(stdout)
        return 0
    if args.command == "sweep-drafts":
        from app import onboarding

        swept = onboarding.sweep_now(force=True)
        print("Another sweep is running; nothing done." if swept is None else f"{swept} expired draft(s) deleted.",
              file=stdout)
        return 0
    if args.command == "list-admins":
        list_admins(stdout, args.org)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

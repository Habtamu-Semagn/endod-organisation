"""Same-organisation foreign keys (migration 0005, app.models.same_org): a row
can only point at rows of its own organisation, enforced by the database even
when every application check is bypassed (here: raw rows in the platform
scope, which row-level security lets write anywhere). SQLite and PostgreSQL."""

from datetime import date

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from test_rls import _seed


@pytest.fixture
def orgs(db):
    return _seed("Alpha"), _seed("Beta")


def _rows(a, b):
    """For each same-organisation key: a new row of A that points at B's parent."""
    from app.models import BenefitPolicy, Claim, Dependant

    def claim(**refs):
        fields = dict(organisation_id=a["organisation"], number=50, employee_id=a["employee"],
                      pharmacy_name="P", pharmacy_tin="0012345678", receipt_number="X-1",
                      receipt_date=date(2026, 10, 1), total_santim=100)
        return Claim(**{**fields, **refs})

    return {
        "claims.employee_id": lambda s: claim(employee_id=b["employee"]),
        "claims.dependant_id": lambda s: claim(dependant_id=b["dependant"]),
        "claims.receipt_file_id": lambda s: claim(receipt_file_id=b["receipt"]),
        "claims.batch_id": lambda s: claim(batch_id=b["batch"]),
        "dependants.employee_id": lambda s: Dependant(organisation_id=a["organisation"], employee_id=b["employee"],
                                                      name="Cross", relationship="child"),
        "benefit_policies.employee_id": lambda s: BenefitPolicy(organisation_id=a["organisation"],
                                                                employee_id=b["employee"], annual_limit_santim=1),
    }


def _keys(orgs):
    """The seeds' keys plus the ids of their dependant, receipt and batch."""
    from sqlalchemy import select

    from app.db import platform_session
    from app.models import Dependant, PaymentBatch, ReceiptFile

    out = []
    with platform_session() as session:
        for keys in orgs:
            org = keys["organisation"]
            out.append({**keys,
                        "dependant": session.scalar(select(Dependant.id).where(Dependant.organisation_id == org)),
                        "receipt": session.scalar(select(ReceiptFile.id).where(ReceiptFile.organisation_id == org)),
                        "batch": session.scalar(select(PaymentBatch.id).where(PaymentBatch.organisation_id == org))})
    return out


@pytest.mark.parametrize("reference", ["claims.employee_id", "claims.dependant_id", "claims.receipt_file_id",
                                       "claims.batch_id", "dependants.employee_id", "benefit_policies.employee_id"])
def test_a_new_row_cannot_point_at_another_organisations_row(orgs, reference):
    from app.db import platform_session

    a, b = _keys(orgs)
    with pytest.raises(IntegrityError):
        with platform_session() as session:
            session.add(_rows(a, b)[reference](session))
            session.flush()
    # The same row pointing at its own organisation's parent is fine.
    own = {"claims.employee_id": "employee", "claims.dependant_id": "dependant", "claims.receipt_file_id": None,
           "claims.batch_id": "batch", "dependants.employee_id": "employee",
           "benefit_policies.employee_id": "employee"}[reference]
    if own:
        with platform_session() as session:
            session.add(_rows(a, a)[reference](session))


@pytest.mark.parametrize("column,key", [("employee_id", "employee"), ("batch_id", "batch"),
                                        ("receipt_file_id", "receipt"), ("dependant_id", "dependant")])
def test_an_existing_claim_cannot_be_pointed_at_another_organisation(orgs, column, key):
    from app.db import platform_session
    from app.models import Claim

    a, b = _keys(orgs)
    with pytest.raises(IntegrityError):
        with platform_session() as session:
            session.execute(update(Claim).where(Claim.id == a["claim"]).values({column: b[key]}))


def test_an_application_contact_is_an_admin_of_the_same_organisation(orgs):
    from app.db import platform_session
    from app.models import OrganisationApplication

    a, b = _keys(orgs)
    with pytest.raises(IntegrityError):
        with platform_session() as session:
            session.execute(update(OrganisationApplication)
                            .where(OrganisationApplication.organisation_id == a["organisation"])
                            .values(contact_admin_id=b["admin"]))
    with platform_session() as session:
        session.execute(update(OrganisationApplication)
                        .where(OrganisationApplication.organisation_id == a["organisation"])
                        .values(contact_admin_id=None))


def test_deleting_an_employee_still_takes_their_dependants_and_override(orgs):
    from sqlalchemy import delete, select

    from app.db import platform_session
    from app.models import BenefitPolicy, Claim, Dependant, Employee

    a, _b = _keys(orgs)
    with platform_session() as session:
        session.add(BenefitPolicy(organisation_id=a["organisation"], employee_id=a["employee"], annual_limit_santim=1))
    with platform_session() as session:
        session.execute(delete(Claim).where(Claim.organisation_id == a["organisation"]))
        session.execute(delete(Employee).where(Employee.id == a["employee"]))
    with platform_session() as session:
        assert session.scalar(select(Dependant.id).where(Dependant.employee_id == a["employee"])) is None
        assert session.scalar(select(BenefitPolicy.id).where(BenefitPolicy.employee_id == a["employee"])) is None


@pytest.mark.parametrize("table", ["integration_assertions", "integration_requests", "integration_idempotency",
                                   "webhook_deliveries", "integration_payout_changes"])
def test_integration_rows_point_only_at_their_own_organisations_client(orgs, table):
    """Migration 0006: (organisation_id, client_pk) -> integration_clients (organisation_id, id)."""
    from app.db import platform_session, utcnow
    from app.models import (
        IntegrationAssertion, IntegrationIdempotency, IntegrationPayoutChange, IntegrationRequest, WebhookDelivery,
    )

    a, b = orgs

    def row(client_pk):
        org = a["organisation"]
        return {
            "integration_assertions": lambda: IntegrationAssertion(organisation_id=org, client_pk=client_pk,
                                                                   jti=f"jti-{client_pk}", expires_at=utcnow()),
            "integration_requests": lambda: IntegrationRequest(organisation_id=org, client_pk=client_pk, method="GET",
                                                               path="/z", status=200, duration_ms=1),
            "integration_idempotency": lambda: IntegrationIdempotency(organisation_id=org, client_pk=client_pk,
                                                                      key=f"key-{client_pk}", request_hash="0" * 64,
                                                                      status_code=200, response="{}"),
            "webhook_deliveries": lambda: WebhookDelivery(organisation_id=org, client_pk=client_pk, event_id="evt_9",
                                                          event_type="x", status="pending", attempts=0),
            "integration_payout_changes": lambda: IntegrationPayoutChange(
                organisation_id=org, employee_id=a["employee"], client_pk=client_pk, hold_until=utcnow()),
        }[table]()

    with pytest.raises(IntegrityError):
        with platform_session() as session:
            session.add(row(b["client"]))
            session.flush()
    with platform_session() as session:
        session.add(row(a["client"]))


def test_a_payout_change_points_only_at_its_own_organisations_employee(orgs):
    from app.db import platform_session, utcnow
    from app.models import IntegrationPayoutChange

    a, b = orgs
    with pytest.raises(IntegrityError):
        with platform_session() as session:
            session.add(IntegrationPayoutChange(organisation_id=a["organisation"], employee_id=b["employee"],
                                                client_pk=a["client"], hold_until=utcnow()))
            session.flush()

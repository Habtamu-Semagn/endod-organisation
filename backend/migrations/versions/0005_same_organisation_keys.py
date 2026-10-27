"""same-organisation foreign keys

Row-level security (0004) decides which rows a transaction sees and writes;
these keys decide what a row may point at. Every reference from one tenant
row to another becomes a composite foreign key on (organisation_id, id), with
a matching UNIQUE (organisation_id, id) on the parent, so the database refuses
a claim, dependant, policy override or application contact that points at
another organisation's row, whatever the application checks:

* claims -> employees, dependants, receipt_files, payment_batches;
* dependants -> employees; benefit_policies -> employees (both ON DELETE CASCADE, as before);
* organisation_applications.contact_admin_id -> org_admins (it had no key at all).

claim_items has no organisation_id: it refers to its claim by id, and its row
policy (0004) only admits an item whose claim is the tenant's. The admin-keyed
tables (sessions, recovery codes, setup links, throttles) are the same through
their admin. The *_by columns (created_by, reviewed_by, ...) are plain ids kept
for the record, like the audit log, and are not keys.

On an existing database every current reference is checked when its key is
added: the migration fails, changing nothing, if one points across
organisations. Downgrade restores the single-column keys.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28 09:00:00.000000
"""
from alembic import op


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

#: Parents that same-organisation keys point at.
PARENTS = ("org_admins", "employees", "dependants", "receipt_files", "payment_batches")

#: table -> [(column, parent, new name, old single-column key or None, ondelete)]
KEYS = {
    "dependants": [("employee_id", "employees", "fk_dependants_employee_same_org",
                    "fk_dependants_employee_id_employees", "CASCADE")],
    "benefit_policies": [("employee_id", "employees", "fk_benefit_policies_employee_same_org",
                          "fk_benefit_policies_employee_id_employees", "CASCADE")],
    "claims": [
        ("employee_id", "employees", "fk_claims_employee_same_org", "fk_claims_employee_id_employees", None),
        ("dependant_id", "dependants", "fk_claims_dependant_same_org", "fk_claims_dependant_id_dependants", None),
        ("receipt_file_id", "receipt_files", "fk_claims_receipt_file_same_org",
         "fk_claims_receipt_file_id_receipt_files", None),
        ("batch_id", "payment_batches", "fk_claims_batch_same_org", "fk_claims_batch_id_payment_batches", None),
    ],
    "organisation_applications": [("contact_admin_id", "org_admins", "fk_organisation_applications_contact_same_org",
                                   None, None)],
}


def upgrade() -> None:
    for parent in PARENTS:
        with op.batch_alter_table(parent) as batch:
            batch.create_unique_constraint(f"uq_{parent}_org_id", ["organisation_id", "id"])
    for table, keys in KEYS.items():
        with op.batch_alter_table(table) as batch:
            for column, parent, name, old, ondelete in keys:
                if old:
                    batch.drop_constraint(old, type_="foreignkey")
                batch.create_foreign_key(name, parent, ["organisation_id", column], ["organisation_id", "id"],
                                         ondelete=ondelete)


def downgrade() -> None:
    for table, keys in KEYS.items():
        with op.batch_alter_table(table) as batch:
            for column, parent, name, old, ondelete in keys:
                batch.drop_constraint(name, type_="foreignkey")
                if old:
                    batch.create_foreign_key(old, parent, [column], ["id"], ondelete=ondelete)
    for parent in PARENTS:
        with op.batch_alter_table(parent) as batch:
            batch.drop_constraint(f"uq_{parent}_org_id", type_="unique")

"""The roster: add, edit, search, deactivate, dependants, and CSV import
(preview with per-row errors, all-or-nothing commit) and export."""

import csv
import io

import pytest

from app import validation


def rows(text):
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


# --- validation -----------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, phone", [("0911223344", "+251911223344"), ("+251 91 122 3344", "+251911223344"),
                                        ("251711223344", "+251711223344"), ("911223344", "+251911223344"),
                                        ("(091) 122-3344", "+251911223344")])
def test_phones_are_stored_as_e164(raw, phone):
    assert validation.phone(raw) == phone


@pytest.mark.parametrize("raw", ["0811223344", "+254911223344", "09112233", "091122334455", "", "+2519112233a4",
                                 "٠٩١١٢٢٣٣٤٤"])
def test_bad_phones(raw):
    with pytest.raises(validation.Invalid):
        validation.phone(raw)


@pytest.mark.parametrize("raw, endod", [("DE123456", "DE123456"), ("de-123 456", "DE123456"), ("", None),
                                        (None, None)])
def test_endod_ids(raw, endod):
    assert validation.endod_id(raw) == endod


@pytest.mark.parametrize("raw", ["DE12345", "DE1234567", "XE123456", "DE12345A", "123456", "DE١٢٣٤٥٦"])
def test_bad_endod_ids(raw):
    with pytest.raises(validation.Invalid):
        validation.endod_id(raw)


def test_payout_details():
    assert validation.payout("CBE", "1000-1234-5678") == ("cbe", "100012345678")
    assert validation.payout("telebirr", "0912345678") == ("telebirr", "+251912345678")
    assert validation.payout(None, "") == (None, None)
    for method, account in (("cbe", None), (None, "1000123456"), ("cbe", "123"), ("telebirr", "1000123456"),
                            ("paypal", "x@y")):
        with pytest.raises(validation.Invalid):
            validation.payout(method, account)


# --- the API ---------------------------------------------------------------------------------------

def test_add_list_search_and_edit(portal):
    created = portal.employee(name="Bethlehem Haile", employee_number="ET-0381", phone="0914456789",
                              department="People & Culture", endod_id="de 000381")
    assert (created["phone"], created["endod_id"], created["active"]) == ("+251914456789", "DE000381", True)
    portal.employee(name="Dawit Bekele", department="Engineering")
    listed = portal.get("/employees").json()
    assert listed["total"] == 2 and listed["departments"] == ["Engineering", "People & Culture"]
    assert listed["counts"]["active"] == 2 and listed["counts"]["linked"] == 1
    assert [e["name"] for e in portal.get("/employees?q=bethle").json()["items"]] == ["Bethlehem Haile"]
    assert portal.get("/employees?q=DE000381").json()["total"] == 1
    assert portal.get("/employees?department=Engineering").json()["items"][0]["name"] == "Dawit Bekele"
    assert portal.get("/employees?q=_").json()["total"] == 2  # LIKE wildcards are plain text

    resp = portal.patch(f"/employees/{created['id']}", json={"department": "Finance", "endod_id": ""})
    assert resp.status_code == 200
    assert (resp.json()["department"], resp.json()["endod_id"]) == ("Finance", None)


def test_duplicates_and_bad_input_are_refused(portal):
    portal.employee(employee_number="ET-1", endod_id="DE111111")
    clash = portal.post("/employees", json={"employee_number": "ET-1", "name": "Again", "phone": "0911000000",
                                            "department": "Ops"})
    assert clash.status_code == 409 and clash.json()["error_code"] == "DUPLICATE_EMPLOYEE"
    clash = portal.post("/employees", json={"employee_number": "ET-2", "name": "Again", "phone": "0911000000",
                                            "department": "Ops", "endod_id": "DE111111"})
    assert clash.status_code == 409 and clash.json()["error_code"] == "DUPLICATE_ENDOD_ID"
    for bad in ({"phone": "12345"}, {"endod_id": "DE1"}, {"name": "x"}, {"employee_number": "a b"},
                {"payout_method": "cbe", "payout_account": None}, {"name": "Bad\u0000Name"}):
        body = {"employee_number": "ET-9", "name": "Fine Name", "phone": "0911000000", "department": "Ops", **bad}
        resp = portal.post("/employees", json=body)
        assert resp.status_code == 400, (bad, resp.text)


def test_deactivate_and_activate(portal):
    emp = portal.employee()
    off = portal.post(f"/employees/{emp['id']}/deactivate").json()
    assert off["active"] is False and off["deactivated_at"]
    assert portal.get("/employees").json()["total"] == 0
    assert portal.get("/employees?status=inactive").json()["total"] == 1
    assert portal.post(f"/employees/{emp['id']}/activate").json()["active"] is True


def test_dependants(portal):
    emp = portal.employee()
    detail = portal.post(f"/employees/{emp['id']}/dependants",
                         json={"name": "Kenenisa T.", "relationship": "Spouse", "birth_date": "1990-02-03"})
    assert detail.status_code == 201
    dependant = detail.json()["dependants"][0]
    assert (dependant["relationship"], dependant["active"]) == ("spouse", True)
    assert portal.post(f"/employees/{emp['id']}/dependants", json={"name": "X Y", "relationship": "cousin"}
                       ).status_code == 400
    assert portal.post(f"/employees/{emp['id']}/dependants",
                       json={"name": "Future", "relationship": "child", "birth_date": "2030-01-01"}).status_code == 400
    removed = portal.post(f"/employees/{emp['id']}/dependants/{dependant['id']}/remove").json()
    assert removed["dependants"][0]["active"] is False
    other = portal.employee()
    assert portal.post(f"/employees/{other['id']}/dependants/{dependant['id']}/remove").status_code == 404


def test_detail_shows_usage_and_recent_claims(portal):
    emp = portal.employee()
    portal.claim(emp["id"])
    detail = portal.get(f"/employees/{emp['id']}").json()
    assert detail["usage"] == {"policy_year": {"start": "2026-01-01", "end": "2026-12-31"}, "used_santim": 0,
                               "remaining_santim": 1_000_000}
    assert [c["code"] for c in detail["recent_claims"]] == ["CLM-000001"]
    assert detail["policy"]["override"] is None


def test_employee_policy_overrides_need_a_fresh_code(portal):
    emp = portal.employee()
    rules = {"annual_limit_santim": 1, "copay_percent": 0, "dependants_covered": True, "excluded_medicines": []}
    assert portal.put(f"/employees/{emp['id']}/policy", json=rules).status_code == 403
    assert portal.delete(f"/employees/{emp['id']}/policy").status_code == 403


# --- CSV import --------------------------------------------------------------------------------------

HEADER = "employee_number,name,phone,department,endod_id,payout_method,payout_account\n"


def test_import_preview_reports_every_row(portal):
    portal.employee(employee_number="ET-1", name="Existing One", phone="0911000001", department="Ops",
                    payout_method="cbe", payout_account="1000000000001")
    text = (HEADER
            + "ET-1,Existing One,0911000001,Ops,,cbe,1000000000001\n"  # unchanged
            + "ET-2,New Person,0911000002,Engineering,DE222222,telebirr,0911000002\n"  # create
            + "ET-3,Bad Phone,12345,Ops,DE1,,\n"  # two errors
            + "ET-2,Twice,0911000003,Ops,,,\n"  # duplicate number in the file
            + "\n"
            + "ET-4,Same Card,0911000004,Ops,DE222222,,\n")  # duplicate Endod ID in the file
    preview = portal.post("/employees/import/preview", json={"csv": text})
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert [(r["line"], r["action"]) for r in data["rows"]] == [
        (2, "unchanged"), (3, "create"), (4, "error"), (5, "error"), (7, "error")]
    assert any("Phone" in e for e in data["rows"][2]["errors"]) and any("Endod" in e for e in data["rows"][2]["errors"])
    assert "also on line 3" in data["rows"][3]["errors"][0]
    assert "DE222222 is also on line 3" in data["rows"][4]["errors"][0]
    assert data["summary"] == {"create": 1, "update": 0, "unchanged": 1, "error": 3} and data["valid"] is False
    assert "fields" not in data["rows"][0]


def test_import_commit_is_all_or_nothing(portal):
    bad = HEADER + "ET-1,Good Row,0911000001,Ops,,,\nET-2,Bad Row,nope,Ops,,,\n"
    resp = portal.post("/employees/import/commit", json={"csv": bad})
    assert resp.status_code == 422 and resp.json()["error_code"] == "IMPORT_INVALID"
    assert portal.get("/employees").json()["total"] == 0

    portal.employee(employee_number="ET-1", name="Old Name", phone="0911000001", department="Ops")
    good = HEADER + "ET-1,New Name,0911000001,Ops,,,\nET-2,Second Person,0911000002,Sales,DE000002,awash,2000000000002\n"
    resp = portal.post("/employees/import/commit", json={"csv": good})
    assert resp.status_code == 200 and resp.json()["summary"] == {"create": 1, "update": 1, "unchanged": 0, "error": 0}
    names = {e["employee_number"]: e for e in portal.get("/employees").json()["items"]}
    assert names["ET-1"]["name"] == "New Name"
    assert (names["ET-2"]["endod_id"], names["ET-2"]["payout_method"]) == ("DE000002", "awash")


@pytest.mark.parametrize("text, message", [
    ("", "csv"),
    ("name,phone\nA,0911000001\n", "missing employee_number"),
    (HEADER, "no employees"),
])
def test_import_refuses_unusable_files(portal, text, message):
    resp = portal.post("/employees/import/preview", json={"csv": text})
    assert resp.status_code in (400, 422) and message in resp.json()["error"]


def test_import_accepts_excel_style_files(portal):
    text = "\ufeffEmployee Number,Name,Phone,Department\r\nET-7,Ayana Bekele,0911000007,Ops\r\n"
    resp = portal.post("/employees/import/commit", json={"csv": text})
    assert resp.status_code == 200 and resp.json()["summary"]["create"] == 1


# --- CSV export ------------------------------------------------------------------------------------

def test_export_is_formula_injection_safe(portal):
    portal.employee(employee_number="ET-1", name="=1+2", department="+SUM(A1:A9)")
    portal.employee(employee_number="ET-2", name="@cmd", department="-2+3")
    portal.employee(employee_number="ET-3", name="  =HYPERLINK(1)", department="Plain")
    resp = portal.get("/employees/export")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"].startswith('attachment; filename="employees-2026-10-20.csv"')
    table = rows(resp.text)
    assert table[0] == ["employee_number", "name", "phone", "department", "endod_id", "payout_method",
                        "payout_account", "active"]
    by_number = {r[0]: r for r in table[1:]}
    assert by_number["ET-1"][1:4:2] == ["'=1+2", "'+SUM(A1:A9)"]
    assert by_number["ET-2"][1] == "'@cmd" and by_number["ET-2"][3] == "'-2+3"
    assert by_number["ET-3"][1] == "'=HYPERLINK(1)"
    # A phone number keeps its + but is quoted as text too.
    assert by_number["ET-1"][2].startswith("'+251")


def test_the_safe_cell_rule():
    from app.csvutil import safe_cell

    for dangerous in ("=1", "+1", "-1", "@a", "\t=1", "\r=1", " =1", "\uff1d1"):
        assert safe_cell(dangerous).startswith("'"), dangerous
    for fine in ("Abebe", "12.50", "", None, "a=b"):
        assert not safe_cell(fine).startswith("'"), fine

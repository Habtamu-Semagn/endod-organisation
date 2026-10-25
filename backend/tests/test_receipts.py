"""Receipt files: PDF/JPEG/PNG/WebP by their first bytes, at most 10 MB,
stored under ids per organisation, served with safe headers, audited."""

import hashlib
from pathlib import Path

import pytest
from conftest import JPEG, PDF, PNG, WEBP, events

from app import files


def upload(portal, data, filename="receipt.png", headers=None):
    return portal.post("/receipts", content=data,
                       headers={"X-Filename": filename, "Content-Type": "application/octet-stream", **(headers or {})})


@pytest.mark.parametrize("data, name, content_type, stored", [
    (PNG, "photo.PNG", "image/png", "photo.png"),
    (JPEG, "scan.jpeg", "image/jpeg", "scan.jpeg"),
    (PDF, "receipt.pdf", "application/pdf", "receipt.pdf"),
    (WEBP, "phone.webp", "image/webp", "phone.webp"),
    (PNG, "", "image/png", "receipt.png"),
    (PNG, "..\\..\\secret/../evil\".png", "image/png", "evil.png"),
    (JPEG, "%E1%8B%B0%E1%88%A8%E1%88%B0%E1%8A%9D.jpg", "image/jpeg", "\u12f0\u1228\u1230\u129d.jpg"),
])
def test_allowed_files_are_recognised_by_content(portal, data, name, content_type, stored):
    resp = upload(portal, data, name)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["content_type"], body["filename"], body["size"]) == (content_type, stored, len(data))
    assert body["sha256"] == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("data, name, status", [
    (b"<html><script>alert(1)</script></html>", "receipt.png", 415),
    (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "receipt.svg", 415),
    (b"GIF89a" + b"\x00" * 20, "receipt.gif", 415),
    (b"PK\x03\x04" + b"\x00" * 20, "receipt.pdf", 415),
    (b"", "receipt.png", 400),
    (PNG, "receipt.pdf", 400),  # the name says PDF, the content is PNG
])
def test_other_files_are_refused(portal, data, name, status):
    resp = upload(portal, data, name)
    assert resp.status_code == status, resp.text
    assert not list(Path(files.root()).rglob("*")) or all(p.is_dir() for p in Path(files.root()).rglob("*"))


def test_files_over_10_mb_are_refused(portal):
    big = PNG + b"\x00" * (10 * 1024 * 1024)
    resp = upload(portal, big)
    assert resp.status_code == 413 and resp.json()["error_code"] == "FILE_TOO_LARGE"
    assert all(p.is_dir() for p in Path(files.root()).rglob("*"))
    exactly = PNG + b"\x00" * (10 * 1024 * 1024 - len(PNG))
    assert upload(portal, exactly).status_code == 201


def test_a_declared_length_over_the_limit_is_refused_before_reading(portal):
    resp = upload(portal, PNG, headers={"Content-Length": str(11 * 1024 * 1024)})
    assert resp.status_code == 413


def test_files_are_stored_under_ids_per_organisation(portal):
    receipt_id = portal.receipt()
    path = files.path_for(portal.org_id, receipt_id)
    assert path.read_bytes() == PNG
    assert path.parent.name == portal.org_id and path.parent.parent == files.root()
    for bad in (("../x", receipt_id), (portal.org_id, "../../etc/passwd"), (portal.org_id, "A" * 32)):
        with pytest.raises(files.FileRejected):
            files.path_for(*bad)


def test_files_are_served_safely_and_every_view_is_audited(portal):
    png = portal.receipt(PNG, "photo.png")
    resp = portal.get(f"/receipts/{png}")
    assert resp.status_code == 200 and resp.content == PNG
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "private, no-store"
    assert resp.headers["content-disposition"].startswith('inline; filename="photo.png"')
    assert "default-src 'none'" in resp.headers["content-security-policy"]
    download = portal.get(f"/receipts/{png}?download=true")
    assert download.headers["content-disposition"].startswith('attachment; filename="photo.png"')

    pdf = portal.receipt(PDF, "receipt.pdf")
    resp = portal.get(f"/receipts/{pdf}")
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-security-policy"] == "frame-ancestors 'self'"
    views = events("receipt_viewed")
    assert len(views) == 3 and all(e[1] == "success" for e in views)
    assert len(events("receipt_uploaded")) == 2


def test_a_missing_file_on_disk_is_not_found(portal):
    receipt_id = portal.receipt()
    files.path_for(portal.org_id, receipt_id).unlink()
    assert portal.get(f"/receipts/{receipt_id}").status_code == 404


def test_unattached_uploads_are_limited(portal, monkeypatch):
    from app.api import receipts

    monkeypatch.setattr(receipts, "MAX_UNATTACHED_PER_DAY", 2)
    portal.receipt()
    portal.receipt()
    resp = upload(portal, PNG)
    assert resp.status_code == 429 and resp.json()["error_code"] == "TOO_MANY_UPLOADS"


def test_unattached_uploads_free_up_when_attached(portal, monkeypatch):
    from app.api import receipts

    emp = portal.employee()
    body = portal.claim_body(emp["id"])
    monkeypatch.setattr(receipts, "MAX_UNATTACHED_PER_DAY", 1)
    assert upload(portal, PNG).status_code == 429
    assert portal.post("/claims", json=body).status_code == 201
    assert upload(portal, PNG).status_code == 201

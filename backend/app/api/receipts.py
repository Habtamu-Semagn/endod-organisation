"""`/receipts`: receipt photos and scans.

The upload is the request body itself (the web app streams the chosen file),
checked by its first bytes and size as it is written (app.files); a claim then
refers to it by id. Files are served only to admins of the organisation that
uploaded them, with ``nosniff``, a safe disposition and no caching; every view
is in the audit log.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app import audit, files
from app.auth import Principal, current_admin
from app.db import iso, new_id, tenant_session, utcnow
from app.errors import ApiError
from app.models import Claim, ReceiptFile
from app.tenancy import not_found, owned

router = APIRouter(tags=["receipts"])

#: Uploads not yet attached to a claim, per organisation per day (disk abuse).
MAX_UNATTACHED_PER_DAY = 200


def receipt_payload(r: ReceiptFile) -> Dict[str, Any]:
    return {"id": r.id, "filename": r.filename, "content_type": r.content_type, "size": r.size,
            "sha256": r.sha256, "created_at": iso(r.created_at)}


@router.post("/receipts", status_code=201)
async def upload_receipt(request: Request,
                         x_filename: Optional[str] = Header(default=None, max_length=600),
                         content_length: Optional[int] = Header(default=None),
                         principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    if content_length is not None and content_length > files.MAX_FILE_BYTES:
        raise ApiError(413, "A receipt can be at most 10 MB.", "FILE_TOO_LARGE")
    org = principal.organisation_id

    def check() -> None:
        with tenant_session(principal.organisation_id) as session:
            attached = select(Claim.receipt_file_id).where(Claim.receipt_file_id.is_not(None))
            waiting = session.scalar(select(func.count()).select_from(ReceiptFile).where(
                ReceiptFile.organisation_id == org, ReceiptFile.id.not_in(attached),
                ReceiptFile.created_at > utcnow() - timedelta(days=1))) or 0
            if waiting >= MAX_UNATTACHED_PER_DAY:
                raise ApiError(429, "Too many receipts are waiting to be attached to a claim. "
                                    "Finish or discard those claims first.", "TOO_MANY_UPLOADS")

    await run_in_threadpool(check)
    file_id = new_id()
    try:
        size, sha256, content_type = await files.store_stream(request.stream(), org, file_id)
        filename = files.safe_filename(unquote(x_filename or ""), content_type)
    except files.FileRejected as exc:
        files.delete(org, file_id)
        code = {413: "FILE_TOO_LARGE", 415: "FILE_TYPE"}.get(exc.status_code, "FILE_REJECTED")
        raise ApiError(exc.status_code, str(exc), code) from exc

    def save() -> Dict[str, Any]:
        with tenant_session(principal.organisation_id) as session:
            row = ReceiptFile(id=file_id, organisation_id=org, filename=filename, content_type=content_type,
                              size=size, sha256=sha256, uploaded_by=principal.admin_id)
            session.add(row)
            audit.by(session, principal, audit.RECEIPT_UPLOADED, target_type="receipt", target_id=file_id,
                     target_name=filename, detail={"size": size, "content_type": content_type})
            return receipt_payload(row)

    try:
        return await run_in_threadpool(save)
    except Exception:
        files.delete(org, file_id)
        raise


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: str, download: bool = Query(default=False),
                principal: Principal = Depends(current_admin)):
    with tenant_session(principal.organisation_id) as session:
        row = owned(session, ReceiptFile, receipt_id, principal.organisation_id)
        try:
            path = files.path_for(row.organisation_id, row.id)
        except files.FileRejected as exc:
            raise not_found() from exc
        if not path.is_file():
            raise not_found()
        claim_id = session.scalar(select(Claim.id).where(Claim.receipt_file_id == row.id))
        audit.by(session, principal, audit.RECEIPT_VIEWED, target_type="receipt", target_id=row.id,
                 target_name=row.filename, detail={"claim_id": claim_id, "download": download})
        content_type, filename, sha256 = row.content_type, row.filename, row.sha256
    # FileResponse streams the file in chunks.
    return FileResponse(path, media_type=content_type, headers={
        "Content-Disposition": files.content_disposition(filename, inline=not download),
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "X-Sha256": sha256,
        "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
                                   "frame-ancestors 'self'" if content_type != "application/pdf"
                                   else "frame-ancestors 'self'",
    })

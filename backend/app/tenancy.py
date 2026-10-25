"""Tenant isolation: the one way the portal API loads a row by its id.

Every row is fetched together with the signed-in admin's organisation id
(``organisation_id = principal.organisation_id``); a row of another
organisation answers exactly like a row that does not exist (404, the same
message), so an admin cannot even learn that another organisation's id is real.
"""

from __future__ import annotations

import re
from typing import Type, TypeVar

from sqlalchemy import select

from app.errors import ApiError

T = TypeVar("T")

NOT_FOUND = "Not found."
_HEX_ID = re.compile(r"^[0-9a-f]{32}$")


def not_found() -> ApiError:
    return ApiError(404, NOT_FOUND, "NOT_FOUND")


def owned(session, model: Type[T], row_id: str, organisation_id: str, *, lock: bool = False) -> T:
    """The ``model`` row with ``row_id`` in ``organisation_id``, or 404."""
    if not isinstance(row_id, str) or not _HEX_ID.match(row_id) or not organisation_id:
        raise not_found()
    query = select(model).where(model.id == row_id, model.organisation_id == organisation_id)
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        raise not_found()
    return row

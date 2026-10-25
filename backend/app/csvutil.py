"""CSV in and out.

Every cell written is safe to open in Excel, LibreOffice or Google Sheets: a
cell that would start a formula (=, +, -, @, tab, carriage return, or those
after leading spaces) is prefixed with an apostrophe, so it is shown as text
and never evaluated (CSV / formula injection).
"""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable, List, Sequence, Tuple

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")

#: Largest CSV accepted for an import (characters) and rows in it.
MAX_IMPORT_CHARS = 1_000_000
MAX_IMPORT_ROWS = 5000


def safe_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    stripped = text.lstrip(" ")
    if stripped.startswith(_FORMULA_START):
        return "'" + text
    return text


def to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """CSV text (UTF-8 with a BOM, so Excel shows Amharic names right; CRLF line ends)."""
    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([safe_cell(h) for h in header])
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    return "\ufeff" + out.getvalue()


def parse(text: str) -> List[Tuple[int, dict]]:
    """Rows of an uploaded CSV as (line number, dict keyed by the lower-cased,
    trimmed header); blank lines are skipped.

    Raises ValueError for an empty, oversized or headerless file."""
    if len(text) > MAX_IMPORT_CHARS:
        raise ValueError("The file is too large (at most 1 MB).")
    text = text.lstrip("\ufeff")
    if not text.strip():
        raise ValueError("The file is empty.")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError("The file is empty.") from exc
    keys = [h.strip().lower().replace(" ", "_") for h in header]
    rows = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue
        if len(rows) >= MAX_IMPORT_ROWS:
            raise ValueError(f"At most {MAX_IMPORT_ROWS} rows can be imported at once.")
        rows.append((reader.line_num,
                     {key: (values[i].strip() if i < len(values) else "") for i, key in enumerate(keys) if key}))
    return rows

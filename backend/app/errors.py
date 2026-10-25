"""One error shape everywhere: ``{"error": "...", "error_code": "..."}``."""

from __future__ import annotations

from typing import Optional


class ApiError(Exception):
    def __init__(self, status_code: int, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code or f"HTTP_{status_code}"

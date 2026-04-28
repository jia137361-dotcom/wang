"""API key authentication dependency.

Protects API routes by requiring an X-API-Key header that matches the
configured API_KEY environment variable.  Set API_KEY to a blank string
to disable authentication (e.g. during local development).
"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Annotated[str | None, Security(API_KEY_HEADER)] = None) -> None:
    settings = get_settings()
    expected = (settings.api_key or "").strip()
    if not expected:
        return
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

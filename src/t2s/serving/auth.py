"""Authentication middleware and API Key dependency."""

import os
from typing import Optional
from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(x_api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    expected_key = os.getenv("API_KEY", "demo-secret-key")

    # If API_KEY environment variable is set to empty or 'disabled', skip verification
    if os.getenv("DISABLE_AUTH", "false").lower() == "true":
        return "unauthenticated"

    if not x_api_key or x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
    return x_api_key

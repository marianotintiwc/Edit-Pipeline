from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, Header, HTTPException

from api.app_config import AppConfig, get_app_config


def _anonymous_user() -> Dict[str, Any]:
    return {
        "user_id": "anonymous",
        "email": "anonymous@local",
        "auth_provider": "disabled",
    }


def get_current_user(
    authorization: str | None = Header(default=None),
    config: AppConfig = Depends(get_app_config),
) -> Dict[str, Any]:
    """Minimal auth boundary.

    When AUTH_ENABLED=false we use a static local user to keep dev UX simple.
    When AUTH_ENABLED=true a bearer token is required.
    """
    if not config.auth_enabled:
        return _anonymous_user()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    # Placeholder validation path. This keeps route contracts intact while
    # allowing a future Cognito/JWT verifier to be wired in one place.
    return {
        "user_id": "auth-user",
        "email": "auth-user@example.com",
        "auth_provider": "bearer",
        "token_fingerprint": token[:12],
    }

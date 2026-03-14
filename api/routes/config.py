from __future__ import annotations

from fastapi import APIRouter

from api.app_config import get_app_config

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/options")
def get_config_options() -> dict[str, object]:
    config = get_app_config()
    return {
        "api_name": config.api_name,
        "cors_origins": config.cors_origins,
        "auth_enabled": config.auth_enabled,
        "aws_region": config.aws_region,
    }

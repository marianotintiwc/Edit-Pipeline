from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class AppConfig:
    api_name: str
    cors_origins: list[str]
    runpod_api_key: str | None
    runpod_endpoint_id: str | None
    runpod_timeout_seconds: int
    aws_region: str
    runs_table_name: str | None
    runs_store_path: str | None
    batch_store_path: str | None
    auth_enabled: bool
    cognito_region: str | None
    cognito_user_pool_id: str | None
    cognito_app_client_id: str | None

    @property
    def cognito_issuer(self) -> str | None:
        if not self.cognito_region or not self.cognito_user_pool_id:
            return None
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com/"
            f"{self.cognito_user_pool_id}"
        )


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    cors_origins = _split_csv(os.environ.get("API_CORS_ORIGINS")) or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    auth_enabled = os.environ.get("AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}

    return AppConfig(
        api_name=os.environ.get("API_NAME", "UGC Visual UI API"),
        cors_origins=cors_origins,
        runpod_api_key=os.environ.get("RUNPOD_API_KEY"),
        runpod_endpoint_id=os.environ.get("RUNPOD_ENDPOINT_ID"),
        runpod_timeout_seconds=int(os.environ.get("RUNPOD_TIMEOUT_SECONDS", "600")),
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        runs_table_name=os.environ.get("RUNS_TABLE_NAME"),
        runs_store_path=os.environ.get("RUNS_STORE_PATH"),
        batch_store_path=os.environ.get("BATCH_STORE_PATH"),
        auth_enabled=auth_enabled,
        cognito_region=os.environ.get("COGNITO_REGION") or os.environ.get("AWS_REGION"),
        cognito_user_pool_id=os.environ.get("COGNITO_USER_POOL_ID"),
        cognito_app_client_id=os.environ.get("COGNITO_APP_CLIENT_ID"),
    )

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    api_name: str
    cors_origins: list[str]
    runpod_api_key: str | None
    runpod_endpoint_id: str | None
    runpod_timeout_seconds: int
    runpod_status_timeout_seconds: int
    runpod_submit_max_retries: int
    runpod_status_max_retries: int
    runpod_retry_backoff_seconds: float
    aws_region: str
    runs_table_name: str | None
    runs_store_path: str | None
    batch_store_path: str | None
    idempotency_store_path: str | None
    idempotency_ttl_seconds: int
    batch_refresh_max_rows: int
    batch_refresh_max_workers: int
    hardening_enable_job_idempotency: bool
    hardening_enable_batch_idempotency: bool
    hardening_enable_batch_refresh_query: bool
    hardening_enable_concurrent_status_refresh: bool
    hardening_enable_runpod_retry_policy: bool
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

    auth_enabled = _env_bool("AUTH_ENABLED", False)

    return AppConfig(
        api_name=os.environ.get("API_NAME", "UGC Visual UI API"),
        cors_origins=cors_origins,
        runpod_api_key=os.environ.get("RUNPOD_API_KEY"),
        runpod_endpoint_id=os.environ.get("RUNPOD_ENDPOINT_ID"),
        runpod_timeout_seconds=int(os.environ.get("RUNPOD_TIMEOUT_SECONDS", "600")),
        runpod_status_timeout_seconds=int(
            os.environ.get("RUNPOD_STATUS_TIMEOUT_SECONDS", "15")
        ),
        runpod_submit_max_retries=int(os.environ.get("RUNPOD_SUBMIT_MAX_RETRIES", "3")),
        runpod_status_max_retries=int(os.environ.get("RUNPOD_STATUS_MAX_RETRIES", "2")),
        runpod_retry_backoff_seconds=float(
            os.environ.get("RUNPOD_RETRY_BACKOFF_SECONDS", "0.5")
        ),
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        runs_table_name=os.environ.get("RUNS_TABLE_NAME"),
        runs_store_path=os.environ.get("RUNS_STORE_PATH"),
        batch_store_path=os.environ.get("BATCH_STORE_PATH"),
        idempotency_store_path=os.environ.get("IDEMPOTENCY_STORE_PATH"),
        idempotency_ttl_seconds=int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "86400")),
        batch_refresh_max_rows=int(os.environ.get("BATCH_REFRESH_MAX_ROWS", "50")),
        batch_refresh_max_workers=int(os.environ.get("BATCH_REFRESH_MAX_WORKERS", "8")),
        hardening_enable_job_idempotency=_env_bool("ENABLE_HARDENING_JOB_IDEMPOTENCY", True),
        hardening_enable_batch_idempotency=_env_bool("ENABLE_HARDENING_BATCH_IDEMPOTENCY", True),
        hardening_enable_batch_refresh_query=_env_bool("ENABLE_HARDENING_BATCH_REFRESH_QUERY", True),
        hardening_enable_concurrent_status_refresh=_env_bool(
            "ENABLE_HARDENING_CONCURRENT_STATUS_REFRESH",
            True,
        ),
        hardening_enable_runpod_retry_policy=_env_bool("ENABLE_HARDENING_RUNPOD_RETRY_POLICY", True),
        auth_enabled=auth_enabled,
        cognito_region=os.environ.get("COGNITO_REGION") or os.environ.get("AWS_REGION"),
        cognito_user_pool_id=os.environ.get("COGNITO_USER_POOL_ID"),
        cognito_app_client_id=os.environ.get("COGNITO_APP_CLIENT_ID"),
    )

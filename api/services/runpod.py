from __future__ import annotations

import os
import random
import time
from typing import Any, Dict

from api.app_config import get_app_config
from ugc_client import UGCPipelineClient


class RunPodService:
    def __init__(
        self,
        client: UGCPipelineClient,
        *,
        submit_max_retries: int,
        status_max_retries: int,
        retry_backoff_seconds: float,
        status_timeout_seconds: int,
    ) -> None:
        self._client = client
        self._submit_max_retries = submit_max_retries
        self._status_max_retries = status_max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._status_timeout_seconds = status_timeout_seconds

    def _sleep_with_jitter(self, attempt: int) -> None:
        base_sleep = self._retry_backoff_seconds * (2 ** max(attempt, 0))
        jitter = random.uniform(0, self._retry_backoff_seconds)
        time.sleep(base_sleep + jitter)

    def submit_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        for attempt in range(self._submit_max_retries + 1):
            try:
                result = self._client.submit_job_async(payload)
                job_id = result.get("job_id") or result.get("id")
                return {
                    "job_id": job_id,
                    "status": result.get("status", "IN_QUEUE"),
                }
            except Exception as exc:
                if attempt >= self._submit_max_retries:
                    raise RuntimeError("RUNPOD_UNAVAILABLE: unable to submit job") from exc
                self._sleep_with_jitter(attempt)
        raise RuntimeError("RUNPOD_UNAVAILABLE: unable to submit job")

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        for attempt in range(self._status_max_retries + 1):
            try:
                return self._client.get_job_status(
                    job_id,
                    timeout_seconds=self._status_timeout_seconds,
                )
            except Exception as exc:
                if attempt >= self._status_max_retries:
                    raise RuntimeError("RUNPOD_UNAVAILABLE: unable to fetch job status") from exc
                self._sleep_with_jitter(attempt)
        raise RuntimeError("RUNPOD_UNAVAILABLE: unable to fetch job status")


def get_runpod_service() -> RunPodService:
    config = get_app_config()
    api_key = config.runpod_api_key or os.environ.get("RUNPOD_API_KEY")
    endpoint_id = config.runpod_endpoint_id or os.environ.get("RUNPOD_ENDPOINT_ID")

    if not api_key or not endpoint_id:
        raise RuntimeError("RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID are required")

    retry_enabled = config.hardening_enable_runpod_retry_policy
    submit_retries = config.runpod_submit_max_retries if retry_enabled else 0
    status_retries = config.runpod_status_max_retries if retry_enabled else 0
    retry_backoff = config.runpod_retry_backoff_seconds if retry_enabled else 0.0
    status_timeout = (
        config.runpod_status_timeout_seconds if retry_enabled else config.runpod_timeout_seconds
    )

    client = UGCPipelineClient(
        api_key=api_key,
        endpoint_id=endpoint_id,
        timeout=config.runpod_timeout_seconds,
        max_retries=submit_retries,
        retry_backoff_seconds=retry_backoff,
    )
    return RunPodService(
        client,
        submit_max_retries=submit_retries,
        status_max_retries=status_retries,
        retry_backoff_seconds=retry_backoff,
        status_timeout_seconds=status_timeout,
    )

from __future__ import annotations

import os
from typing import Any, Dict

from api.app_config import get_app_config
from ugc_client import UGCPipelineClient


class RunPodService:
    def __init__(self, client: UGCPipelineClient) -> None:
        self._client = client

    def submit_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self._client.submit_job_async(payload)
        except Exception as exc:
            raise RuntimeError("RUNPOD_UNAVAILABLE: unable to submit job") from exc
        job_id = result.get("job_id") or result.get("id")
        return {
            "job_id": job_id,
            "status": result.get("status", "IN_QUEUE"),
        }

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        try:
            return self._client.get_job_status(job_id)
        except Exception as exc:
            raise RuntimeError("RUNPOD_UNAVAILABLE: unable to fetch job status") from exc


def get_runpod_service() -> RunPodService:
    config = get_app_config()
    api_key = config.runpod_api_key or os.environ.get("RUNPOD_API_KEY")
    endpoint_id = config.runpod_endpoint_id or os.environ.get("RUNPOD_ENDPOINT_ID")

    if not api_key or not endpoint_id:
        raise RuntimeError("RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID are required")

    client = UGCPipelineClient(
        api_key=api_key,
        endpoint_id=endpoint_id,
        timeout=config.runpod_timeout_seconds,
    )
    return RunPodService(client)

from __future__ import annotations

from typing import Any, Dict, List, Protocol


class RunsStoreProtocol(Protocol):
    def create_run(
        self,
        *,
        user_id: str,
        preset_name: str | None,
        payload: Dict[str, Any],
        runpod_job_id: str,
        initial_status: str,
    ) -> Dict[str, Any]:
        ...

    def update_job_status(self, *, job_id: str, status_payload: Dict[str, Any]) -> Dict[str, Any] | None:
        ...

    def list_runs(self, *, user_id: str) -> List[Dict[str, Any]]:
        ...

    def get_run_by_job_id(self, *, job_id: str, user_id: str) -> Dict[str, Any]:
        ...

    def get_run(self, *, run_id: str, user_id: str) -> Dict[str, Any]:
        ...


class BatchStoreProtocol(Protocol):
    def next_batch_id(self) -> str:
        ...

    def save_batch(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def get_batch(self, *, batch_id: str, user_id: str) -> Dict[str, Any]:
        ...

    def update_batch(self, *, batch_id: str, user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def list_batches(self, *, user_id: str) -> List[Dict[str, Any]]:
        ...

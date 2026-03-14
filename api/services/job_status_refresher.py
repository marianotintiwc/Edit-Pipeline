from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any, Dict, List

from api.services.runpod import RunPodService
from api.services.runs_store import RunsStore


def map_job_status_to_batch_row(status: str | None) -> str | None:
    if not status:
        return None
    normalized = status.upper()
    if normalized == "COMPLETED":
        return "completed"
    if normalized == "FAILED":
        return "failed"
    if normalized == "IN_PROGRESS":
        return "in_progress"
    if normalized == "IN_QUEUE":
        return "queued"
    return status.lower()


def refresh_batch_rows_status(
    *,
    rows: List[Dict[str, Any]],
    runpod_service: RunPodService,
    runs_store: RunsStore,
    max_workers: int,
    max_rows_to_refresh: int,
) -> tuple[List[Dict[str, Any]], bool]:
    updated_rows = [deepcopy(row) for row in rows]
    candidates = [
        (idx, row["job_id"])
        for idx, row in enumerate(updated_rows)
        if row.get("job_id") and row.get("status") in {"submitted", "queued", "in_progress"}
    ][: max(max_rows_to_refresh, 0)]
    if not candidates:
        return updated_rows, False

    changed = False
    worker_count = max(1, min(max_workers, len(candidates)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_by_idx = {
            executor.submit(runpod_service.get_job_status, job_id): (idx, job_id)
            for idx, job_id in candidates
        }
        for future in as_completed(future_by_idx):
            idx, job_id = future_by_idx[future]
            try:
                status_payload = future.result()
                runs_store.update_job_status(job_id=job_id, status_payload=status_payload)
                next_status = map_job_status_to_batch_row(status_payload.get("status"))
                if next_status and next_status != updated_rows[idx].get("status"):
                    updated_rows[idx]["status"] = next_status
                    changed = True
            except RuntimeError as exc:
                updated_rows[idx].setdefault("warnings", [])
                updated_rows[idx]["warnings"] = [
                    *updated_rows[idx]["warnings"],
                    f"status_refresh_error:{exc}",
                ]
    return updated_rows, changed

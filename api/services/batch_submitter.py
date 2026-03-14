from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from api.services.runpod import RunPodService
from api.services.runs_store import RunsStore


def submit_batch_rows(
    *,
    batch: Dict[str, Any],
    user_id: str,
    runpod_service: RunPodService,
    runs_store: RunsStore,
    recipe_input: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if batch.get("status") == "completed":
        return deepcopy(batch)

    submitted_rows = 0
    updated_rows = []

    def deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(base)
        for key, value in overrides.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    for row in batch.get("rows", []):
        next_row = deepcopy(row)
        if next_row.get("status") not in {"ready", "failed"}:
            updated_rows.append(next_row)
            continue

        row_input = deepcopy(next_row["input"])
        if recipe_input:
            row_input = deep_merge(recipe_input, row_input)
            next_row["input"] = row_input
        payload = {"input": row_input}
        try:
            submit_result = runpod_service.submit_job(payload)
            run_record = runs_store.create_run(
                user_id=user_id,
                preset_name=next_row["input"].get("edit_preset"),
                payload=next_row["input"],
                runpod_job_id=submit_result["job_id"],
                initial_status=submit_result["status"],
            )
            next_row["status"] = "submitted"
            next_row["run_id"] = run_record["run_id"]
            next_row["job_id"] = submit_result["job_id"]
            next_row["errors"] = []
            submitted_rows += 1
        except Exception as exc:
            next_row["status"] = "failed"
            next_row.setdefault("errors", [])
            next_row["errors"] = [*next_row["errors"], str(exc)]
        updated_rows.append(next_row)

    blocked_rows = sum(1 for row in updated_rows if row.get("status") == "blocked_by_validation")
    failed_rows = sum(1 for row in updated_rows if row.get("status") == "failed")
    total_submitted_rows = sum(
        1
        for row in updated_rows
        if row.get("status") in {"submitted", "queued", "in_progress", "completed"}
    )
    if total_submitted_rows and (blocked_rows or failed_rows):
        batch_status = "partial_success"
    elif total_submitted_rows:
        batch_status = "completed"
    elif failed_rows:
        batch_status = "failed"
    else:
        batch_status = "failed"

    updated_batch = deepcopy(batch)
    updated_batch["rows"] = updated_rows
    updated_batch["submitted_rows"] = total_submitted_rows
    updated_batch["status"] = batch_status
    return updated_batch

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, File, Form, Header, HTTPException, Query, UploadFile
from api.auth import get_current_user
from api.app_config import AppConfig, get_app_config
from api.errors import error_response
from api.services.batch_csv import parse_batch_csv
from api.services.idempotency_store import IdempotencyStore, get_idempotency_store
from api.services.job_status_refresher import map_job_status_to_batch_row, refresh_batch_rows_status
from api.services.batch_store import BatchStore, get_batch_store
from api.services.batch_submitter import submit_batch_rows
from api.services.runpod import RunPodService, get_runpod_service
from api.services.runs_store import RunsStore, get_runs_store


router = APIRouter(prefix="/batches", tags=["batches"])


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _next_batch_id(batch_store: BatchStore) -> str:
    if hasattr(batch_store, "next_batch_id"):
        return batch_store.next_batch_id()
    records = getattr(batch_store, "records", {})
    return f"batch-{len(records) + 1}"


def _refresh_batch_progress(
    *,
    batch: Dict[str, Any],
    config: AppConfig,
    batch_store: BatchStore,
    user_id: str,
    runpod_service: RunPodService,
    runs_store: RunsStore,
) -> Dict[str, Any]:
    if config.hardening_enable_concurrent_status_refresh:
        updated_rows, changed = refresh_batch_rows_status(
            rows=batch.get("rows", []),
            runpod_service=runpod_service,
            runs_store=runs_store,
            max_workers=config.batch_refresh_max_workers,
            max_rows_to_refresh=config.batch_refresh_max_rows,
        )
    else:
        changed = False
        updated_rows = []
        for row in batch.get("rows", []):
            next_row = dict(row)
            job_id = next_row.get("job_id")
            if job_id and next_row.get("status") in {"submitted", "queued", "in_progress"}:
                status_payload = runpod_service.get_job_status(job_id)
                runs_store.update_job_status(job_id=job_id, status_payload=status_payload)
                next_status = map_job_status_to_batch_row(status_payload.get("status"))
                if next_status and next_status != next_row.get("status"):
                    next_row["status"] = next_status
                    changed = True
            updated_rows.append(next_row)

    if not changed:
        return batch

    completed_rows = sum(1 for row in updated_rows if row.get("status") == "completed")
    failed_rows = sum(1 for row in updated_rows if row.get("status") == "failed")
    active_rows = sum(1 for row in updated_rows if row.get("status") in {"submitted", "queued", "in_progress"})

    patch: Dict[str, Any] = {"rows": updated_rows}
    if active_rows:
        patch["status"] = "in_progress"
    elif failed_rows and completed_rows:
        patch["status"] = "partial_success"
    elif failed_rows:
        patch["status"] = "failed"
    elif completed_rows:
        patch["status"] = "completed"

    return batch_store.update_batch(batch_id=batch["batch_id"], user_id=user_id, patch=patch)


@router.get("")
def list_batches(
    current_user: Dict[str, Any] = Depends(get_current_user),
    batch_store: BatchStore = Depends(get_batch_store),
) -> Dict[str, Any]:
    items = []
    for batch in batch_store.list_batches(user_id=current_user["user_id"]):
        items.append(
            {
                "batch_id": batch["batch_id"],
                "filename": batch["filename"],
                "status": batch["status"],
                "total_rows": batch["total_rows"],
                "valid_rows": batch["valid_rows"],
                "invalid_rows": batch["invalid_rows"],
                "submitted_rows": batch.get("submitted_rows", 0),
                "updated_at": batch.get("updated_at"),
                "created_at": batch.get("created_at"),
            }
        )
    return {"items": items}


@router.post("")
async def create_batch(
    file: UploadFile = File(...),
    mapping: str | None = Form(default=None),
    recipe_input: str | None = Form(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    batch_store: BatchStore = Depends(get_batch_store),
) -> Dict[str, Any]:
    if file.filename and not file.filename.lower().endswith(".csv"):
        return error_response(
            status_code=400,
            error_code="INVALID_BATCH_FILE",
            message="Batch upload must be a .csv file",
            details=["Batch upload must be a .csv file"],
        )

    content = await file.read()
    parsed_mapping: Dict[str, str] | None = None
    parsed_recipe_input: Dict[str, Any] | None = None
    if mapping:
        try:
            parsed_mapping = json.loads(mapping)
            if not isinstance(parsed_mapping, dict):
                raise ValueError("mapping must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            return error_response(
                status_code=400,
                error_code="INVALID_BATCH_MAPPING",
                message="Invalid mapping payload",
                details=[str(exc)],
            )
    if recipe_input:
        try:
            parsed_recipe_input = json.loads(recipe_input)
            if not isinstance(parsed_recipe_input, dict):
                raise ValueError("recipe_input must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            return error_response(
                status_code=400,
                error_code="INVALID_RECIPE_INPUT",
                message="Invalid recipe input payload",
                details=[str(exc)],
            )

    try:
        total_rows, rows = parse_batch_csv(
            content,
            mapping=parsed_mapping,
            recipe_input=parsed_recipe_input,
        )
    except UnicodeDecodeError as exc:
        return error_response(
            status_code=400,
            error_code="INVALID_CSV_ENCODING",
            message="Batch upload must be a UTF-8 encoded CSV file",
            details=["Batch upload must be a UTF-8 encoded CSV file"],
        )
    except ValueError as exc:
        return error_response(
            status_code=400,
            error_code="INVALID_CSV",
            message="Invalid CSV data",
            details=[str(exc)],
        )
    valid_rows = sum(1 for row in rows if row["status"] == "ready")
    invalid_rows = total_rows - valid_rows
    timestamp = _now_iso()
    batch = {
        "batch_id": _next_batch_id(batch_store),
        "filename": file.filename or "batch.csv",
        "status": "ready" if valid_rows > 0 else "validation_failed",
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "rows": rows,
        "created_at": timestamp,
        "updated_at": timestamp,
        "user_id": current_user["user_id"],
        "mapping": parsed_mapping,
        "recipe_input": parsed_recipe_input,
    }
    return batch_store.save_batch(batch)


@router.get("/{batch_id}")
def get_batch(
    batch_id: str,
    refresh: bool = Query(default=True),
    current_user: Dict[str, Any] = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
    batch_store: BatchStore = Depends(get_batch_store),
    runpod_service: RunPodService = Depends(get_runpod_service),
    runs_store: RunsStore = Depends(get_runs_store),
) -> Dict[str, Any]:
    try:
        batch = batch_store.get_batch(batch_id=batch_id, user_id=current_user["user_id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found") from exc
    if config.hardening_enable_batch_refresh_query and not refresh:
        return batch
    return _refresh_batch_progress(
        batch=batch,
        config=config,
        batch_store=batch_store,
        user_id=current_user["user_id"],
        runpod_service=runpod_service,
        runs_store=runs_store,
    )


@router.post("/{batch_id}/cancel")
def cancel_batch(
    batch_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    batch_store: BatchStore = Depends(get_batch_store),
    runpod_service: RunPodService = Depends(get_runpod_service),
    runs_store: RunsStore = Depends(get_runs_store),
) -> Dict[str, Any]:
    try:
        batch = batch_store.get_batch(batch_id=batch_id, user_id=current_user["user_id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found") from exc

    active_statuses = {"submitted", "queued", "in_progress"}
    cancelled_ok: list[str] = []
    already_terminal: list[str] = []
    failed_cancel: list[str] = []

    updated_rows = []
    for row in batch.get("rows", []):
        next_row = dict(row)
        job_id = next_row.get("job_id")
        if next_row.get("status") not in active_statuses:
            if job_id:
                already_terminal.append(job_id)
            updated_rows.append(next_row)
            continue

        if not job_id:
            updated_rows.append(next_row)
            continue

        try:
            runpod_service.cancel_job(job_id)
            runs_store.update_job_status(
                job_id=job_id,
                status_payload={"status": "CANCELLED", "stage": "cancelled"},
            )
            next_row["status"] = "cancelled"
            cancelled_ok.append(job_id)
        except RuntimeError:
            failed_cancel.append(job_id)
        updated_rows.append(next_row)

    if cancelled_ok or failed_cancel:
        batch_store.update_batch(
            batch_id=batch_id,
            user_id=current_user["user_id"],
            patch={"rows": updated_rows},
        )

    return {
        "batch_id": batch_id,
        "cancelled_ok": cancelled_ok,
        "already_terminal": already_terminal,
        "failed_cancel": failed_cancel,
    }


@router.post("/{batch_id}/submit")
def submit_batch(
    batch_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    config: AppConfig = Depends(get_app_config),
    current_user: Dict[str, Any] = Depends(get_current_user),
    batch_store: BatchStore = Depends(get_batch_store),
    runpod_service: RunPodService = Depends(get_runpod_service),
    runs_store: RunsStore = Depends(get_runs_store),
    idempotency_store: IdempotencyStore = Depends(get_idempotency_store),
) -> Dict[str, Any]:
    try:
        batch = batch_store.get_batch(batch_id=batch_id, user_id=current_user["user_id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found") from exc

    recipe_input = payload.get("recipe_input") if isinstance(payload, dict) else None
    if recipe_input is None:
        recipe_input = batch.get("recipe_input")
    if recipe_input is not None and not isinstance(recipe_input, dict):
        return error_response(
            status_code=400,
            error_code="INVALID_RECIPE_INPUT",
            message="recipe_input must be an object when provided",
            details=["recipe_input must be an object when provided"],
        )
    request_payload = {"batch_id": batch_id, "payload": payload}
    scope = "batches:submit"
    idempotency_enabled = config.hardening_enable_batch_idempotency
    if idempotency_enabled and idempotency_key:
        cached = idempotency_store.get(
            user_id=current_user["user_id"],
            scope=scope,
            idempotency_key=idempotency_key,
        )
        if cached:
            if not idempotency_store.request_hash_matches(record=cached, request_payload=request_payload):
                return error_response(
                    status_code=409,
                    error_code="IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                    message="Idempotency key already used with a different payload",
                )
            return cached["response_payload"]

    submitted_batch = submit_batch_rows(
        batch=batch,
        user_id=current_user["user_id"],
        runpod_service=runpod_service,
        runs_store=runs_store,
        recipe_input=recipe_input,
    )
    response_payload = batch_store.update_batch(
        batch_id=batch_id,
        user_id=current_user["user_id"],
        patch=submitted_batch,
    )
    if idempotency_enabled and idempotency_key:
        idempotency_store.put(
            user_id=current_user["user_id"],
            scope=scope,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            response_payload=response_payload,
        )
    return response_payload

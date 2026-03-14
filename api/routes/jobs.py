from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.errors import error_response
from api.services.runpod import RunPodService, get_runpod_service
from api.services.runs_store import RunsStore, get_runs_store
from ugc_pipeline.planning import build_execution_plan

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _extract_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("input"), dict):
        raise ValueError("payload.input must be an object")
    return payload["input"]


def _build_plan_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        job_input = _extract_input(payload)
        plan = build_execution_plan(job_input)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    return {"job_input": job_input, "plan": plan.to_dict(), "normalized_input": plan.normalized_input}


@router.post("/preview")
def preview_job(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    del current_user
    try:
        preview = _build_plan_response(payload)
    except ValueError as exc:
        return error_response(
            status_code=400,
            error_code="VALIDATION_ERROR",
            message="Invalid job payload",
            details=[str(exc)],
        )
    return preview["plan"]


@router.post("")
def submit_job(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    service: RunPodService = Depends(get_runpod_service),
    runs_store: RunsStore = Depends(get_runs_store),
) -> Dict[str, Any]:
    try:
        preview = _build_plan_response(payload)
    except ValueError as exc:
        return error_response(
            status_code=400,
            error_code="VALIDATION_ERROR",
            message="Invalid job payload",
            details=[str(exc)],
        )
    normalized_input = preview["normalized_input"]
    plan = preview["plan"]
    if plan["plan_only"]:
        response = {
            "status": "PLAN_ONLY",
            "preview": plan,
        }
        if plan["warnings"]:
            response["warnings"] = plan["warnings"]
        return response
    try:
        result = service.submit_job({"input": normalized_input})
    except RuntimeError as exc:
        return error_response(
            status_code=503,
            error_code="RUNPOD_UNAVAILABLE",
            message="RunPod submission failed",
            details=[str(exc)],
        )
    run_record = runs_store.create_run(
        user_id=current_user["user_id"],
        preset_name=normalized_input.get("edit_preset"),
        payload=normalized_input,
        runpod_job_id=result["job_id"],
        initial_status=result["status"],
    )
    response = {
        "run_id": run_record["run_id"],
        "job_id": result["job_id"],
        "status": result["status"],
    }
    if plan["warnings"]:
        response["warnings"] = plan["warnings"]
    return response


@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    runs_store: RunsStore = Depends(get_runs_store),
    service: RunPodService = Depends(get_runpod_service),
) -> Dict[str, Any]:
    try:
        runs_store.get_run_by_job_id(job_id=job_id, user_id=current_user["user_id"])
    except KeyError:
        return error_response(
            status_code=404,
            error_code="JOB_NOT_FOUND",
            message=f"Job '{job_id}' not found",
        )

    try:
        result = service.get_job_status(job_id)
    except RuntimeError as exc:
        return error_response(
            status_code=503,
            error_code="RUNPOD_UNAVAILABLE",
            message="Could not fetch job status from RunPod",
            details=[str(exc)],
        )
    try:
        runs_store.update_job_status(job_id=job_id, status_payload=result)
    except KeyError:
        pass
    return result

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.services.runpod import RunPodService, get_runpod_service
from api.services.runs_store import RunsStore, get_runs_store

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
def list_runs(
    current_user: Dict[str, Any] = Depends(get_current_user),
    runs_store: RunsStore = Depends(get_runs_store),
) -> Dict[str, Any]:
    return {"items": runs_store.list_runs(user_id=current_user["user_id"])}


@router.get("/{run_id}")
def get_run(
    run_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    runs_store: RunsStore = Depends(get_runs_store),
    runpod_service: RunPodService = Depends(get_runpod_service),
) -> Dict[str, Any]:
    try:
        run = runs_store.get_run(run_id=run_id, user_id=current_user["user_id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found") from exc

    job_id = run.get("job_id")
    if isinstance(job_id, str) and job_id:
        try:
            status_payload = runpod_service.get_job_status(job_id)
            updated = runs_store.update_job_status(job_id=job_id, status_payload=status_payload)
            if updated:
                return updated
        except RuntimeError:
            # Return last persisted snapshot when provider is temporarily unavailable.
            return run
    return run

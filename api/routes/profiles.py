from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from api.auth import get_current_user
from api.errors import error_response
from api.services.profiles_store import (
    MELI_DEFAULT_PROFILE_ID,
    ProfilesStore,
    get_profiles_store,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("")
def list_profiles(
    current_user: Dict[str, Any] = Depends(get_current_user),
    profiles_store: ProfilesStore = Depends(get_profiles_store),
) -> Dict[str, Any]:
    items = profiles_store.list_profiles(user_id=current_user["user_id"])
    return {"items": items}


@router.post("")
def create_profile(
    payload: Dict[str, Any] = Body(default_factory=dict),
    current_user: Dict[str, Any] = Depends(get_current_user),
    profiles_store: ProfilesStore = Depends(get_profiles_store),
) -> Dict[str, Any]:
    name = payload.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        return error_response(
            status_code=400,
            error_code="INVALID_PROFILE",
            message="Profile name is required",
            details=["name must be a non-empty string"],
        )
    input_payload = payload.get("input")
    if input_payload is None:
        input_payload = {}
    if not isinstance(input_payload, dict):
        return error_response(
            status_code=400,
            error_code="INVALID_PROFILE",
            message="Profile input must be an object",
            details=["input must be a JSON object (Partial<JobInput>)"],
        )
    is_meli = bool(payload.get("is_meli", False))
    try:
        return profiles_store.create_profile(
            user_id=current_user["user_id"],
            name=name.strip(),
            input_payload=input_payload,
            is_meli=is_meli,
        )
    except ValueError as exc:
        return error_response(
            status_code=400,
            error_code="INVALID_PROFILE_INPUT",
            message="Profile input validation failed",
            details=[str(exc)],
        )


@router.get("/{profile_id}")
def get_profile(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    profiles_store: ProfilesStore = Depends(get_profiles_store),
) -> Dict[str, Any]:
    if profile_id == MELI_DEFAULT_PROFILE_ID:
        meli = profiles_store.get_meli_default()
        meli["user_id"] = current_user["user_id"]
        return meli
    try:
        return profiles_store.get_profile(profile_id=profile_id, user_id=current_user["user_id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found") from exc


@router.put("/{profile_id}")
def update_profile(
    profile_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
    current_user: Dict[str, Any] = Depends(get_current_user),
    profiles_store: ProfilesStore = Depends(get_profiles_store),
) -> Dict[str, Any]:
    if profile_id == MELI_DEFAULT_PROFILE_ID:
        raise HTTPException(status_code=400, detail="Cannot modify built-in MELI profile")
    try:
        return profiles_store.update_profile(
            profile_id=profile_id,
            user_id=current_user["user_id"],
            name=payload.get("name"),
            input_payload=payload.get("input"),
            is_meli=payload.get("is_meli"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found") from exc
    except ValueError as exc:
        return error_response(
            status_code=400,
            error_code="INVALID_PROFILE_INPUT",
            message="Profile input validation failed",
            details=[str(exc)],
        )


@router.delete("/{profile_id}")
def delete_profile(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    profiles_store: ProfilesStore = Depends(get_profiles_store),
) -> Dict[str, Any]:
    if profile_id == MELI_DEFAULT_PROFILE_ID:
        raise HTTPException(status_code=400, detail="Cannot delete built-in MELI profile")
    try:
        profiles_store.delete_profile(profile_id=profile_id, user_id=current_user["user_id"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found") from exc
    return {"deleted": profile_id}

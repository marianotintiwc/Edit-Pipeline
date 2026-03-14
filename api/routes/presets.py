from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/presets", tags=["presets"])
_PRESETS_DIR = Path(__file__).resolve().parents[2] / "presets"


def _list_preset_files() -> list[Path]:
    if not _PRESETS_DIR.exists():
        return []
    return sorted(_PRESETS_DIR.glob("*.json"))


@router.get("")
def list_presets() -> dict[str, Any]:
    items = []
    for file_path in _list_preset_files():
        items.append({"name": file_path.stem, "filename": file_path.name})
    return {"items": items}


@router.get("/{name}")
def get_preset(name: str) -> dict[str, Any]:
    file_path = _PRESETS_DIR / f"{name}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Preset '{name}' is invalid JSON") from exc

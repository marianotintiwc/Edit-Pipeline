from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# Valid top-level keys for Partial<JobInput> (profile input)
VALID_JOB_INPUT_KEYS = frozenset({
    "video_urls", "geo", "clips", "music_url", "music_volume", "loop_music",
    "subtitle_mode", "edit_preset", "enable_interpolation", "rife_model",
    "input_fps", "manual_srt_url", "style_overrides", "output_filename",
    "output_folder", "output_bucket", "aspect_ratio", "request_text",
    "plan_only", "storyboard", "retrieval",
})

# Built-in MELI profile: clip order introcard, scene1, scene2, scene3, broll, endcard
# Subtitle: no stroke, text color = stroke_color. Geo BR/MLB -> pt via normalize_geo.
MELI_DEFAULT_PROFILE_ID = "meli-default"

MELI_DEFAULT_INPUT: Dict[str, Any] = {
    "subtitle_mode": "auto",
    "edit_preset": "standard_vertical",
    "style_overrides": {
        "stroke_width": 0,
        "highlight": {
            "stroke_width": 0,
            "text_color": "#333333",
        },
    },
}


def _validate_profile_input(input_payload: Any) -> List[str]:
    """Validate profile input is a sane Partial<JobInput>. Returns list of error messages."""
    errors: List[str] = []
    if input_payload is None:
        return errors
    if not isinstance(input_payload, dict):
        return ["input must be an object"]
    for key in input_payload:
        if key not in VALID_JOB_INPUT_KEYS:
            errors.append(f"Unknown key '{key}' in profile input")
    clips = input_payload.get("clips")
    if clips is not None:
        if not isinstance(clips, list):
            errors.append("clips must be a list")
        else:
            for idx, clip in enumerate(clips):
                if not isinstance(clip, dict):
                    errors.append(f"clips[{idx}] must be an object")
                    continue
                if clip.get("url") is not None and not isinstance(clip.get("url"), str):
                    errors.append(f"clips[{idx}].url must be a string")
                clip_type = clip.get("type")
                if clip_type is not None and clip_type not in ("scene", "broll", "endcard", "introcard"):
                    errors.append(f"clips[{idx}].type must be scene, broll, endcard, or introcard")
    subtitle_mode = input_payload.get("subtitle_mode")
    if subtitle_mode is not None and subtitle_mode not in ("auto", "manual", "none"):
        errors.append("subtitle_mode must be one of: auto, manual, none")
    return errors


@dataclass
class ProfilesStore:
    records: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    counter: int = 0
    storage_path: str | None = None
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            records = payload.get("records", {})
            counter = int(payload.get("counter", 0))
            if isinstance(records, dict):
                self.records = records
            self.counter = counter
        except (OSError, ValueError, TypeError):
            self.records = {}
            self.counter = 0

    def _persist_to_disk(self) -> None:
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        payload = {"counter": self.counter, "records": self.records}
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def create_profile(
        self,
        *,
        user_id: str,
        name: str,
        input_payload: Dict[str, Any],
        is_meli: bool = False,
    ) -> Dict[str, Any]:
        errors = _validate_profile_input(input_payload)
        if errors:
            raise ValueError("; ".join(errors))
        with self._lock:
            self.counter += 1
            profile_id = f"profile-{self.counter}"
            timestamp = _now_iso()
            record = {
                "profile_id": profile_id,
                "name": name,
                "input": deepcopy(input_payload),
                "is_meli": bool(is_meli),
                "created_at": timestamp,
                "updated_at": timestamp,
                "user_id": user_id,
            }
            self.records[profile_id] = record
            self._persist_to_disk()
            return deepcopy(record)

    def update_profile(
        self,
        *,
        profile_id: str,
        user_id: str,
        name: str | None = None,
        input_payload: Dict[str, Any] | None = None,
        is_meli: bool | None = None,
    ) -> Dict[str, Any]:
        with self._lock:
            record = self.records.get(profile_id)
            if not record or record["user_id"] != user_id:
                raise KeyError(profile_id)
            if input_payload is not None:
                errors = _validate_profile_input(input_payload)
                if errors:
                    raise ValueError("; ".join(errors))
                record["input"] = deepcopy(input_payload)
            if name is not None:
                record["name"] = str(name)
            if is_meli is not None:
                record["is_meli"] = bool(is_meli)
            record["updated_at"] = _now_iso()
            self._persist_to_disk()
            return deepcopy(record)

    def delete_profile(self, *, profile_id: str, user_id: str) -> None:
        with self._lock:
            record = self.records.get(profile_id)
            if not record or record["user_id"] != user_id:
                raise KeyError(profile_id)
            del self.records[profile_id]
            self._persist_to_disk()

    def get_profile(self, *, profile_id: str, user_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self.records.get(profile_id)
            if not record or record["user_id"] != user_id:
                raise KeyError(profile_id)
            return deepcopy(record)

    def list_profiles(self, *, user_id: str) -> List[Dict[str, Any]]:
        builtin = {
            "profile_id": MELI_DEFAULT_PROFILE_ID,
            "name": "MELI Default",
            "input": deepcopy(MELI_DEFAULT_INPUT),
            "is_meli": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "user_id": user_id,
        }
        with self._lock:
            user_profiles = [
                deepcopy(record)
                for record in sorted(
                    self.records.values(),
                    key=lambda r: r.get("updated_at", ""),
                    reverse=True,
                )
                if record["user_id"] == user_id
            ]
        return [builtin] + user_profiles

    def get_meli_default(self) -> Dict[str, Any]:
        """Return the built-in MELI profile (no user_id check)."""
        return {
            "profile_id": MELI_DEFAULT_PROFILE_ID,
            "name": "MELI Default",
            "input": deepcopy(MELI_DEFAULT_INPUT),
            "is_meli": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }


@lru_cache(maxsize=1)
def get_profiles_store() -> ProfilesStore:
    storage_path = os.environ.get("PROFILES_STORE_PATH")
    return ProfilesStore(storage_path=storage_path)

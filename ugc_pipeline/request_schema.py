from __future__ import annotations

from typing import Any, Dict, List, Tuple


def collect_payload_issues(input_payload: Dict[str, Any] | None) -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    errors: List[str] = []
    if not isinstance(input_payload, dict):
        return warnings, ["payload.input must be an object"]

    clips = input_payload.get("clips")
    video_urls = input_payload.get("video_urls")
    if not clips and not video_urls:
        errors.append("Either clips or video_urls must be provided")

    if isinstance(clips, list):
        for idx, clip in enumerate(clips):
            if not isinstance(clip, dict):
                errors.append(f"clips[{idx}] must be an object")
                continue
            clip_url = clip.get("url")
            if not isinstance(clip_url, str) or not clip_url.strip():
                errors.append(f"clips[{idx}].url is required and must be a non-empty string")
            clip_type = clip.get("type")
            if clip_type is None:
                warnings.append(f"clips[{idx}].type not provided, defaulting to 'scene'")

    subtitle_mode = input_payload.get("subtitle_mode")
    if subtitle_mode not in (None, "auto", "manual", "none"):
        errors.append("subtitle_mode must be one of: auto, manual, none")

    return warnings, errors

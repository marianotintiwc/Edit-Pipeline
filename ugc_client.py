#!/usr/bin/env python3
"""
UGC Pipeline Client - Cliente copiable para enviar jobs a RunPod.

Este módulo está diseñado para ser copiado a otros workspaces/proyectos.
Solo requiere: pip install requests

Uso básico:
    from ugc_client import UGCPipelineClient
    
    client = UGCPipelineClient(api_key="...", endpoint_id="...")
    payload = client.build_payload({...})
    result = client.submit_job_sync(payload)

Ejemplo MELI (geo=MLB):
    client = UGCPipelineClient(
        api_key=os.environ["RUNPOD_API_KEY"],
        endpoint_id=os.environ["RUNPOD_ENDPOINT_ID"]
    )
    
    payload = {
        "input": {
            "geo": "MLB",
            "clips": [
                {"type": "scene", "url": "https://.../scene1.mp4"},
                {"type": "scene", "url": "https://.../scene2.mp4"},
                {
                    "type": "broll",
                    "url": "https://.../broll.mp4",
                    "alpha_fill": {"enabled": True, "blur_sigma": 60, "slow_factor": 1.5}
                },
                {"type": "scene", "url": "https://.../scene3.mp4", "end_time": -0.1},
                {
                    "type": "endcard",
                    "url": "https://.../endcard.mov",
                    "overlap_seconds": 0.5,
                    "alpha_fill": {"enabled": True, "blur_sigma": 30}
                }
            ],
            "music_url": "random",
            "subtitle_mode": "auto",
            "enable_interpolation": True,
            "style_overrides": {
                "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
                "fontsize": 60,
                "stroke_color": "#333333",
                "stroke_width": 10,
                "highlight": {"color": "#333333", "stroke_width": 4},
                "transcription": {"model": "large"},
                "postprocess": {"color_grading": {"enabled": False}}
            }
        }
    }
    
    # Validar antes de enviar (detecta typos)
    warnings, errors = client.validate_payload(payload, strict=False)
    for w in warnings:
        print(f"⚠️ {w}")
    
    # Enviar job y esperar resultado
    result = client.submit_job_sync(payload)
    print(f"✅ Video: {result['output']['output_url']}")

Docker Image recomendada: marianotintiwc/ugc-pipeline:latestv_1.06

Variables de entorno requeridas:
    RUNPOD_API_KEY      - API key de RunPod
    RUNPOD_ENDPOINT_ID  - ID del endpoint serverless
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re
import requests


VALID_INPUT_KEYS = {
    "video_urls",
    "clips",
    "geo",
    "music_url",
    "music_volume",
    "loop_music",
    "subtitle_mode",
    "manual_srt_url",
    "edit_preset",
    "enable_interpolation",
    "rife_model",
    "style_overrides",
    "output_filename",
    "output_folder",
    "project_name",
    "job_id"
}

VALID_CLIP_KEYS = {
    "type",
    "url",
    "start_time",
    "end_time",
    "alpha_fill",
    "overlap_seconds",
    "effects",
    "duration",
    "invert_alpha"
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_alpha_fill_config(alpha_cfg: Dict[str, Any], prefix: str, errors: List[str]) -> None:
    """Validate alpha_fill config for expected types and ranges."""
    if not isinstance(alpha_cfg, dict):
        errors.append(f"{prefix} must be an object")
        return

    def _check_bool(key: str):
        if key in alpha_cfg and alpha_cfg[key] is not None and not isinstance(alpha_cfg[key], bool):
            errors.append(f"{prefix}.{key} must be a boolean")

    def _check_number(key: str, min_val: float | None = None, max_val: float | None = None):
        if key in alpha_cfg and alpha_cfg[key] is not None:
            if not _is_number(alpha_cfg[key]):
                errors.append(f"{prefix}.{key} must be a number")
                return
            if min_val is not None and alpha_cfg[key] < min_val:
                errors.append(f"{prefix}.{key} must be >= {min_val}")
            if max_val is not None and alpha_cfg[key] > max_val:
                errors.append(f"{prefix}.{key} must be <= {max_val}")

    _check_bool("enabled")
    _check_number("blur_sigma", min_val=0)
    _check_number("slow_factor", min_val=0)
    _check_bool("force_chroma_key")
    _check_number("chroma_key_similarity", min_val=0, max_val=1)
    _check_number("chroma_key_blend", min_val=0, max_val=1)
    _check_number("edge_feather", min_val=0)
    _check_bool("auto_tune")
    _check_number("auto_tune_min", min_val=0, max_val=1)
    _check_number("auto_tune_max", min_val=0, max_val=1)
    _check_number("auto_tune_step", min_val=0, max_val=1)
    _check_bool("invert_alpha")
    _check_bool("auto_invert_alpha")
    _check_number("auto_invert_alpha_threshold", min_val=0, max_val=1)

    if "auto_tune_min" in alpha_cfg and "auto_tune_max" in alpha_cfg:
        min_val = alpha_cfg.get("auto_tune_min")
        max_val = alpha_cfg.get("auto_tune_max")
        if _is_number(min_val) and _is_number(max_val) and min_val > max_val:
            errors.append(f"{prefix}.auto_tune_min must be <= auto_tune_max")

    if "auto_tune_step" in alpha_cfg:
        step = alpha_cfg.get("auto_tune_step")
        if _is_number(step) and step <= 0:
            errors.append(f"{prefix}.auto_tune_step must be > 0")

    if "chroma_key_color" in alpha_cfg and alpha_cfg["chroma_key_color"] is not None:
        color = str(alpha_cfg["chroma_key_color"])
        if not re.match(r"^(#|0x)[0-9a-fA-F]{6}$", color):
            errors.append(f"{prefix}.chroma_key_color must be #RRGGBB or 0xRRGGBB")


class UGCPipelineClient:
    def __init__(self, api_key: str, endpoint_id: str, base_url: Optional[str] = None, timeout: int = 600):
        self.base_url = base_url or f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = timeout

    def build_payload(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"input": input_data}

    def validate_payload(self, payload: Dict[str, Any], strict: bool = True) -> Tuple[List[str], List[str]]:
        warnings: List[str] = []
        errors: List[str] = []

        if not isinstance(payload, dict) or "input" not in payload:
            errors.append("payload must be an object with an 'input' key")
            return warnings, errors

        input_data = payload.get("input")
        if not isinstance(input_data, dict):
            errors.append("payload.input must be an object")
            return warnings, errors

        unknown_top = [k for k in input_data.keys() if k not in VALID_INPUT_KEYS]
        for key in unknown_top:
            warnings.append(f"Unknown input field '{key}' will be ignored by the server")

        if "video_urls" in input_data and input_data["video_urls"] is not None:
            if not isinstance(input_data["video_urls"], list) or not all(isinstance(u, str) for u in input_data["video_urls"]):
                errors.append("video_urls must be an array of strings")

        if "clips" in input_data and input_data["clips"] is not None:
            if not isinstance(input_data["clips"], list):
                errors.append("clips must be an array of clip objects")
            else:
                for idx, clip in enumerate(input_data["clips"]):
                    if not isinstance(clip, dict):
                        errors.append(f"clips[{idx}] must be an object")
                        continue
                    unknown_clip = [k for k in clip.keys() if k not in VALID_CLIP_KEYS]
                    for key in unknown_clip:
                        warnings.append(f"Unknown clip field '{key}' in clips[{idx}] will be ignored by the server")
                    if not clip.get("url") or not isinstance(clip.get("url"), str):
                        errors.append(f"clips[{idx}].url is required and must be a string")
                    clip_type = clip.get("type", "scene")
                    if clip_type not in ("scene", "broll", "endcard"):
                        errors.append(f"clips[{idx}].type must be 'scene', 'broll', or 'endcard'")
                    for key in ("start_time", "end_time"):
                        if key in clip and clip[key] is not None and not _is_number(clip[key]):
                            errors.append(f"clips[{idx}].{key} must be a number or null")
                    if "overlap_seconds" in clip and clip["overlap_seconds"] is not None:
                        if not _is_number(clip["overlap_seconds"]):
                            errors.append(f"clips[{idx}].overlap_seconds must be a number or null")
                        elif clip["overlap_seconds"] < 0:
                            errors.append(f"clips[{idx}].overlap_seconds must be >= 0")
                    if "alpha_fill" in clip and clip["alpha_fill"] is not None and not isinstance(clip["alpha_fill"], dict):
                        errors.append(f"clips[{idx}].alpha_fill must be an object or null")
                    if "alpha_fill" in clip and clip["alpha_fill"] is not None:
                        _validate_alpha_fill_config(clip["alpha_fill"], f"clips[{idx}].alpha_fill", errors)
                    if "effects" in clip and clip["effects"] is not None and not isinstance(clip["effects"], dict):
                        errors.append(f"clips[{idx}].effects must be an object or null")

        if "music_volume" in input_data and input_data["music_volume"] is not None and not _is_number(input_data["music_volume"]):
            errors.append("music_volume must be a number")

        if "loop_music" in input_data and input_data["loop_music"] is not None and not isinstance(input_data["loop_music"], bool):
            errors.append("loop_music must be a boolean")

        if "enable_interpolation" in input_data and input_data["enable_interpolation"] is not None and not isinstance(input_data["enable_interpolation"], bool):
            errors.append("enable_interpolation must be a boolean")

        if "subtitle_mode" in input_data and input_data["subtitle_mode"] is not None:
            if input_data["subtitle_mode"] not in {"auto", "manual", "none"}:
                errors.append("subtitle_mode must be 'auto', 'manual', or 'none'")

        if "style_overrides" in input_data and input_data["style_overrides"] is not None:
            if not isinstance(input_data["style_overrides"], dict):
                errors.append("style_overrides must be an object")
            else:
                for key in ("broll_alpha_fill", "endcard_alpha_fill"):
                    if key in input_data["style_overrides"] and input_data["style_overrides"][key] is not None:
                        _validate_alpha_fill_config(
                            input_data["style_overrides"][key],
                            f"style_overrides.{key}",
                            errors
                        )

        if strict and errors:
            raise ValueError("Payload validation failed: " + "; ".join(errors))

        return warnings, errors

    def submit_job_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_payload(payload, strict=True)
        response = requests.post(
            f"{self.base_url}/runsync",
            json=payload,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def submit_job_async(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_payload(payload, strict=True)
        response = requests.post(
            f"{self.base_url}/run",
            json=payload,
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/status/{job_id}",
            headers=self.headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    import os
    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")

    if not api_key or not endpoint_id:
        raise SystemExit("RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID are required")

    client = UGCPipelineClient(api_key, endpoint_id)

    payload = {
        "input": {
            "project_name": "demo-MLA",
            "geo": "MLA",
            "clips": [
                {"type": "scene", "url": "https://.../scene1.mp4"},
                {"type": "scene", "url": "https://.../scene2.mp4"},
                {
                    "type": "broll",
                    "url": "https://.../broll.mp4",
                    "alpha_fill": {"enabled": True, "blur_sigma": 60, "slow_factor": 1.6}
                },
                {"type": "scene", "url": "https://.../scene3.mp4"},
                {
                    "type": "endcard",
                    "url": "https://.../endcard.mov",
                    "overlap_seconds": 1.25,
                    "alpha_fill": {"enabled": True, "blur_sigma": 30, "slow_factor": 1.2}
                }
            ],
            "music_url": "random",
            "subtitle_mode": "auto",
            "style_overrides": {
                "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
                "fontsize": 60,
                "stroke_color": "#333333",
                "stroke_width": 10,
                "transcription": {"model": "large"}
            }
        }
    }

    warnings, _ = client.validate_payload(payload, strict=False)
    for w in warnings:
        print(f"[WARN] {w}")

    result = client.submit_job_sync(payload)
    print(result)

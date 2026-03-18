from __future__ import annotations

import csv
import io
import re
from copy import deepcopy
from typing import Any, Dict, List, Tuple

from geo_mapping import normalize_geo
from ugc_pipeline.request_schema import collect_payload_issues


_SEGMENT_TOKEN_RE = re.compile(r"([^\[\]]+)|\[(\d+)\]")


def _coerce_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped == "":
        return ""
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return stripped


def _set_path(target: Dict[str, Any], path: str, raw_value: str) -> None:
    value = _coerce_scalar(raw_value)
    tokens: List[Any] = []
    for segment in path.split("."):
        for match in _SEGMENT_TOKEN_RE.finditer(segment):
            key_token = match.group(1)
            index_token = match.group(2)
            if key_token is not None:
                tokens.append(key_token)
            elif index_token is not None:
                tokens.append(int(index_token))

    current: Any = target
    for index, token in enumerate(tokens):
        is_last = index == len(tokens) - 1
        next_token = None if is_last else tokens[index + 1]

        if isinstance(token, str):
            if is_last:
                current[token] = value
                return
            if token not in current or current[token] in ("", None):
                current[token] = [] if isinstance(next_token, int) else {}
            current = current[token]
            continue

        if not isinstance(current, list):
            raise ValueError(f"Invalid CSV path '{path}'")
        while len(current) <= token:
            current.append(None)
        if is_last:
            current[token] = value
            return
        if current[token] in (None, ""):
            current[token] = [] if isinstance(next_token, int) else {}
        current = current[token]


def _normalize_row(raw_row: Dict[str, str]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in raw_row.items():
        if key is None:
            continue
        stripped_key = key.strip()
        if not stripped_key:
            continue
        _set_path(normalized, stripped_key, value or "")

    # Drop blank clips that come from sparse CSV columns.
    clips = normalized.get("clips")
    if isinstance(clips, list):
        normalized["clips"] = [
            clip
            for clip in clips
            if isinstance(clip, dict)
            and any((clip.get("url"), clip.get("type"), clip.get("start_time"), clip.get("end_time")))
        ]

    return normalized


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_row_with_mapping(raw_row: Dict[str, str], mapping: Dict[str, str]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for header, target_path in mapping.items():
        if not target_path:
            continue
        raw_value = raw_row.get(header, "")
        _set_path(normalized, target_path, raw_value or "")
    return normalized


def parse_batch_csv(
    content: bytes,
    *,
    mapping: Dict[str, str] | None = None,
    recipe_input: Dict[str, Any] | None = None,
) -> Tuple[int, List[Dict[str, Any]]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []

    for row_number, raw_row in enumerate(reader, start=1):
        input_payload = (
            _normalize_row_with_mapping(raw_row, mapping)
            if mapping
            else _normalize_row(raw_row)
        )
        if recipe_input:
            input_payload = _deep_merge(recipe_input, input_payload)
        # Normalize geo (BR -> MLB, etc.) for Whisper/language resolution
        if input_payload.get("geo"):
            input_payload["geo"] = normalize_geo(str(input_payload["geo"]))
        warnings, errors = collect_payload_issues(deepcopy(input_payload))
        rows.append(
            {
                "row_number": row_number,
                "status": "ready" if not errors else "blocked_by_validation",
                "warnings": warnings,
                "errors": errors,
                "input": input_payload,
            }
        )

    return len(rows), rows

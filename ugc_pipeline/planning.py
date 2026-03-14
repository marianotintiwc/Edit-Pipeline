from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from ugc_pipeline.request_schema import collect_payload_issues


@dataclass
class ExecutionPlan:
    normalized_input: Dict[str, Any]
    intents: List[str]
    warnings: List[str]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "normalized_input": self.normalized_input,
            "job_input": self.normalized_input,
            "intents": self.intents,
            "warnings": self.warnings,
            "plan_only": bool(self.normalized_input.get("plan_only")),
            "resolved_style": self.normalized_input.get("style_overrides") or {},
            "resolved_clips": self.normalized_input.get("clips") or [],
            "storyboard_plan": self.normalized_input.get("storyboard"),
            "retrieval_plan": self.normalized_input.get("retrieval"),
            "execution_steps": [
                "validate_input",
                "resolve_assets",
                "submit_runpod_job",
            ],
        }


def build_execution_plan(job_input: Dict[str, Any]) -> ExecutionPlan:
    if not isinstance(job_input, dict):
        raise ValueError("payload.input must be an object")
    warnings, errors = collect_payload_issues(job_input)
    if errors:
        raise ValueError("; ".join(errors))
    intents = ["video_edit"]
    if job_input.get("subtitle_mode") == "auto":
        intents.append("auto_subtitles")
    if job_input.get("enable_interpolation", True):
        intents.append("frame_interpolation")
    return ExecutionPlan(
        normalized_input=job_input,
        intents=intents,
        warnings=warnings,
        errors=[],
    )

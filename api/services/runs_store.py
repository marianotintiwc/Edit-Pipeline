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


@dataclass
class RunsStore:
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
            # Keep service operational with in-memory fallback.
            self.records = {}
            self.counter = 0

    def _persist_to_disk(self) -> None:
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        payload = {"counter": self.counter, "records": self.records}
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def create_run(
        self,
        *,
        user_id: str,
        preset_name: str | None,
        payload: Dict[str, Any],
        runpod_job_id: str,
        initial_status: str,
    ) -> Dict[str, Any]:
        with self._lock:
            self.counter += 1
            run_id = f"run-{self.counter}"
            timestamp = _now_iso()
            record = {
                "run_id": run_id,
                "job_id": runpod_job_id,
                "status": initial_status,
                "geo": payload.get("geo"),
                "preset_name": preset_name,
                "created_at": timestamp,
                "updated_at": timestamp,
                "logs": [],
                "input_snapshot": payload,
                "user_id": user_id,
            }
            self.records[run_id] = record
            self._persist_to_disk()
            return deepcopy(record)

    def update_job_status(self, *, job_id: str, status_payload: Dict[str, Any]) -> Dict[str, Any] | None:
        with self._lock:
            for record in self.records.values():
                if record["job_id"] != job_id:
                    continue
                record["status"] = status_payload.get("status", record["status"])
                record["stage"] = status_payload.get("stage")
                record["logs"] = status_payload.get("logs", [])
                output = status_payload.get("output") or {}
                if output.get("output_url"):
                    record["output_url"] = output["output_url"]
                record["updated_at"] = _now_iso()
                self._persist_to_disk()
                return deepcopy(record)
        return None

    def list_runs(self, *, user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(record)
                for record in self.records.values()
                if record["user_id"] == user_id
            ]

    def get_run_by_job_id(self, *, job_id: str, user_id: str) -> Dict[str, Any]:
        with self._lock:
            for record in self.records.values():
                if record["job_id"] == job_id and record["user_id"] == user_id:
                    return deepcopy(record)
        raise KeyError(job_id)

    def get_run(self, *, run_id: str, user_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self.records[run_id]
            if record["user_id"] != user_id:
                raise KeyError(run_id)
            return deepcopy(record)


@lru_cache(maxsize=1)
def get_runs_store() -> RunsStore:
    storage_path = os.environ.get("RUNS_STORE_PATH")
    return RunsStore(storage_path=storage_path)

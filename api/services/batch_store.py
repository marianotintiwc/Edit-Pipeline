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
class BatchStore:
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

    def next_batch_id(self) -> str:
        with self._lock:
            self.counter += 1
            self._persist_to_disk()
            return f"batch-{self.counter}"

    def save_batch(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self.records[batch["batch_id"]] = deepcopy(batch)
            self._persist_to_disk()
            return deepcopy(batch)

    def get_batch(self, *, batch_id: str, user_id: str) -> Dict[str, Any]:
        with self._lock:
            batch = self.records[batch_id]
            if batch["user_id"] != user_id:
                raise KeyError(batch_id)
            return deepcopy(batch)

    def update_batch(self, *, batch_id: str, user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            batch = self.records[batch_id]
            if batch["user_id"] != user_id:
                raise KeyError(batch_id)
            batch.update(deepcopy(patch))
            batch["updated_at"] = _now_iso()
            self._persist_to_disk()
            return deepcopy(batch)

    def list_batches(self, *, user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(batch)
                for batch in sorted(
                    self.records.values(),
                    key=lambda record: record.get("updated_at", ""),
                    reverse=True,
                )
                if batch["user_id"] == user_id
            ]


@lru_cache(maxsize=1)
def get_batch_store() -> BatchStore:
    storage_path = os.environ.get("BATCH_STORE_PATH")
    return BatchStore(storage_path=storage_path)

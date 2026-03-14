from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from threading import Lock
from typing import Any, Dict, Optional

from api.app_config import get_app_config


def _hash_payload(payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class IdempotencyStore:
    records: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    storage_path: str | None = None
    ttl_seconds: int = 86400
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        self._load_from_disk()

    def _key(self, *, user_id: str, scope: str, idempotency_key: str) -> str:
        return f"{scope}:{user_id}:{idempotency_key}"

    def _load_from_disk(self) -> None:
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                self.records = payload
        except (OSError, ValueError, TypeError):
            self.records = {}

    def _persist_to_disk(self) -> None:
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump(self.records, handle)

    def _is_expired(self, record: Dict[str, Any]) -> bool:
        created_at = float(record.get("created_at_epoch", 0))
        return created_at + self.ttl_seconds < time.time()

    def get(
        self,
        *,
        user_id: str,
        scope: str,
        idempotency_key: str,
    ) -> Optional[Dict[str, Any]]:
        storage_key = self._key(user_id=user_id, scope=scope, idempotency_key=idempotency_key)
        with self._lock:
            record = self.records.get(storage_key)
            if not record:
                return None
            if self._is_expired(record):
                self.records.pop(storage_key, None)
                self._persist_to_disk()
                return None
            return dict(record)

    def put(
        self,
        *,
        user_id: str,
        scope: str,
        idempotency_key: str,
        request_payload: Dict[str, Any],
        response_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        storage_key = self._key(user_id=user_id, scope=scope, idempotency_key=idempotency_key)
        record = {
            "request_hash": _hash_payload(request_payload),
            "response_payload": response_payload,
            "created_at_epoch": time.time(),
        }
        with self._lock:
            self.records[storage_key] = record
            self._persist_to_disk()
        return dict(record)

    def request_hash_matches(
        self,
        *,
        record: Dict[str, Any],
        request_payload: Dict[str, Any],
    ) -> bool:
        return str(record.get("request_hash", "")) == _hash_payload(request_payload)


@lru_cache(maxsize=1)
def get_idempotency_store() -> IdempotencyStore:
    config = get_app_config()
    return IdempotencyStore(
        storage_path=config.idempotency_store_path,
        ttl_seconds=config.idempotency_ttl_seconds,
    )

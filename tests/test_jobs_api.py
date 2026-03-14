import json
import unittest
from hashlib import sha256

from fastapi.testclient import TestClient


class JobsApiTests(unittest.TestCase):
    def setUp(self):
        from api.auth import get_current_user
        from api.main import app
        from api.services.idempotency_store import get_idempotency_store
        from api.services.runpod import get_runpod_service
        from api.services.runs_store import get_runs_store

        class StubRunPodService:
            def __init__(self) -> None:
                self.submissions = []

            def submit_job(self, payload):
                self.submissions.append(payload)
                return {"job_id": f"job-{len(self.submissions)}", "status": "IN_QUEUE"}

            def get_job_status(self, job_id):
                return {"status": "COMPLETED", "stage": "Finished", "logs": [f"done:{job_id}"]}

        class StubRunsStore:
            def __init__(self) -> None:
                self.records = {}
                self.counter = 0

            def create_run(self, *, user_id, preset_name, payload, runpod_job_id, initial_status):
                self.counter += 1
                run_id = f"run-{self.counter}"
                record = {
                    "run_id": run_id,
                    "job_id": runpod_job_id,
                    "status": initial_status,
                    "preset_name": preset_name,
                    "input_snapshot": payload,
                    "user_id": user_id,
                }
                self.records[run_id] = record
                return record

            def get_run_by_job_id(self, *, job_id, user_id):
                for item in self.records.values():
                    if item["job_id"] == job_id and item["user_id"] == user_id:
                        return item
                raise KeyError(job_id)

            def update_job_status(self, *, job_id, status_payload):
                for item in self.records.values():
                    if item["job_id"] == job_id:
                        item["status"] = status_payload.get("status", item["status"])
                        return item
                raise KeyError(job_id)

        class StubIdempotencyStore:
            def __init__(self) -> None:
                self.records = {}

            def _digest(self, payload):
                normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                return sha256(normalized.encode("utf-8")).hexdigest()

            def get(self, *, user_id, scope, idempotency_key):
                return self.records.get(f"{scope}:{user_id}:{idempotency_key}")

            def request_hash_matches(self, *, record, request_payload):
                return record["request_hash"] == self._digest(request_payload)

            def put(self, *, user_id, scope, idempotency_key, request_payload, response_payload):
                key = f"{scope}:{user_id}:{idempotency_key}"
                self.records[key] = {
                    "request_hash": self._digest(request_payload),
                    "response_payload": response_payload,
                }
                return self.records[key]

        self.runpod_service = StubRunPodService()
        self.runs_store = StubRunsStore()
        self.idempotency_store = StubIdempotencyStore()
        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "user-123",
            "email": "jobs@test.local",
        }
        app.dependency_overrides[get_runpod_service] = lambda: self.runpod_service
        app.dependency_overrides[get_runs_store] = lambda: self.runs_store
        app.dependency_overrides[get_idempotency_store] = lambda: self.idempotency_store
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    @staticmethod
    def _payload(scene_url: str) -> dict:
        return {
            "input": {
                "geo": "MLA",
                "subtitle_mode": "auto",
                "clips": [{"type": "scene", "url": scene_url}],
            }
        }

    def test_submit_job_returns_202_accepted(self):
        response = self.client.post("/api/jobs", json=self._payload("https://example.com/s1.mp4"))
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["job_id"], "job-1")
        self.assertEqual(body["run_id"], "run-1")
        self.assertEqual(len(self.runpod_service.submissions), 1)

    def test_submit_job_honors_idempotency_key_with_202_replay(self):
        first = self.client.post(
            "/api/jobs",
            json=self._payload("https://example.com/s1.mp4"),
            headers={"Idempotency-Key": "jobs-key-1"},
        )
        second = self.client.post(
            "/api/jobs",
            json=self._payload("https://example.com/s1.mp4"),
            headers={"Idempotency-Key": "jobs-key-1"},
        )
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 202)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(len(self.runpod_service.submissions), 1)

    def test_submit_job_rejects_idempotency_key_payload_mismatch(self):
        self.client.post(
            "/api/jobs",
            json=self._payload("https://example.com/s1.mp4"),
            headers={"Idempotency-Key": "jobs-key-2"},
        )
        conflict = self.client.post(
            "/api/jobs",
            json=self._payload("https://example.com/s2.mp4"),
            headers={"Idempotency-Key": "jobs-key-2"},
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.json()["error_code"],
            "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
        )


if __name__ == "__main__":
    unittest.main()

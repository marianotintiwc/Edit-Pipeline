"""Tests for cancel run and cancel batch endpoints."""

import io
import unittest

from fastapi.testclient import TestClient


class CancelApiTests(unittest.TestCase):
    def setUp(self):
        from api.auth import get_current_user
        from api.main import app
        from api.services.batch_store import get_batch_store
        from api.services.runpod import get_runpod_service
        from api.services.runs_store import get_runs_store

        class StubRunPodService:
            def __init__(self) -> None:
                self.submissions = []
                self.cancelled_jobs = []

            def submit_job(self, payload):
                self.submissions.append(payload)
                job_id = f"job-{len(self.submissions)}"
                return {"job_id": job_id, "status": "IN_QUEUE"}

            def get_job_status(self, job_id):
                return {"status": "COMPLETED", "stage": "done"}

            def cancel_job(self, job_id):
                self.cancelled_jobs.append(job_id)
                return {"id": job_id, "status": "CANCELLED"}

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
                    "user_id": user_id,
                }
                self.records[run_id] = record
                return record

            def get_run(self, *, run_id, user_id):
                r = self.records[run_id]
                if r["user_id"] != user_id:
                    raise KeyError(run_id)
                return r.copy()

            def update_job_status(self, *, job_id, status_payload):
                for r in self.records.values():
                    if r["job_id"] == job_id:
                        r["status"] = status_payload.get("status", r["status"])
                        return r
                return None

        class StubBatchStore:
            def __init__(self) -> None:
                self.records = {}

            def save_batch(self, batch):
                self.records[batch["batch_id"]] = batch
                return batch

            def get_batch(self, *, batch_id, user_id):
                return self.records[batch_id]

            def update_batch(self, *, batch_id, user_id, patch):
                batch = self.records[batch_id]
                batch.update(patch)
                return batch

        self.runpod = StubRunPodService()
        self.runs_store = StubRunsStore()
        self.batch_store = StubBatchStore()

        app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1", "email": "t@t.com"}
        app.dependency_overrides[get_runpod_service] = lambda: self.runpod
        app.dependency_overrides[get_runs_store] = lambda: self.runs_store
        app.dependency_overrides[get_batch_store] = lambda: self.batch_store
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_cancel_run_returns_cancelled_true(self):
        job_resp = self.client.post(
            "/api/jobs",
            json={
                "input": {
                    "geo": "MLA",
                    "clips": [{"type": "scene", "url": "https://x.com/s1.mp4"}],
                }
            },
        )
        run_id = job_resp.json()["run_id"]

        cancel_resp = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual(cancel_resp.status_code, 200)
        body = cancel_resp.json()
        self.assertTrue(body["cancelled"])
        self.assertEqual(len(self.runpod.cancelled_jobs), 1)
        self.assertEqual(self.runpod.cancelled_jobs[0], body["job_id"])

    def test_cancel_run_already_terminal_returns_cancelled_false(self):
        job_resp = self.client.post(
            "/api/jobs",
            json={
                "input": {
                    "geo": "MLA",
                    "clips": [{"type": "scene", "url": "https://x.com/s1.mp4"}],
                }
            },
        )
        run_id = job_resp.json()["run_id"]
        self.runs_store.records[run_id]["status"] = "COMPLETED"

        cancel_resp = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual(cancel_resp.status_code, 200)
        body = cancel_resp.json()
        self.assertFalse(body["cancelled"])
        self.assertEqual(body.get("reason"), "already_terminal")

    def test_cancel_run_404_when_not_found(self):
        cancel_resp = self.client.post("/api/runs/run-nonexistent/cancel")
        self.assertEqual(cancel_resp.status_code, 404)

    def test_cancel_batch_cancels_active_rows(self):
        create_resp = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,clips[0].type,clips[0].url\n"
                            "MLA,scene,https://example.com/s1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_resp.json()["batch_id"]
        self.batch_store.records[batch_id] = create_resp.json()

        self.client.post(f"/api/batches/{batch_id}/submit")

        cancel_resp = self.client.post(f"/api/batches/{batch_id}/cancel")
        self.assertEqual(cancel_resp.status_code, 200)
        body = cancel_resp.json()
        self.assertIn("cancelled_ok", body)
        self.assertGreater(len(body["cancelled_ok"]), 0)

    def test_cancel_batch_404_when_not_found(self):
        cancel_resp = self.client.post("/api/batches/batch-nonexistent/cancel")
        self.assertEqual(cancel_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()

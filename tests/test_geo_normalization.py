"""Tests for geo normalization (BR -> MLB) in planning and batch."""

import io
import unittest

from fastapi.testclient import TestClient


class GeoNormalizationTests(unittest.TestCase):
    def test_planning_normalizes_br_to_mlb(self):
        from ugc_pipeline.planning import build_execution_plan

        plan = build_execution_plan({
            "geo": "BR",
            "clips": [{"type": "scene", "url": "https://example.com/s1.mp4"}],
        })
        self.assertEqual(plan.normalized_input.get("geo"), "MLB")

    def test_planning_passes_through_mlb(self):
        from ugc_pipeline.planning import build_execution_plan

        plan = build_execution_plan({
            "geo": "MLB",
            "clips": [{"type": "scene", "url": "https://example.com/s1.mp4"}],
        })
        self.assertEqual(plan.normalized_input.get("geo"), "MLB")

    def test_batch_csv_normalizes_geo(self):
        from api.services.batch_csv import parse_batch_csv

        content = (
            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
            "BR,auto,scene,https://example.com/s1.mp4\n"
        ).encode("utf-8")
        _, rows = parse_batch_csv(content)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["input"]["geo"], "MLB")

    def test_batch_submit_normalizes_geo(self):
        from api.main import app
        from api.auth import get_current_user
        from api.services.batch_store import get_batch_store
        from api.services.runpod import get_runpod_service
        from api.services.runs_store import get_runs_store

        class StubRunPodService:
            def submit_job(self, payload):
                self.last_payload = payload
                return {"job_id": "job-1", "status": "IN_QUEUE"}

            def get_job_status(self, job_id):
                return {"status": "COMPLETED", "stage": "done"}

        class StubRunsStore:
            def create_run(self, *, user_id, preset_name, payload, runpod_job_id, initial_status):
                return {"run_id": "run-1", "job_id": runpod_job_id, "status": initial_status}

            def update_job_status(self, *, job_id, status_payload):
                return None

        class StubBatchStore:
            def __init__(self):
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

        runpod = StubRunPodService()
        runs_store = StubRunsStore()
        batch_store = StubBatchStore()

        app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1", "email": "t@t.com"}
        app.dependency_overrides[get_runpod_service] = lambda: runpod
        app.dependency_overrides[get_runs_store] = lambda: runs_store
        app.dependency_overrides[get_batch_store] = lambda: batch_store
        self.addCleanup(app.dependency_overrides.clear)

        client = TestClient(app)

        create_resp = client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,clips[0].type,clips[0].url\n"
                            "BR,scene,https://example.com/s1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_resp.json()["batch_id"]
        batch_store.records[batch_id] = create_resp.json()

        submit_resp = client.post(f"/api/batches/{batch_id}/submit")
        self.assertEqual(submit_resp.status_code, 200)
        self.assertEqual(runpod.last_payload["input"]["geo"], "MLB")


if __name__ == "__main__":
    unittest.main()

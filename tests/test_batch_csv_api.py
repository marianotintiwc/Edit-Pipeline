import io
import unittest

from fastapi.testclient import TestClient


class BatchCsvApiTests(unittest.TestCase):
    def setUp(self):
        from api.main import app
        from api.auth import get_current_user
        from api.services.batch_store import get_batch_store
        from api.services.runpod import get_runpod_service
        from api.services.runs_store import get_runs_store

        class StubRunPodService:
            def __init__(self) -> None:
                self.submissions = []
                self.fail_on_submission_number = None
                self.status_calls = 0

            def submit_job(self, payload):
                self.submissions.append(payload)
                submission_number = len(self.submissions)
                if self.fail_on_submission_number == submission_number:
                    raise RuntimeError("RunPod unavailable")
                return {
                    "job_id": f"job-{submission_number}",
                    "status": "IN_QUEUE",
                }

            def get_job_status(self, job_id):
                self.status_calls += 1
                return {
                    "status": "COMPLETED",
                    "stage": "Finished",
                    "logs": [f"done:{job_id}"],
                }

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
                    "geo": payload.get("geo"),
                    "preset_name": preset_name,
                    "created_at": "2026-03-14T01:00:00Z",
                    "updated_at": "2026-03-14T01:00:00Z",
                    "logs": [],
                    "input_snapshot": payload,
                    "user_id": user_id,
                }
                self.records[run_id] = record
                return record

            def update_job_status(self, *, job_id, status_payload):
                record = next(
                    candidate for candidate in self.records.values() if candidate["job_id"] == job_id
                )
                record["status"] = status_payload["status"]
                record["stage"] = status_payload.get("stage")
                record["logs"] = status_payload.get("logs", [])
                return record

            def list_runs(self, *, user_id):
                return [record for record in self.records.values() if record["user_id"] == user_id]

            def get_run(self, *, run_id, user_id):
                record = self.records[run_id]
                if record["user_id"] != user_id:
                    raise KeyError(run_id)
                return record

        class StubBatchStore:
            def __init__(self) -> None:
                self.records = {}

            def save_batch(self, batch):
                self.records[batch["batch_id"]] = batch
                return batch

            def get_batch(self, *, batch_id, user_id):
                batch = self.records[batch_id]
                if batch["user_id"] != user_id:
                    raise KeyError(batch_id)
                return batch

            def update_batch(self, *, batch_id, user_id, patch):
                batch = self.get_batch(batch_id=batch_id, user_id=user_id)
                batch.update(patch)
                return batch

            def list_batches(self, *, user_id):
                return [
                    batch
                    for batch in self.records.values()
                    if batch["user_id"] == user_id
                ]

        self.runpod_service = StubRunPodService()
        self.runs_store = StubRunsStore()
        self.batch_store = StubBatchStore()
        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "user-123",
            "email": "test@example.com",
        }
        app.dependency_overrides[get_runpod_service] = lambda: self.runpod_service
        app.dependency_overrides[get_runs_store] = lambda: self.runs_store
        app.dependency_overrides[get_batch_store] = lambda: self.batch_store
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_upload_batch_csv_returns_persisted_preview(self):
        response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                            "MLB,auto,scene,\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["batch_id"], "batch-1")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["total_rows"], 2)
        self.assertEqual(payload["valid_rows"], 1)
        self.assertEqual(payload["invalid_rows"], 1)
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertEqual(payload["rows"][1]["status"], "blocked_by_validation")
        self.assertTrue(any("clips[0].url" in error for error in payload["rows"][1]["errors"]))

    def test_upload_batch_csv_rejects_invalid_utf8(self):
        response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(b"\xff\xfe\x00\x00"),
                    "text/csv",
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("errors", payload)
        self.assertTrue(any("UTF-8" in error for error in payload["errors"]))

    def test_get_batch_returns_persisted_preview(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        response = self.client.get(f"/api/batches/{batch_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["batch_id"], batch_id)
        self.assertEqual(payload["rows"][0]["row_number"], 1)

    def test_list_batches_returns_saved_previews(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        response = self.client.get("/api/batches")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"][0]["batch_id"], batch_id)
        self.assertEqual(payload["items"][0]["valid_rows"], 1)

    def test_submit_batch_creates_runs_for_valid_rows_only(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                            "MLB,auto,scene,\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        response = self.client.post(f"/api/batches/{batch_id}/submit")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["batch_id"], batch_id)
        self.assertEqual(payload["status"], "partial_success")
        self.assertEqual(payload["submitted_rows"], 1)
        self.assertEqual(payload["rows"][0]["run_id"], "run-1")
        self.assertEqual(payload["rows"][0]["job_id"], "job-1")
        self.assertEqual(payload["rows"][1]["status"], "blocked_by_validation")
        self.assertEqual(len(self.runpod_service.submissions), 1)

    def test_get_batch_refreshes_submitted_rows_from_job_status(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]
        self.client.post(f"/api/batches/{batch_id}/submit")

        response = self.client.get(f"/api/batches/{batch_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rows"][0]["status"], "completed")
        self.assertEqual(self.runpod_service.status_calls, 1)

    def test_get_batch_can_skip_refresh_for_fast_ui_polls(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]
        self.client.post(f"/api/batches/{batch_id}/submit")
        self.runpod_service.status_calls = 0

        response = self.client.get(f"/api/batches/{batch_id}?refresh=false")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rows"][0]["status"], "submitted")
        self.assertEqual(self.runpod_service.status_calls, 0)

    def test_submit_batch_marks_failed_rows_without_aborting_the_entire_batch(self):
        self.runpod_service.fail_on_submission_number = 2
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                            "MLB,auto,scene,https://example.com/scene2.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        response = self.client.post(f"/api/batches/{batch_id}/submit")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "partial_success")
        self.assertEqual(payload["rows"][0]["status"], "submitted")
        self.assertEqual(payload["rows"][1]["status"], "failed")
        self.assertIn("RunPod unavailable", payload["rows"][1]["errors"][0])

    def test_submit_batch_retries_failed_rows_on_a_follow_up_submit(self):
        self.runpod_service.fail_on_submission_number = 2
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                            "MLB,auto,scene,https://example.com/scene2.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        first_response = self.client.post(f"/api/batches/{batch_id}/submit")
        self.runpod_service.fail_on_submission_number = None
        second_response = self.client.post(f"/api/batches/{batch_id}/submit")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertEqual(second_payload["rows"][0]["status"], "submitted")
        self.assertEqual(second_payload["rows"][1]["status"], "submitted")
        self.assertEqual(second_payload["status"], "completed")

    def test_submit_batch_is_idempotent_after_the_first_submission(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,subtitle_mode,clips[0].type,clips[0].url\n"
                            "MLA,auto,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        first_response = self.client.post(f"/api/batches/{batch_id}/submit")
        second_response = self.client.post(f"/api/batches/{batch_id}/submit")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_payload = first_response.json()
        second_payload = second_response.json()
        self.assertEqual(first_payload["status"], "completed")
        self.assertEqual(second_payload["status"], "completed")
        self.assertEqual(second_payload["submitted_rows"], 1)
        self.assertEqual(second_payload["rows"][0]["run_id"], "run-1")

    def test_upload_batch_supports_mapping_and_recipe_defaults(self):
        response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "market,scene_one\n"
                            "MLA,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
            data={
                "mapping": '{"market":"geo","scene_one":"clips[0].url"}',
                "recipe_input": '{"subtitle_mode":"auto","clips":[{"type":"scene"}]}',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rows"][0]["input"]["geo"], "MLA")
        self.assertEqual(payload["rows"][0]["input"]["clips"][0]["url"], "https://example.com/scene1.mp4")
        self.assertEqual(payload["rows"][0]["input"]["subtitle_mode"], "auto")

    def test_submit_batch_accepts_recipe_input_override(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,clips[0].type,clips[0].url\n"
                            "MLA,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        submit_response = self.client.post(
            f"/api/batches/{batch_id}/submit",
            json={"recipe_input": {"subtitle_mode": "auto"}},
        )

        self.assertEqual(submit_response.status_code, 200)
        self.assertEqual(self.runpod_service.submissions[0]["input"]["subtitle_mode"], "auto")

    def test_submit_batch_honors_idempotency_key(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,clips[0].type,clips[0].url\n"
                            "MLA,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]

        first = self.client.post(
            f"/api/batches/{batch_id}/submit",
            headers={"Idempotency-Key": "batch-submit-1"},
        )
        second = self.client.post(
            f"/api/batches/{batch_id}/submit",
            headers={"Idempotency-Key": "batch-submit-1"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(self.runpod_service.submissions), 1)

    def test_submit_batch_rejects_idempotency_key_payload_mismatch(self):
        create_response = self.client.post(
            "/api/batches",
            files={
                "file": (
                    "jobs.csv",
                    io.BytesIO(
                        (
                            "geo,clips[0].type,clips[0].url\n"
                            "MLA,scene,https://example.com/scene1.mp4\n"
                        ).encode("utf-8")
                    ),
                    "text/csv",
                )
            },
        )
        batch_id = create_response.json()["batch_id"]
        self.client.post(
            f"/api/batches/{batch_id}/submit",
            headers={"Idempotency-Key": "batch-submit-2"},
            json={"recipe_input": {"subtitle_mode": "auto"}},
        )
        conflict = self.client.post(
            f"/api/batches/{batch_id}/submit",
            headers={"Idempotency-Key": "batch-submit-2"},
            json={"recipe_input": {"subtitle_mode": "none"}},
        )

        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(
            conflict.json()["error_code"],
            "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
        )


if __name__ == "__main__":
    unittest.main()

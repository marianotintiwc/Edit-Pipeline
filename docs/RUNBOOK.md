# Operations Runbook

## Common failures

### `RUNPOD_UNAVAILABLE`
- Symptom: API returns `error_code=RUNPOD_UNAVAILABLE`.
- Checks:
  - Confirm RunPod endpoint is healthy.
  - Confirm API credentials/env vars are valid.
  - Inspect API logs for `request_id` and matching job attempts.
- Action: retry request; client has exponential backoff for transient errors.

### `Server returned malformed JSON` in UI
- Symptom: UI banner indicates malformed JSON.
- Checks:
  - Confirm backend is running (`/health`).
  - Confirm reverse proxy path (`/api`) points to API server.
- Action: restart API and inspect upstream response body.

### Batch stuck in `in_progress`
- Symptom: rows remain `submitted/queued/in_progress`.
- Checks:
  - Open batch details endpoint and inspect row `job_id`.
  - Query `/api/jobs/{job_id}` to force status refresh.
- Action: retry failed rows via `POST /api/batches/{batch_id}/submit`.

### Missing run history after restart
- Symptom: `/api/runs` returns empty after server restart.
- Checks:
  - Ensure `RUNS_STORE_PATH` and `BATCH_STORE_PATH` are set to writable locations.
- Action: set env vars and restart API.

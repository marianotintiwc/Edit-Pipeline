# Environments

## Local development
- UI: `cd ui && npm run dev`
- API: `python3 -m uvicorn api.main:app --reload --port 8000`
- UI proxy expects `/api -> http://localhost:8000`

## Staging
- Separate RunPod endpoint and API deployment.
- Use staging-only credentials and storage paths.
- Run smoke scenario:
  - `POST /api/jobs/preview`
  - `POST /api/jobs` with one short clip
  - `POST /api/batches` with one-row CSV

## Production
- Isolated RunPod endpoint and credentials.
- Persistent storage required (`RUNS_STORE_PATH`, `BATCH_STORE_PATH` or durable DB adapter).
- Monitor request success rate and `RUNPOD_UNAVAILABLE` errors.

## Hardening feature flags
- `ENABLE_HARDENING_JOB_IDEMPOTENCY`: enable idempotency behavior on `POST /api/jobs`.
- `ENABLE_HARDENING_BATCH_IDEMPOTENCY`: enable idempotency behavior on `POST /api/batches/{id}/submit`.
- `ENABLE_HARDENING_BATCH_REFRESH_QUERY`: enable `?refresh=false` fast-path on `GET /api/batches/{id}`.
- `ENABLE_HARDENING_CONCURRENT_STATUS_REFRESH`: enable concurrent status refresh for active batch rows.
- `ENABLE_HARDENING_RUNPOD_RETRY_POLICY`: enable retry/backoff and dedicated status timeout behavior.

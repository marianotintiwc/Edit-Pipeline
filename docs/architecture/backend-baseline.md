# Backend Baseline (Throughput-first)

## Current stack
- API: FastAPI (`api/main.py`) with job and batch routes.
- Job provider: RunPod via `UGCPipelineClient`.
- Persistence fallback: JSON files (`RUNS_STORE_PATH`, `BATCH_STORE_PATH`).

## Baseline risks detected
- `GET /api/batches/{batch_id}` performs status refresh work inline and can degrade under high active-row counts.
- Retry behavior existed at client level but without dedicated status timeout and jitter policy at service boundary.
- No server-side idempotency key handling for submit endpoints.
- No durable abstraction boundary for future DynamoDB/Postgres stores.

## Baseline SLI proposal
- API availability (5m): >= 99.9%
- `POST /api/jobs` accepted latency p95: < 400ms (excluding provider processing time)
- `GET /api/batches/{id}` latency p95: < 800ms with refresh disabled
- Batch submit success ratio (per row): >= 99% excluding provider outages

## Baseline error taxonomy
- Validation: `VALIDATION_ERROR`, `INVALID_*`
- Provider availability: `RUNPOD_UNAVAILABLE`
- Idempotency misuse: `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`

## Phase A checkpoints
1. Idempotency key support in submit endpoints.
2. Decoupled batch refresh (`refresh=false`) and bounded concurrency.
3. Tunable retries/backoff/timeouts through env vars.
4. Interface layer for durable store migration.

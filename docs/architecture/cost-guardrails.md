# Cost Guardrails

## Objective
Protect throughput while preventing runaway cost in retries, polling, logs retention, and compute minutes.

## Guardrails
- Retries:
  - Submit retries: `RUNPOD_SUBMIT_MAX_RETRIES` (default 3)
  - Status retries: `RUNPOD_STATUS_MAX_RETRIES` (default 2)
  - Backoff base: `RUNPOD_RETRY_BACKOFF_SECONDS` (default 0.5)
- Polling:
  - Max refreshed rows per request: `BATCH_REFRESH_MAX_ROWS` (default 50)
  - Max workers per request refresh: `BATCH_REFRESH_MAX_WORKERS` (default 8)
  - Prefer UI polling intervals >= 3s for large batches.
- Idempotency:
  - TTL: `IDEMPOTENCY_TTL_SECONDS` (default 86400)
  - Avoid duplicate submit storms from UI retries.
- Logging:
  - Keep app logs structured; downsample noisy per-row polling logs in production.
  - Define retention windows by environment (staging shorter than production).

## Alarms to wire
- Provider errors:
  - Spike in `RUNPOD_UNAVAILABLE`.
- Retry pressure:
  - High retry-attempt histogram.
- Throughput degradation:
  - Sudden drop in accepted jobs/minute.
- Polling pressure:
  - p95 latency increase in `GET /api/batches/{id}`.

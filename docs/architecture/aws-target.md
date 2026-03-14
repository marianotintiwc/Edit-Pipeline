# AWS Target Architecture (Phased Migration)

## Goal
Move from FastAPI + RunPod-only orchestration to an AWS-native control plane while keeping RunPod as optional compute during migration.

## Phase B (hybrid control plane)
- FastAPI API on ECS/Fargate.
- SQS queue for asynchronous job orchestration.
- Worker adapter that can dispatch either:
  - RunPod jobs (existing provider),
  - AWS compute jobs (future native path).
- DynamoDB as hot-path state store for jobs/runs/batches.
- S3 for outputs and large execution artifacts.
- CloudWatch + OpenTelemetry for traces/logs/metrics.

## Phase C (AWS-native target)
- Keep API contract compatible with existing UI routes.
- Primary compute on AWS workers.
- RunPod kept as optional overflow/feature-specific backend.
- Alarm-driven autoscaling and retry policies centralized in queue consumers.

## Migration constraints
- Preserve `docs/design/api-contract.md` routes and response shapes.
- Roll out behind feature flags:
  - `ENABLE_ASYNC_QUEUE_SUBMISSION`
  - `ENABLE_DYNAMODB_STORE`
  - `ENABLE_RUNPOD_ADAPTER`

## No-downtime path
1. Introduce durable stores behind current interfaces.
2. Start dual-write mode (JSON + durable store) in staging.
3. Enable queue submission for a sampled traffic slice.
4. Shift default path to queue + workers, keep sync fallback.
5. Disable legacy path only after SLO stability period.

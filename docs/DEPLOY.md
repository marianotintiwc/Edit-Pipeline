# Deploy Playbook

## 1) Pre-flight
- Confirm `RUNPOD_API_KEY` and `RUNPOD_ENDPOINT_ID` are present.
- Set `RUNS_STORE_PATH` and `BATCH_STORE_PATH` for persistent API history.
- Run local checks:
  - `python -m pytest tests`
  - `cd ui && npm test && npm run build`

## 2) Backend API (FastAPI)
- Start API locally for smoke validation:
  - `python3 -m uvicorn api.main:app --reload --port 8000`
- Verify:
  - `GET /health`
  - `GET /api/presets`
  - `GET /api/config/options`

## 3) RunPod image deployment
- Build and push image as described in `README.md`.
- Update RunPod endpoint image.
- Validate one canary request with `plan_only=true`.

## 4) Post-deploy checks
- Launch one Studio run.
- Submit one batch with at least one row.
- Validate run history persists across API restart.

## 5) Rollback
- Revert RunPod endpoint to previous image tag.
- Revert API release if schema or route compatibility changed.
- Keep persisted data files (`RUNS_STORE_PATH`, `BATCH_STORE_PATH`) untouched.

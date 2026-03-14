# Visual UI Frontend

React + Vite frontend for configuring UGC Pipeline jobs through operator-focused workspaces.

## Features

- `Build` workspace for preset-first setup, clip editing, and progressive advanced settings
- `Review & Submit` workspace backed by `POST /api/jobs/preview`
- `Monitor Runs` workspace for reopening saved runs and polling live job status
- `Batch Queue` workspace for CSV upload, recent batch recovery, and batch re-submit
- Backend-driven preset/config metadata via `GET /api/presets` and `GET /api/config/options`
- Progressive advanced controls for interpolation, audio, output, and raw JSON overrides

## Local setup

Install dependencies:

```bash
cd ui
npm install
```

Start the frontend:

```bash
npm run dev
```

The app runs on `http://localhost:5173` (or next free port if 5173 is busy).

## Backend expectation

The Vite dev server proxies `/api` requests to `http://localhost:8000`, so start the FastAPI backend first:

```bash
python3 -m uvicorn api.main:app --reload
```

If you need a fixed backend URL instead of proxy defaults, create `ui/.env` from `ui/.env.example`
and set `VITE_API_BASE_URL`.

The UI expects these backend routes:

- `GET /api/config/options`
- `GET /api/presets`
- `GET /api/presets/{name}`
- `POST /api/jobs/preview`
- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/batches`
- `POST /api/batches`
- `GET /api/batches/{batch_id}`
- `POST /api/batches/{batch_id}/submit`

## Verification

```bash
npm test
npm run build
```

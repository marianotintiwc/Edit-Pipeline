# Frontend / Backend Contract

## Goal
Define the API boundary required by the new shell while preserving the existing editor pipeline behavior.

## Existing Endpoints To Preserve

### Config and Presets
- `GET /api/config/options`
- `GET /api/presets`
- `GET /api/presets/{name}`

### Jobs
- `POST /api/jobs/preview`
- `POST /api/jobs`
- `GET /api/jobs/{jobId}`

### Runs
- `GET /api/runs`
- `GET /api/runs/{runId}`

### Batch
- `GET /api/batches`
- `POST /api/batches`
- `GET /api/batches/{batchId}`
- `POST /api/batches/{batchId}/submit`

`POST /api/batches` accepts optional multipart fields:
- `mapping`: JSON object where keys are CSV headers and values are target payload paths.
- `recipe_input`: JSON object merged as defaults into every row.

`POST /api/batches/{batchId}/submit` accepts optional JSON body:
- `recipe_input`: JSON object merged into row input before submission.

## Existing Shapes Already Used

### Preview
```ts
type JobPreviewResponse = {
  normalized_input: JobInput;
  job_input: JobInput;
  intents: string[];
  warnings: string[];
  plan_only: boolean;
  resolved_style: Record<string, unknown>;
  resolved_clips: ClipInput[];
  storyboard_plan?: Record<string, unknown> | null;
  retrieval_plan?: Record<string, unknown> | null;
  execution_steps: string[];
};
```

### Submit
```ts
type JobSubmitResponse = {
  run_id?: string;
  job_id?: string;
  status: string;
  warnings?: string[];
  preview?: JobPreviewResponse;
};
```

### Runs
```ts
type RunListItem = {
  run_id: string;
  job_id: string;
  status: string;
  geo?: string;
  preset_name?: string | null;
  created_at?: string;
  updated_at?: string;
  output_url?: string;
};
```

## New / Extended Endpoints Proposed

### Projects
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{projectId}`

Purpose:
- populate Home / Projects
- support future drafts, versions, and resumable sessions

### Interpret
- `POST /api/interpret`

Purpose:
- turn brief language into a normalized plan without pretending it is already a launched job
- may wrap the existing planner internally

### Recipes
- `GET /api/recipes`
- `GET /api/recipes/{recipeId}`
- `GET /api/recipes/{recipeId}/diff`

Purpose:
- expose presets as richer recipe objects
- show “what this recipe changes” in human-readable form

### Batch Schema Validation
- `POST /api/batch/validate-schema`

Purpose:
- validate CSV mapping before batch creation
- can be implemented later if client-side mapping proves insufficient

## Error Model
Keep the current error behavior:

- `errors: string[]` for validation-style failures
- `detail: string` for resource lookup failures
- `error_code: string` for machine-readable classification

## Contract Notes
- Existing job, run, and batch endpoints remain the operational truth.
- New routes should be additive so the current production flows remain valid.
- The first migration can mock `projects`, `recipes`, and `interpret` on the frontend if backend work is not ready yet.

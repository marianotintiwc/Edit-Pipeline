# Phase 1: Inventory — UGC Edit Pipeline UI

## Screen title & URL patterns

| Route | Title | Purpose |
|-------|-------|---------|
| `/` | Home / UGC Video Editor | Workspace hub, session snapshot, KPIs, cards |
| `/batch/import` | Batch assistant | Dataset import (default batch step) |
| `/batch/mapping` | Batch assistant | Schema mapping (placeholder content) |
| `/batch/validation` | Batch assistant | Validation (placeholder content) |
| `/batch/recipe` | Batch assistant | Recipe assignment (placeholder content) |
| `/batch/preview` | Batch assistant | Batch preview (split layout: config left, results right) |
| `/studio/brief` | Creative studio | Choose recipe, brief composer, clip list |
| `/studio/style` | Style lab | Creative controls, delivery settings |
| `/studio/review` | Review & submit | Preview plan, launch, open batch |
| `/runs` | Runs dashboard | Monitor jobs, track work, recover failures |
| `/library` | Library | Placeholder — recipes, brand kits |
| `/admin` | Admin | Placeholder — provider defaults |

## User job-to-be-done

1. **Studio flow:** Choose a recipe → configure creative inputs (geo, aspect ratio, music, clips) → preview plan → submit for render or plan-only.
2. **Batch flow:** Upload CSV or load batch → see preview/results → submit pending rows.
3. **Runs flow:** Monitor active jobs and recover failures.

## Success state

- **Studio:** Job submitted, run ID / job ID surfaced, user navigated to Runs.
- **Batch:** CSV parsed, rows validated, pending rows submitted; BatchProgress shows status.
- **Runs:** User sees run status and can drill down to records.

## Component tree (visual)

```
App
├── Shell (header, top-nav, alertSlot)
│   ├── Nav: Home | Studio | Batch | Runs | Library | Admin
│   └── Routes
├── HomePage
│   ├── hero-grid: Workspace hub card, Session snapshot
│   ├── kpi-grid: Active runs, Recipes, Needs review
│   └── home-grid--cards: Saved recipes, Production pulse, Project placeholder, Review queue
├── BatchPage (for /batch/*)
│   ├── SurfaceCard: Operations console + batch step NavLinks
│   ├── StepRail (numbered steps)
│   └── BatchWorkspace(activeStepId)
│       ├── [preview] batch-split-layout
│       │   ├── batch-split-layout__input: BatchUpload(externalPreview, onBatchChange)
│       │   └── batch-split-layout__results: BatchPreview | empty helper
│       └── [import|mapping|validation|recipe] BatchUpload (inline preview)
├── StudioLayout (Brief | Style | Review)
│   ├── PanelShell (left): Brief/Style/Review nav + ToolbarPills
│   ├── shell-page: StudioBriefView | StudioStyleView | StudioReviewView
│   └── PanelShell (right): Preview panel or empty state
├── StudioBriefView: PresetCards, JobForm, ClipList, Preview CTA
├── StudioStyleView: JobForm, coming-next list, Refresh CTA
├── StudioReviewView: ReviewWorkspace → ReviewPanel
└── RunsPage: SurfaceCard + MonitorWorkspace
```

## Primitives & shared components

| Component | Location | Role |
|-----------|----------|------|
| Button, Badge, Chip | primitives | Actions, status |
| SurfaceCard, PanelShell, ModalShell | primitives | Containers |
| UploadZone | primitives | Drag/drop CSV, text/hint, dragging state |
| EmptyState, StatusBanner | primitives | Empty/error/success |
| StepRail | primitives | Batch step labels |
| FormatPill | FormatPill.tsx | Ratio + platform (optional) |
| BulkActionBar | BulkActionBar.tsx | Fixed bar for batch actions |
| MediaResultCard | primitives | Ratio badge, overlay actions |
| PresetCards | PresetCards.tsx | Recipe cards with gradient, hover |
| BatchUpload | BatchUpload.tsx | CSV upload, load by ID, recent batches |
| BatchPreview | BatchPreview.tsx | Result cards with row status |
| BatchProgress | BatchProgress | Polling / submitted status |

## Data dependencies

- **Config:** `getConfigOptions()` → clipTypes, etc.
- **Presets:** `getPresets()`, `getPreset(name)` → recipe input
- **Job:** `previewJob(form)`, `submitJob(form)` → preview, run/job IDs
- **Batch:** `createBatchFromCsv`, `getBatch`, `listBatches`, `submitBatch`

## States observed (runtime)

- **Home:** Errors section with "Not Found" (API/config fallback), empty state for recipes and runs.
- **Batch preview:** Split layout visible; left: UploadZone + Load batch; right: "Upload a CSV or load a batch..." empty state.
- **Studio style:** JobForm with geo, preset, aspect ratio, music, advanced settings; right panel "No plan preview yet".
- **Batch step nav:** All 5 steps (import, mapping, validation, recipe, preview) render; mapping/validation/recipe show same BatchUpload as import (no distinct step content).

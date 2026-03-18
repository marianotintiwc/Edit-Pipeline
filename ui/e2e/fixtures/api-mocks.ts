import type { Page, Route } from "@playwright/test";

export const CONFIG_OPTIONS = {
  geos: [
    { value: "MLA", label: "Argentina (MLA)" },
    { value: "MLB", label: "Brasil (MLB)" },
  ],
  subtitleModes: [
    { value: "auto", label: "Auto subtitles" },
    { value: "manual", label: "Manual subtitles" },
    { value: "none", label: "No subtitles" },
  ],
  editPresets: [
    { value: "standard_vertical", label: "Standard vertical" },
    { value: "horizontal", label: "Horizontal" },
  ],
  clipTypes: [
    { value: "scene", label: "Talking scene" },
    { value: "broll", label: "B-roll demo" },
    { value: "endcard", label: "Endcard" },
    { value: "introcard", label: "Introcard" },
  ],
  wizardSteps: [
    { id: "preset", title: "Choose a starting point" },
    { id: "content", title: "Add clips and assets" },
    { id: "delivery", title: "Delivery settings" },
    { id: "review", title: "Review and launch" },
  ],
};

export const PRESETS = {
  items: [
    {
      name: "meli_edit_classic",
      label: "MELI Edit Classic",
      description: "Best for standard marketplace edits.",
      recommended_for: "Marketplace product videos",
    },
  ],
};

export const PRESET_DETAIL = {
  name: "meli_edit_classic",
  label: "MELI Edit Classic",
  description: "Best for standard marketplace edits.",
  recommended_for: "Marketplace product videos",
  basic_fields: ["geo", "subtitle_mode", "music_url"],
  input: {
    geo: "MLB",
    subtitle_mode: "auto",
    edit_preset: "standard_vertical",
    clips: [
      { type: "introcard", url: "https://example.com/intro.mov" },
      { type: "scene", url: "https://example.com/scene1.mp4" },
    ],
  },
};

export const JOB_PREVIEW_RESPONSE = {
  normalized_input: {
    geo: "MLB",
    subtitle_mode: "auto",
    edit_preset: "standard_vertical",
    plan_only: false,
    clips: [
      { type: "introcard", url: "https://example.com/intro.mov" },
      { type: "scene", url: "https://example.com/scene2.mp4" },
    ],
  },
  job_input: {
    geo: "MLB",
    subtitle_mode: "auto",
    edit_preset: "standard_vertical",
    plan_only: false,
    clips: [
      { type: "introcard", url: "https://example.com/intro.mov" },
      { type: "scene", url: "https://example.com/scene2.mp4" },
    ],
  },
  intents: ["assemble_edit"],
  warnings: ["Preview warning"],
  plan_only: false,
  resolved_style: {
    audio: {
      music_volume: 0.3,
      loop_music: true,
    },
  },
  resolved_clips: [
    { type: "introcard", url: "https://example.com/intro.mov" },
    { type: "scene", url: "https://example.com/scene2.mp4" },
  ],
  storyboard_plan: null,
  retrieval_plan: null,
  execution_steps: ["download_inputs", "prepare_music", "render_video", "upload_output"],
};

export const JOB_SUBMIT_RESPONSE = {
  run_id: "run-1",
  job_id: "job-1",
  status: "IN_QUEUE",
  warnings: ["Audio level is low."],
};

export const RUNS_RESPONSE = {
  items: [
    {
      run_id: "run-1",
      job_id: "job-1",
      status: "COMPLETED",
      geo: "MLB",
      preset_name: "meli_edit_classic",
      created_at: "2026-03-14T01:00:00Z",
      updated_at: "2026-03-14T01:05:00Z",
      output_url: "https://example.com/output.mp4",
    },
  ],
};

export const RUN_DETAIL_RESPONSE = {
  run_id: "run-1",
  job_id: "job-1",
  status: "COMPLETED",
  geo: "MLB",
  preset_name: "meli_edit_classic",
  created_at: "2026-03-14T01:00:00Z",
  updated_at: "2026-03-14T01:05:00Z",
  output_url: "https://example.com/output.mp4",
  logs: ["done"],
  input_snapshot: {
    geo: "MLB",
    clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
  },
};

export const JOB_STATUS_RESPONSE = {
  status: "IN_PROGRESS",
  stage: "Rendering video",
  logs: ["Downloading assets", "Rendering timeline"],
};

export const BATCH_DETAIL_READY = {
  batch_id: "batch-1",
  filename: "jobs.csv",
  status: "ready",
  total_rows: 1,
  valid_rows: 1,
  invalid_rows: 0,
  rows: [
    {
      row_number: 1,
      status: "ready",
      warnings: [],
      errors: [],
      input: {
        geo: "MLA",
        clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
        subtitle_mode: "auto",
      },
    },
  ],
};

export const BATCH_LIST_RESPONSE = {
  items: [
    {
      batch_id: "batch-1",
      filename: "jobs.csv",
      status: "ready",
      valid_rows: 1,
      invalid_rows: 0,
      updated_at: "2026-03-14T01:05:00Z",
    },
  ],
};

export const BATCH_SUBMIT_RESPONSE = {
  ...BATCH_DETAIL_READY,
  status: "completed",
  submitted_rows: 1,
  rows: [
    {
      row_number: 1,
      status: "submitted",
      run_id: "run-1",
      job_id: "job-1",
      warnings: [],
      errors: [],
    },
  ],
};

type Overrides = {
  runsResponse?: Record<string, unknown>;
  runDetailResponse?: Record<string, unknown>;
  batchGetResponse?: Record<string, unknown>;
};

async function fulfillJson(route: Route, status: number, payload: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

export async function attachApiMocks(page: Page, overrides: Overrides = {}) {
  await page.route("**/api/config/options", async (route) => {
    await fulfillJson(route, 200, CONFIG_OPTIONS);
  });
  await page.route("**/api/presets", async (route) => {
    await fulfillJson(route, 200, PRESETS);
  });
  await page.route("**/api/presets/*", async (route) => {
    await fulfillJson(route, 200, PRESET_DETAIL);
  });
  await page.route("**/api/jobs/preview", async (route) => {
    await fulfillJson(route, 200, JOB_PREVIEW_RESPONSE);
  });
  await page.route("**/api/jobs", async (route) => {
    if (route.request().method() === "POST") {
      await fulfillJson(route, 202, JOB_SUBMIT_RESPONSE);
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/jobs/*", async (route) => {
    if (route.request().url().endsWith("/api/jobs/preview")) {
      await route.fallback();
      return;
    }
    await fulfillJson(route, 200, JOB_STATUS_RESPONSE);
  });
  await page.route("**/api/runs", async (route) => {
    await fulfillJson(route, 200, overrides.runsResponse ?? RUNS_RESPONSE);
  });
  await page.route("**/api/runs/*", async (route) => {
    await fulfillJson(route, 200, overrides.runDetailResponse ?? RUN_DETAIL_RESPONSE);
  });
  await page.route("**/api/batches", async (route) => {
    const method = route.request().method();
    if (method === "POST") {
      await fulfillJson(route, 200, BATCH_DETAIL_READY);
      return;
    }
    if (method === "GET") {
      await fulfillJson(route, 200, BATCH_LIST_RESPONSE);
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/batches/*/submit", async (route) => {
    await fulfillJson(route, 200, BATCH_SUBMIT_RESPONSE);
  });
  await page.route("**/api/batches/*", async (route) => {
    await fulfillJson(route, 200, overrides.batchGetResponse ?? BATCH_DETAIL_READY);
  });
}

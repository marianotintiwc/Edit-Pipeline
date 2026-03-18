import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const apiMocks = vi.hoisted(() => ({
  createBatchFromCsv: vi.fn(),
  getBatch: vi.fn(),
  listBatches: vi.fn(),
  getPresets: vi.fn(),
  getPreset: vi.fn(),
  getConfigOptions: vi.fn(),
  listProfiles: vi.fn(),
  previewJob: vi.fn(),
  submitJob: vi.fn(),
  submitBatch: vi.fn(),
  getJobStatus: vi.fn(),
  listRuns: vi.fn(),
  getRun: vi.fn(),
}));

vi.mock("./api", () => ({
  createBatchFromCsv: apiMocks.createBatchFromCsv,
  getBatch: apiMocks.getBatch,
  listBatches: apiMocks.listBatches,
  getPresets: apiMocks.getPresets,
  getPreset: apiMocks.getPreset,
  getConfigOptions: apiMocks.getConfigOptions,
  listProfiles: apiMocks.listProfiles,
  previewJob: apiMocks.previewJob,
  submitJob: apiMocks.submitJob,
  submitBatch: apiMocks.submitBatch,
  getJobStatus: apiMocks.getJobStatus,
  listRuns: apiMocks.listRuns,
  getRun: apiMocks.getRun,
}));

const CONFIG_OPTIONS = {
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

const PRESETS = {
  items: [
    {
      name: "meli_edit_classic",
      label: "MELI Edit Classic",
      description: "Best for standard marketplace edits.",
      recommended_for: "Marketplace product videos",
    },
  ],
};

beforeEach(() => {
  apiMocks.getPresets.mockResolvedValue(PRESETS);
  apiMocks.getConfigOptions.mockResolvedValue(CONFIG_OPTIONS);
  apiMocks.listProfiles.mockResolvedValue({ items: [] });
  apiMocks.getPreset.mockResolvedValue({
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
  });
  apiMocks.submitJob.mockResolvedValue({
    run_id: "run-1",
    job_id: "job-1",
    status: "IN_QUEUE",
    warnings: ["Audio level is low."],
  });
  apiMocks.previewJob.mockResolvedValue({
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
  });
  apiMocks.getJobStatus.mockResolvedValue({
    status: "IN_PROGRESS",
    stage: "Rendering video",
    logs: ["Downloading assets", "Rendering timeline"],
  });
  apiMocks.listRuns.mockResolvedValue({
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
  });
  apiMocks.getRun.mockResolvedValue({
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
  });
  apiMocks.createBatchFromCsv.mockResolvedValue({
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
  });
  apiMocks.getBatch.mockResolvedValue({
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
      },
    ],
  });
  apiMocks.listBatches.mockResolvedValue({
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
  });
  apiMocks.submitBatch.mockResolvedValue({
    batch_id: "batch-1",
    filename: "jobs.csv",
    status: "completed",
    total_rows: 1,
    valid_rows: 1,
    invalid_rows: 0,
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
  });
});

describe("App", () => {
  it("starts from the new Home shell and previews a Studio run before launch", async () => {
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Studio" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Batch" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Runs" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Build, style, scale, and ship videos" })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Studio" }));
    expect(await screen.findByText("Choose a starting point")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Use MELI Edit Classic" }));
    expect(screen.getAllByText("Best for standard marketplace edits.").length).toBeGreaterThan(0);
    expect(await screen.findByLabelText("Market / country configuration")).toHaveValue("MLB");
    expect(screen.getAllByLabelText(/Clip URL/i)).toHaveLength(2);

    const clipUrls = screen.getAllByLabelText(/Clip URL/i);
    await user.clear(clipUrls[1]);
    await user.type(clipUrls[1], "https://example.com/scene2.mp4");

    await user.click(screen.getByRole("button", { name: "Preview render plan" }));

    await waitFor(() => {
      expect(apiMocks.previewJob).toHaveBeenCalledWith(
        expect.objectContaining({
          geo: "MLB",
          clips: expect.arrayContaining([
            expect.objectContaining({ url: "https://example.com/scene2.mp4" }),
          ]),
        }),
      );
    });
    expect(await screen.findByRole("heading", { name: "Review & submit" })).toBeInTheDocument();
    expect(screen.getByText("Submission preview")).toBeInTheDocument();
    expect(screen.getByText("Preview warning")).toBeInTheDocument();
    expect(screen.getByText("download_inputs")).toBeInTheDocument();
    expect(screen.getAllByText("2 resolved clips").length).toBeGreaterThan(0);
  });

  it("submits from Studio review and lets operators continue into Runs and Batch", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(await screen.findByRole("link", { name: "Studio" }));
    await user.click(await screen.findByRole("button", { name: "Use MELI Edit Classic" }));

    const clipUrls = await screen.findAllByLabelText(/Clip URL/i);
    await user.clear(clipUrls[1]);
    await user.type(clipUrls[1], "https://example.com/scene2.mp4");

    await user.click(screen.getByRole("button", { name: "Preview render plan" }));
    expect(await screen.findByText("Submission preview")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Launch run" }));

    await waitFor(() => {
      expect(apiMocks.submitJob).toHaveBeenCalledWith(
        expect.objectContaining({
          geo: "MLB",
          clips: expect.arrayContaining([
            expect.objectContaining({ url: "https://example.com/scene2.mp4" }),
          ]),
        }),
      );
    });

    expect(await screen.findByText("Run launched")).toBeInTheDocument();
    expect(screen.getByText("Audio level is low.")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Runs" }));
    expect(await screen.findByText("Recent runs")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open run-1" }));
    expect(await screen.findByText("Rendering video")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Batch" }));
    expect(await screen.findByText("Load existing batch")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Batch ID"), "batch-1");
    await user.click(screen.getByRole("button", { name: "Load batch" }));
    expect(await screen.findByText("1 valid row")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Runs" }));
    expect(await screen.findByText("Recent runs")).toBeInTheDocument();
    expect(screen.getByText("https://example.com/output.mp4")).toBeInTheDocument();
  });

  it("blocks preview with zero clips and exposes batch through the new shell", async () => {
    const user = userEvent.setup();

    render(<App />);

    await user.click(await screen.findByRole("link", { name: "Studio" }));
    await user.click(await screen.findByRole("button", { name: "Use MELI Edit Classic" }));

    const removeButtons = await screen.findAllByRole("button", { name: "Remove clip" });
    await user.click(removeButtons[1]);
    await user.click(screen.getByRole("button", { name: "Remove clip" }));

    expect(screen.getByRole("button", { name: "Preview render plan" })).toBeDisabled();
    expect(screen.getByText(/No clips added yet/)).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Batch" }));

    expect(await screen.findByText("Drop CSV or click to upload")).toBeInTheDocument();
    expect(screen.getByText("Load existing batch")).toBeInTheDocument();
  });
});

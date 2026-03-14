import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createBatchFromCsv,
  getBatch,
  getConfigOptions,
  getJobStatus,
  getPreset,
  getPresets,
  getRun,
  listBatches,
  listRuns,
  previewJob,
  submitBatch,
  submitJob,
} from "./api";

describe("ui api client", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("submits jobs to the backend", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ run_id: "run-1", job_id: "job-1", status: "IN_QUEUE" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await submitJob({
      geo: "MLA",
      clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
      subtitle_mode: "auto",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/jobs",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
    expect(result.job_id).toBe("job-1");
  });

  it("requests a preview before launch", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          normalized_input: {
            geo: "MLA",
            clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
          },
          job_input: {
            geo: "MLA",
            clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
          },
          intents: ["assemble_edit"],
          warnings: [],
          plan_only: false,
          resolved_style: {},
          resolved_clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
          storyboard_plan: null,
          retrieval_plan: null,
          execution_steps: ["download_inputs"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const result = await previewJob({
      geo: "MLA",
      clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/jobs/preview",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
    expect(result.execution_steps).toContain("download_inputs");
  });

  it("loads config, presets, and preset details", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            geos: [{ value: "MLA", label: "Argentina (MLA)" }],
            subtitleModes: [{ value: "auto", label: "Auto subtitles" }],
            editPresets: [{ value: "standard_vertical", label: "Standard vertical" }],
            clipTypes: [{ value: "scene", label: "Talking scene" }],
            wizardSteps: [{ id: "preset", title: "Choose a starting point" }],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [{ name: "meli_edit_classic", label: "Classic" }] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            name: "meli_edit_classic",
            label: "Classic",
            description: "Best for standard marketplace edits.",
            recommended_for: "Marketplace product videos",
            basic_fields: ["geo"],
            input: { geo: "MLB", clips: [] },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );

    const config = await getConfigOptions();
    const presets = await getPresets();
    const preset = await getPreset("meli_edit_classic");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.example.com/api/config/options",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.example.com/api/presets",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://api.example.com/api/presets/meli_edit_classic",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(config.geos[0].value).toBe("MLA");
    expect(presets.items[0].name).toBe("meli_edit_classic");
    expect(preset.input.geo).toBe("MLB");
  });

  it("surfaces backend validation errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ errors: ["clips[0].url is required"] }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      submitJob({
        clips: [{ type: "scene", url: "" }],
      }),
    ).rejects.toThrow("clips[0].url is required");
  });

  it("loads job status payloads", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "COMPLETED", logs: ["done"], stage: "Finished" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getJobStatus("job-123");

    expect(result.status).toBe("COMPLETED");
    expect(result.logs).toEqual(["done"]);
  });

  it("loads saved run history and a single run", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [{ run_id: "run-1", job_id: "job-1", status: "COMPLETED" }],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "run-1",
            job_id: "job-1",
            status: "COMPLETED",
            output_url: "https://example.com/output.mp4",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );

    const runs = await listRuns();
    const run = await getRun("run-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.example.com/api/runs",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.example.com/api/runs/run-1",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(runs.items[0].run_id).toBe("run-1");
    expect(run.output_url).toBe("https://example.com/output.mp4");
  });

  it("creates, lists, loads, and submits CSV batches", async () => {
    const csvFile = new File(
      [
        "geo,subtitle_mode,clips[0].type,clips[0].url\n" +
          "MLA,auto,scene,https://example.com/scene1.mp4\n",
      ],
      "jobs.csv",
      { type: "text/csv" },
    );
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
                  subtitle_mode: "auto",
                  clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
                },
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [
              {
                batch_id: "batch-1",
                filename: "jobs.csv",
                status: "ready",
                total_rows: 1,
                valid_rows: 1,
                invalid_rows: 0,
                submitted_rows: 0,
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
                  subtitle_mode: "auto",
                  clips: [{ type: "scene", url: "https://example.com/scene1.mp4" }],
                },
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );

    const createdBatch = await createBatchFromCsv(csvFile);
    const batches = await listBatches();
    const fetchedBatch = await getBatch("batch-1");
    const submittedBatch = await submitBatch("batch-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.example.com/api/batches",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: expect.any(FormData),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.example.com/api/batches",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://api.example.com/api/batches/batch-1",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "https://api.example.com/api/batches/batch-1/submit",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recipe_input: null }),
      }),
    );
    expect(createdBatch.batch_id).toBe("batch-1");
    expect(batches.items[0].batch_id).toBe("batch-1");
    expect(fetchedBatch.rows[0].status).toBe("ready");
    expect(submittedBatch.rows[0].run_id).toBe("run-1");
  });

  it("sends mapping and recipe defaults when creating a batch", async () => {
    const csvFile = new File(["geo\nMLA\n"], "jobs.csv", { type: "text/csv" });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          batch_id: "batch-2",
          filename: "jobs.csv",
          status: "ready",
          total_rows: 1,
          valid_rows: 1,
          invalid_rows: 0,
          rows: [{ row_number: 1, status: "ready", warnings: [], errors: [], input: { geo: "MLA" } }],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await createBatchFromCsv(csvFile, {
      mapping: { geo: "geo" },
      recipeInput: { subtitle_mode: "auto" },
    });

    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const formData = requestInit.body as FormData;
    expect(formData.get("mapping")).toBe(JSON.stringify({ geo: "geo" }));
    expect(formData.get("recipe_input")).toBe(JSON.stringify({ subtitle_mode: "auto" }));
  });
});

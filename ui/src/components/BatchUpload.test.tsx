import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BatchUpload } from "./BatchUpload";

describe("BatchUpload", () => {
  it("uploads a CSV, shows row validation, and submits valid rows", async () => {
    const user = userEvent.setup();
    const listBatches = vi.fn().mockResolvedValue({
      items: [
        {
          batch_id: "batch-1",
          filename: "jobs.csv",
          status: "ready",
          total_rows: 2,
          valid_rows: 1,
          invalid_rows: 1,
        },
      ],
    });
    const createBatch = vi.fn().mockResolvedValue({
      batch_id: "batch-1",
      filename: "jobs.csv",
      status: "ready",
      total_rows: 2,
      valid_rows: 1,
      invalid_rows: 1,
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
        {
          row_number: 2,
          status: "blocked_by_validation",
          warnings: [],
          errors: ["clips[0].url is required and must be a string"],
          input: {
            geo: "MLB",
            subtitle_mode: "auto",
            clips: [{ type: "scene", url: "" }],
          },
        },
      ],
    });
    const getBatch = vi.fn().mockResolvedValue({
      batch_id: "batch-1",
      filename: "jobs.csv",
      status: "ready",
      total_rows: 2,
      valid_rows: 1,
      invalid_rows: 1,
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
        {
          row_number: 2,
          status: "blocked_by_validation",
          warnings: [],
          errors: ["clips[0].url is required and must be a string"],
        },
      ],
    });
    const submitBatch = vi.fn().mockResolvedValue({
      batch_id: "batch-1",
      filename: "jobs.csv",
      status: "partial_success",
      total_rows: 2,
      valid_rows: 1,
      invalid_rows: 1,
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
        {
          row_number: 2,
          status: "blocked_by_validation",
          warnings: [],
          errors: ["clips[0].url is required and must be a string"],
        },
      ],
    });

    render(
      <BatchUpload
        createBatch={createBatch}
        getBatch={getBatch}
        listBatches={listBatches}
        submitBatch={submitBatch}
      />,
    );

    expect(await screen.findByText("Recent batches")).toBeInTheDocument();

    const input = screen.getByLabelText("CSV batch file");
    const file = new File(
      [
        "geo,subtitle_mode,clips[0].type,clips[0].url\n" +
          "MLA,auto,scene,https://example.com/scene1.mp4\n" +
          "MLB,auto,scene,\n",
      ],
      "jobs.csv",
      { type: "text/csv" },
    );

    await user.upload(input, file);

    await waitFor(() => {
      expect(createBatch).toHaveBeenCalledWith(file);
    });

    expect(await screen.findByText("1 valid row")).toBeInTheDocument();
    expect(screen.getByText("1 row needs attention")).toBeInTheDocument();
    expect(screen.getByText("clips[0].url is required and must be a string")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Batch ID"));
    await user.type(screen.getByLabelText("Batch ID"), "batch-1");
    await user.click(screen.getByRole("button", { name: "Load batch" }));

    await waitFor(() => {
      expect(getBatch).toHaveBeenCalledWith("batch-1");
    });

    await user.click(screen.getByRole("button", { name: "Submit pending rows" }));

    await waitFor(() => {
      expect(submitBatch).toHaveBeenCalledWith("batch-1");
    });

    expect(await screen.findByText("1 row submitted")).toBeInTheDocument();
    expect(screen.getByText("run-1")).toBeInTheDocument();
  });

  it("polls the saved batch after submission while rows are still processing", async () => {
    const user = userEvent.setup();
    const listBatches = vi.fn().mockResolvedValue({ items: [] });
    const createBatch = vi.fn().mockResolvedValue({
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
    });
    const getBatch = vi
      .fn()
      .mockResolvedValueOnce({
        batch_id: "batch-1",
        filename: "jobs.csv",
        status: "in_progress",
        total_rows: 1,
        valid_rows: 1,
        invalid_rows: 0,
        submitted_rows: 1,
        rows: [
          {
            row_number: 1,
            status: "completed",
            run_id: "run-1",
            job_id: "job-1",
            warnings: [],
            errors: [],
          },
        ],
      });
    const submitBatch = vi.fn().mockResolvedValue({
      batch_id: "batch-1",
      filename: "jobs.csv",
      status: "in_progress",
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

    render(
      <BatchUpload
        createBatch={createBatch}
        getBatch={getBatch}
        listBatches={listBatches}
        pollIntervalMs={1}
        submitBatch={submitBatch}
      />,
    );

    const input = screen.getByLabelText("CSV batch file");
    const file = new File(
      ["geo,subtitle_mode,clips[0].type,clips[0].url\nMLA,auto,scene,https://example.com/scene1.mp4\n"],
      "jobs.csv",
      { type: "text/csv" },
    );

    await user.upload(input, file);
    await user.click(await screen.findByRole("button", { name: "Submit pending rows" }));

    await waitFor(() => {
      expect(getBatch).toHaveBeenCalledWith("batch-1");
    });
    expect((await screen.findAllByText("Status: completed")).length).toBeGreaterThan(0);
  });

  it("keeps the submit action available when failed rows can be retried", async () => {
    const user = userEvent.setup();
    const listBatches = vi.fn().mockResolvedValue({ items: [] });
    const createBatch = vi.fn().mockResolvedValue({
      batch_id: "batch-1",
      filename: "jobs.csv",
      status: "ready",
      total_rows: 2,
      valid_rows: 2,
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
        {
          row_number: 2,
          status: "ready",
          warnings: [],
          errors: [],
          input: {
            geo: "MLB",
            subtitle_mode: "auto",
            clips: [{ type: "scene", url: "https://example.com/scene2.mp4" }],
          },
        },
      ],
    });
    const getBatch = vi.fn().mockResolvedValue({
      batch_id: "batch-1",
      filename: "jobs.csv",
      status: "partial_success",
      total_rows: 2,
      valid_rows: 2,
      invalid_rows: 0,
      submitted_rows: 1,
      rows: [
        { row_number: 1, status: "submitted", run_id: "run-1", job_id: "job-1", warnings: [], errors: [] },
        {
          row_number: 2,
          status: "failed",
          warnings: [],
          errors: ["RunPod unavailable"],
          input: {
            geo: "MLB",
            subtitle_mode: "auto",
            clips: [{ type: "scene", url: "https://example.com/scene2.mp4" }],
          },
        },
      ],
    });
    const submitBatch = vi
      .fn()
      .mockResolvedValueOnce({
        batch_id: "batch-1",
        filename: "jobs.csv",
        status: "partial_success",
        total_rows: 2,
        valid_rows: 2,
        invalid_rows: 0,
        submitted_rows: 1,
        rows: [
          { row_number: 1, status: "submitted", run_id: "run-1", job_id: "job-1", warnings: [], errors: [] },
          {
            row_number: 2,
            status: "failed",
            warnings: [],
            errors: ["RunPod unavailable"],
            input: {
              geo: "MLB",
              subtitle_mode: "auto",
              clips: [{ type: "scene", url: "https://example.com/scene2.mp4" }],
            },
          },
        ],
      })
      .mockResolvedValueOnce({
        batch_id: "batch-1",
        filename: "jobs.csv",
        status: "completed",
        total_rows: 2,
        valid_rows: 2,
        invalid_rows: 0,
        submitted_rows: 2,
        rows: [
          { row_number: 1, status: "submitted", run_id: "run-1", job_id: "job-1", warnings: [], errors: [] },
          { row_number: 2, status: "submitted", run_id: "run-2", job_id: "job-2", warnings: [], errors: [] },
        ],
      });

    render(
      <BatchUpload
        createBatch={createBatch}
        getBatch={getBatch}
        listBatches={listBatches}
        submitBatch={submitBatch}
      />,
    );

    const input = screen.getByLabelText("CSV batch file");
    const file = new File(
      ["geo,subtitle_mode,clips[0].type,clips[0].url\nMLA,auto,scene,https://example.com/scene1.mp4\nMLB,auto,scene,https://example.com/scene2.mp4\n"],
      "jobs.csv",
      { type: "text/csv" },
    );

    await user.upload(input, file);
    await user.click(await screen.findByRole("button", { name: "Submit pending rows" }));

    expect(await screen.findByRole("button", { name: "Submit pending rows" })).toBeInTheDocument();
  });
});

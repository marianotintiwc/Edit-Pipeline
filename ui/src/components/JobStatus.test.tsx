import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { JobStatus } from "./JobStatus";

describe("JobStatus", () => {
  it("loads the latest status and logs for a job", async () => {
    const loadStatus = vi.fn().mockResolvedValue({
      status: "COMPLETED",
      stage: "Finished",
      logs: ["done"],
      output: {
        output_url: "https://example.com/out.mp4",
      },
    });

    render(<JobStatus jobId="job-123" loadStatus={loadStatus} />);

    await waitFor(() => {
      expect(screen.getByText("Completed")).toBeInTheDocument();
    });
    expect(loadStatus).toHaveBeenCalledWith("job-123");
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getByText("https://example.com/out.mp4")).toBeInTheDocument();
  });

  it("shows an actionable error when the first status refresh fails", async () => {
    const loadStatus = vi.fn().mockRejectedValue(new Error("API unavailable"));

    render(<JobStatus jobId="job-123" loadStatus={loadStatus} />);

    await waitFor(() => {
      expect(screen.getByText("We could not load the latest run status.")).toBeInTheDocument();
    });
    expect(screen.getByText("API unavailable")).toBeInTheDocument();
  });

  it("stops polling when the job reaches a cancelled terminal state", async () => {
    const loadStatus = vi.fn().mockResolvedValue({
      status: "CANCELLED",
      stage: "Stopped by operator",
      logs: ["cancelled"],
    });

    render(<JobStatus jobId="job-123" loadStatus={loadStatus} />);

    await waitFor(() => {
      expect(screen.getByText("Cancelled")).toBeInTheDocument();
    });
    await new Promise((resolve) => window.setTimeout(resolve, 50));

    expect(loadStatus).toHaveBeenCalledTimes(1);
  });
});

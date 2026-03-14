import { useEffect, useState } from "react";

import { getJobStatus } from "../api";
import type { JobStatusResponse } from "../types";

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"]);

interface JobStatusProps {
  jobId: string;
  loadStatus?: (jobId: string) => Promise<JobStatusResponse | undefined>;
}

export function JobStatus({
  jobId,
  loadStatus = getJobStatus,
}: JobStatusProps) {
  const [status, setStatus] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const statusLabel =
    status?.status
      ?.toLowerCase()
      .split("_")
      .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
      .join(" ") ?? null;

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const refresh = async () => {
      try {
        const nextStatus = await loadStatus(jobId);
        if (cancelled || !nextStatus) {
          return;
        }

        setError(null);
        setStatus(nextStatus);
        if (!TERMINAL_STATUSES.has(nextStatus.status)) {
          timer = window.setTimeout(refresh, 2500);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load job status");
        }
      }
    };

    void refresh();

    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [jobId, loadStatus]);

  if (!status && !error) {
    return <p>Loading latest job status...</p>;
  }

  return (
    <section>
      <h2>Job status</h2>
      {error ? (
        <>
          <p>We could not load the latest run status.</p>
          <p>{error}</p>
        </>
      ) : null}
      {statusLabel ? <p>{statusLabel}</p> : null}
      {status?.stage ? <p>{status.stage}</p> : null}
      {status?.logs?.length ? (
        <ul>
          {status.logs.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
      {status?.output?.output_url ? <p>{status.output.output_url}</p> : null}
    </section>
  );
}

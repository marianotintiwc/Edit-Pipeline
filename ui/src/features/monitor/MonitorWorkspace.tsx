import { Link } from "react-router-dom";
import { useEffect, useState } from "react";

import { cancelRun as cancelRunApi, getRun as getRunApi, listRuns as listRunsApi } from "../../api";
import { JobStatus } from "../../components/JobStatus";
import { Button, EmptyState } from "../../components/primitives";
import type { RunDetail, RunListItem } from "../../types";

const ACTIVE_RUN_STATUSES = new Set([
  "submitted",
  "queued",
  "in_progress",
  "IN_QUEUE",
  "IN_PROGRESS",
]);

interface MonitorWorkspaceProps {
  initialJobId?: string;
  initialRunId?: string;
  initialRecordId?: string;
}

export function MonitorWorkspace({ initialJobId, initialRunId, initialRecordId }: MonitorWorkspaceProps) {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const loadRuns = async () => {
      setLoading(true);
      try {
        const response = await listRunsApi();
        if (!active) {
          return;
        }
        setRuns(response.items);
        const preferredRun =
          response.items.find((run) => run.run_id === initialRunId) ?? response.items[0] ?? null;
        if (preferredRun?.run_id) {
          const detail = await getRunApi(preferredRun.run_id);
          if (active) {
            setSelectedRun(detail);
          }
        } else {
          setSelectedRun(null);
        }
        setError(null);
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load runs");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadRuns();

    return () => {
      active = false;
    };
  }, [initialRunId]);

  const handleOpenRun = async (runId: string) => {
    try {
      const detail = await getRunApi(runId);
      setSelectedRun(detail);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load the selected run");
    }
  };

  const handleCancelRun = async (runId: string) => {
    if (!window.confirm("Cancel this run? The job will be stopped.")) {
      return;
    }
    try {
      await cancelRunApi(runId);
      const response = await listRunsApi();
      setRuns(response.items);
      const run = response.items.find((r) => r.run_id === runId);
      if (run) {
        const detail = await getRunApi(runId);
        setSelectedRun(detail);
      }
      setError(null);
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Failed to cancel run");
    }
  };

  return (
    <section aria-labelledby="monitor-workspace-title">
      <h2 id="monitor-workspace-title">Monitor runs</h2>
      <p>Recent runs</p>
      {/* Researched Linear/Vercel 2026 → loading state with aria-busy for accessibility */}
      {loading ? (
        <p aria-busy="true" className="helper">
          Loading recent runs…
        </p>
      ) : null}
      {error ? <p className="helper">{error}</p> : null}
      {runs.length === 0 && !loading ? (
        <EmptyState
          title="No runs yet"
          description="Start a video project in Studio or submit a batch to see runs here."
          action={
            <Link to="/studio/brief">
              <Button variant="secondary" style={{ marginTop: "var(--space-2)" }}>
                Start in Studio
              </Button>
            </Link>
          }
        />
      ) : null}
      {runs.map((run) => (
        <article key={run.run_id}>
          <p>{run.run_id}</p>
          <p>{run.status}</p>
          <div className="button-row">
            <Button variant="secondary" onClick={() => void handleOpenRun(run.run_id)}>
              Open {run.run_id}
            </Button>
            {ACTIVE_RUN_STATUSES.has(run.status) ? (
              <Button
                variant="ghost"
                onClick={() => void handleCancelRun(run.run_id)}
                aria-label={`Cancel run ${run.run_id}`}
              >
                Cancel run
              </Button>
            ) : null}
            <Link to={`/runs/${run.run_id}`}>
              <Button variant="ghost">Permalink</Button>
            </Link>
            <Link to={`/runs/${run.run_id}/records/${run.job_id}`}>
              <Button variant="ghost">Record view</Button>
            </Link>
          </div>
        </article>
      ))}

      {selectedRun ? (
        <section>
          <h3>Selected run</h3>
          <p>{selectedRun.run_id}</p>
          {initialRecordId ? <p className="helper">Focused record: {initialRecordId}</p> : null}
          {selectedRun.output_url ? <p>{selectedRun.output_url}</p> : null}
          {ACTIVE_RUN_STATUSES.has(selectedRun.status) ? (
            <div className="button-row" style={{ marginBottom: "var(--space-2)" }}>
              <Button
                variant="ghost"
                onClick={() => void handleCancelRun(selectedRun.run_id)}
                aria-label={`Cancel run ${selectedRun.run_id}`}
              >
                Cancel run
              </Button>
            </div>
          ) : null}
          <JobStatus jobId={selectedRun.job_id ?? initialJobId ?? ""} />
        </section>
      ) : initialJobId ? (
        <JobStatus jobId={initialJobId} />
      ) : null}
    </section>
  );
}

import { Link } from "react-router-dom";
import { useEffect, useState } from "react";

import { getRun as getRunApi, listRuns as listRunsApi } from "../../api";
import { JobStatus } from "../../components/JobStatus";
import { Button, EmptyState } from "../../components/primitives";
import type { RunDetail, RunListItem } from "../../types";

interface MonitorWorkspaceProps {
  initialJobId?: string;
  initialRunId?: string;
}

export function MonitorWorkspace({ initialJobId, initialRunId }: MonitorWorkspaceProps) {
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
          <Button variant="secondary" onClick={() => void handleOpenRun(run.run_id)}>
            Open {run.run_id}
          </Button>
        </article>
      ))}

      {selectedRun ? (
        <section>
          <h3>Selected run</h3>
          <p>{selectedRun.run_id}</p>
          {selectedRun.output_url ? <p>{selectedRun.output_url}</p> : null}
          <JobStatus jobId={selectedRun.job_id ?? initialJobId ?? ""} />
        </section>
      ) : initialJobId ? (
        <JobStatus jobId={initialJobId} />
      ) : null}
    </section>
  );
}

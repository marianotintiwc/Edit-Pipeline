import type { JobSubmitResponse } from "../types";
import { MonitorWorkspace } from "../features/monitor/MonitorWorkspace";
import { EmptyState, SurfaceCard } from "../components/primitives";

interface RunsPageProps {
  latestJobResult: JobSubmitResponse | null;
}

export function RunsPage({ latestJobResult }: RunsPageProps) {
  return (
    <div className="runs-layout">
      <SurfaceCard>
        <span className="micro-label">Runs dashboard</span>
        <h2>Track active work and recover failures</h2>
        <p className="helper">
          The first migration keeps the existing run monitor intact, then layers a clearer dashboard
          around it so operators can move from creation to diagnosis without changing tools.
        </p>
        {latestJobResult ? (
          <p className="helper">
            Latest handoff: {latestJobResult.run_id ?? latestJobResult.job_id ?? latestJobResult.status}
          </p>
        ) : (
          <EmptyState
            title="No live handoff yet"
            description="As soon as Studio launches a run, this page becomes the operational follow-up surface."
          />
        )}
      </SurfaceCard>

      <MonitorWorkspace initialJobId={latestJobResult?.job_id} initialRunId={latestJobResult?.run_id} />
    </div>
  );
}

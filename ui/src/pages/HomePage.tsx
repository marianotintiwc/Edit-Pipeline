import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listRuns } from "../api";
import type { JobSubmitResponse, PresetListItem, RunListItem } from "../types";
import { Badge, Button, EmptyState, SurfaceCard, ToolbarPill } from "../components/primitives";

interface HomePageProps {
  presets: PresetListItem[];
  latestJobResult: JobSubmitResponse | null;
}

export function HomePage({ presets, latestJobResult }: HomePageProps) {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadRuns = async () => {
      try {
        const response = await listRuns();
        if (!cancelled) {
          setRuns(response.items);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load run snapshot");
        }
      }
    };

    void loadRuns();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeRuns = runs.filter((run) => !["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"].includes(run.status));

  return (
    <div className="shell-page">
      <section className="hero-grid">
        <SurfaceCard>
          <span className="section-header">Workspace hub</span>
          <h2>Start in Studio, keep Batch and Runs close</h2>
          <p className="helper">
            The product is shifting from a flat operator console into a creative-first shell. Use
            Studio for authoring and review, then drop into Batch or Runs only when the workflow
            becomes operational.
          </p>
          <div className="button-row">
            <Link to="/studio/brief">
              <Button>New video project</Button>
            </Link>
            <Link to="/batch/import">
              <Button variant="secondary">Open batch assistant</Button>
            </Link>
            <Link to="/runs">
              <Button variant="ghost">Review active runs</Button>
            </Link>
          </div>
        </SurfaceCard>

        <SurfaceCard muted>
          <span className="section-header">Session snapshot</span>
          <h3>Latest launch</h3>
          {latestJobResult ? (
            <div className="surface-stack">
              <Badge tone={latestJobResult.status === "PLAN_ONLY" ? "warning" : "success"}>
                {latestJobResult.status}
              </Badge>
              {latestJobResult.run_id ? <p>Run: {latestJobResult.run_id}</p> : null}
              {latestJobResult.job_id ? <p>Job: {latestJobResult.job_id}</p> : null}
            </div>
          ) : (
            <EmptyState
              title="No launch yet"
              description="Your latest render or plan-only session will appear here after the first Studio submit."
              action={
                <Link to="/studio/brief">
                  <Button variant="secondary" style={{ marginTop: "var(--space-2)" }}>
                    New video project
                  </Button>
                </Link>
              }
            />
          )}
        </SurfaceCard>
      </section>

      <section className="kpi-grid">
        <SurfaceCard compact>
          <p className="micro-label">Active runs</p>
          <p className="kpi-card__value">{activeRuns.length}</p>
          <p className="helper">Runs that still need monitoring or intervention.</p>
        </SurfaceCard>
        <SurfaceCard compact>
          <p className="micro-label">Recipes available</p>
          <p className="kpi-card__value">{presets.length}</p>
          <p className="helper">Presets that can seed a Studio session today.</p>
        </SurfaceCard>
        <SurfaceCard compact>
          <p className="micro-label">Needs review</p>
          <p className="kpi-card__value">{runs.slice(0, 3).length}</p>
          <p className="helper">Temporary proxy until record-level review queues are exposed.</p>
        </SurfaceCard>
      </section>

      <section className="home-grid home-grid--cards">
        <SurfaceCard>
          <span className="section-header">Recent recipes</span>
          <h3>Saved recipes</h3>
          {presets.length ? (
            <div className="surface-stack">
              {presets.slice(0, 4).map((preset) => (
                <div key={preset.name}>
                  <ToolbarPill>{preset.label}</ToolbarPill>
                  {preset.description ? <p>{preset.description}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Recipes are loading"
              description="The preset catalog will surface here so users enter by recipe instead of raw payload."
            />
          )}
        </SurfaceCard>

        <SurfaceCard>
          <span className="section-header">Active runs rail</span>
          <h3>Production pulse</h3>
          {error ? <p>{error}</p> : null}
          {runs.length ? (
            <div className="surface-stack">
              {runs.slice(0, 4).map((run) => (
                <div key={run.run_id}>
                  <div className="button-row">
                    <ToolbarPill>{run.run_id}</ToolbarPill>
                    <Badge tone={run.status === "COMPLETED" ? "success" : "warning"}>{run.status}</Badge>
                  </div>
                  {run.preset_name ? <p className="helper">{run.preset_name}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No runs yet"
              description="Once runs exist, Home becomes the workspace hub for monitoring and resuming work."
            />
          )}
        </SurfaceCard>

        <SurfaceCard>
          <span className="section-header">Recent projects</span>
          <h3>Project system placeholder</h3>
          <EmptyState
            title="Project abstraction is next"
            description="The shell is ready for Project -> Version -> Recipe -> Run, even though projects are not persisted yet."
          />
        </SurfaceCard>

        <SurfaceCard>
          <span className="section-header">Needs review queue</span>
          <h3>Record review placeholder</h3>
          <EmptyState
            title="Review queue not exposed yet"
            description="This card marks the intended surface for approve, reject, retry, and patch workflows once record-level APIs arrive."
          />
        </SurfaceCard>
      </section>
    </div>
  );
}

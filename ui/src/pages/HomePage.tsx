import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listRuns } from "../api";
import type { JobInput, JobSubmitResponse, PresetListItem, RunListItem } from "../types";
import { CURATED_RECIPES, type Recipe } from "../data/recipes";
import { Badge, Button, EmptyState, SurfaceCard, ToolbarPill } from "../components/primitives";
import { RecipeCards } from "../components/RecipeCards";

interface HomePageProps {
  presets: PresetListItem[];
  isPresetsLoading?: boolean;
  latestJobResult: JobSubmitResponse | null;
  onApplyRecipe?: (input: Partial<JobInput>) => void;
}

export function HomePage({
  presets,
  isPresetsLoading = false,
  latestJobResult,
  onApplyRecipe,
}: HomePageProps) {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isRunsLoading, setIsRunsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const loadRuns = async () => {
      setIsRunsLoading(true);
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
      } finally {
        if (!cancelled) {
          setIsRunsLoading(false);
        }
      }
    };

    void loadRuns();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeRuns = runs.filter((run) => !["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"].includes(run.status));

  const handleRecipeSelect = (recipe: Recipe) => {
    if (onApplyRecipe) {
      onApplyRecipe(recipe.input);
    }
    navigate("/studio/brief");
  };

  return (
    <div className="shell-page">
      <section className="hero-grid">
        <SurfaceCard>
          <span className="section-header">Creator workspace</span>
          <h2>Build, style, scale, and ship videos</h2>
          <p className="helper">
            Start from a recipe, fine-tune style controls, scale through batch, and monitor runs —
            all from one workspace. The pipeline supports {CURATED_RECIPES.length} ready-to-use
            recipes and 100+ configurable creative controls.
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
          <p className="kpi-card__value">{CURATED_RECIPES.length + presets.length}</p>
          <p className="helper">Built-in recipes plus loaded presets.</p>
        </SurfaceCard>
        <SurfaceCard compact>
          <p className="micro-label">Needs review</p>
          <p className="kpi-card__value">{runs.filter((r) => r.status === "COMPLETED").length}</p>
          <p className="helper">Completed runs awaiting review.</p>
        </SurfaceCard>
      </section>

      {/* Creator Recipes */}
      <RecipeCards onSelect={handleRecipeSelect} />

      <section className="home-grid home-grid--cards">
        <SurfaceCard>
          <span className="section-header">Active runs rail</span>
          <h3>Production pulse</h3>
          {error ? <p>{error}</p> : null}
          {isRunsLoading ? (
            <EmptyState
              title="Loading runs"
              description="Fetching the latest runs and statuses from the API."
            />
          ) : runs.length ? (
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
          <span className="section-header">Loaded presets</span>
          <h3>Server presets</h3>
          {isPresetsLoading ? (
            <EmptyState
              title="Loading presets"
              description="Fetching preset catalog from the server."
            />
          ) : presets.length ? (
            <div className="surface-stack">
              {presets.slice(0, 4).map((preset) => (
                <div key={preset.name}>
                  <ToolbarPill>{preset.label}</ToolbarPill>
                  {preset.description ? <p className="helper">{preset.description}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Loading presets"
              description="Server presets will appear here once the API responds."
            />
          )}
        </SurfaceCard>
      </section>
    </div>
  );
}

import { NavLink } from "react-router-dom";

import { BatchWorkspace } from "../features/batch/BatchWorkspace";
import { StepRail, SurfaceCard } from "../components/primitives";

const STEPS = [
  { id: "import", title: "Dataset import" },
  { id: "mapping", title: "Schema mapping" },
  { id: "validation", title: "Validation" },
  { id: "recipe", title: "Recipe assignment" },
  { id: "preview", title: "Batch preview" },
];

interface BatchPageProps {
  activeStepId: string;
}

export function BatchPage({ activeStepId }: BatchPageProps) {
  return (
    <div className="batch-layout shell-page">
      <SurfaceCard>
        <span className="micro-label">Operations console</span>
        <h2>Batch assistant</h2>
        <p className="helper">
          Convert the current CSV queue into a staged workflow so operators understand mapping,
          validation, preview, and submission as one guided flow.
        </p>
        <div className="button-row">
          {STEPS.map((step) => (
            <NavLink
              key={step.id}
              to={`/batch/${step.id}`}
              className={({ isActive }) =>
                `batch-nav__link ${isActive ? "batch-nav__link--active" : ""}`.trim()
              }
            >
              {step.title}
            </NavLink>
          ))}
        </div>
      </SurfaceCard>

      <StepRail steps={STEPS} activeStepId={activeStepId} />
      <BatchWorkspace activeStepId={activeStepId} />
    </div>
  );
}

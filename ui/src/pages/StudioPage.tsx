import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import type {
  ClipInput,
  ConfigOptions,
  JobInput,
  JobPreviewResponse,
  PresetDetail,
  PresetListItem,
} from "../types";
import { Button, EmptyState, PanelShell, SurfaceCard, ToolbarPill } from "../components/primitives";
import { ClipList } from "../components/ClipList";
import { JobForm } from "../components/JobForm";
import { PresetCards } from "../components/PresetCards";
import { ReviewWorkspace } from "../features/review/ReviewWorkspace";

interface StudioLayoutProps {
  children?: ReactNode;
  preview: JobPreviewResponse | null;
  previewError: string | null;
  isPreviewLoading: boolean;
  presets: PresetListItem[];
  selectedPreset: PresetDetail | null;
  form: JobInput;
  configOptions: ConfigOptions | null;
  canPreview: boolean;
  onPresetSelect: (presetName: string) => void;
  onFormChange: (patch: Partial<JobInput>) => void;
  onClipsChange: (clips: ClipInput[]) => void;
  onAddClip: () => void;
  onPreview: () => void;
  onLaunch: () => void;
}

const STUDIO_ITEMS = [
  { to: "/studio/brief", label: "Brief" },
  { to: "/studio/style", label: "Style Lab" },
  { to: "/studio/review", label: "Review" },
];

export function StudioLayout(props: StudioLayoutProps) {
  return (
    <div className="studio-shell">
      <PanelShell className="custom-scrollbar">
        <span className="section-header">Creative studio</span>
        <h2>Build, inspect, and review a renderable plan</h2>
        <div className="surface-stack">
          {STUDIO_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `studio-nav__link ${isActive ? "studio-nav__link--active" : ""}`.trim()
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
        <div className="surface-stack">
          <ToolbarPill>{props.form.edit_preset ?? "standard_vertical"}</ToolbarPill>
          <ToolbarPill>{props.form.aspect_ratio ?? "preset default"}</ToolbarPill>
          <ToolbarPill>{props.form.geo || "geo pending"}</ToolbarPill>
        </div>
      </PanelShell>

      <div className="shell-page">
        {props.children}
      </div>

      <PanelShell className="custom-scrollbar">
        <span className="section-header">Studio panel</span>
        <h3>Preview and validations</h3>
        {props.preview ? (
          <div className="surface-stack">
            <p>{props.preview.resolved_clips.length} resolved clips</p>
            <p className="helper">{props.preview.intents.join(", ") || "No inferred intents yet."}</p>
            <div className="button-row">
              <Button onClick={props.onPreview} disabled={!props.canPreview}>
                Refresh plan
              </Button>
            </div>
          </div>
        ) : (
          <EmptyState
            title="No plan preview yet"
            description="Use the brief or style surfaces, then refresh the render plan before launching."
          />
        )}
      </PanelShell>
    </div>
  );
}

export function StudioBriefView({
  form,
  configOptions,
  presets,
  selectedPreset,
  canPreview,
  onPresetSelect,
  onFormChange,
  onClipsChange,
  onAddClip,
  onPreview,
}: StudioLayoutProps) {
  return (
    <div className="shell-page" style={{ gap: "var(--space-6)" }}>
      <SurfaceCard>
        <span className="section-header">Brief composer</span>
        <h2>Choose a starting point</h2>
        <p className="helper">
          Begin with a recipe, then confirm the creative inputs and clip order before review.
        </p>
      </SurfaceCard>

      <PresetCards presets={presets} onSelect={onPresetSelect} />

      {selectedPreset ? (
        <SurfaceCard muted>
          <span className="section-header">Recipe inspector</span>
          <h3>{selectedPreset.label}</h3>
          {selectedPreset.description ? <p>{selectedPreset.description}</p> : null}
          {selectedPreset.recommended_for ? <p className="helper">{selectedPreset.recommended_for}</p> : null}
        </SurfaceCard>
      ) : null}

      <JobForm value={form} onChange={onFormChange} configOptions={configOptions} />

      <ClipList
        clips={form.clips}
        onAdd={onAddClip}
        onChange={onClipsChange}
        clipTypes={configOptions?.clipTypes}
      />

      <div className="button-row" style={{ marginTop: "var(--space-2)" }}>
        <Button onClick={onPreview} disabled={!canPreview}>
          Preview render plan
        </Button>
      </div>
    </div>
  );
}

export function StudioStyleView({
  form,
  configOptions,
  onFormChange,
  onPreview,
  canPreview,
}: StudioLayoutProps) {
  return (
    <div className="shell-page">
      <SurfaceCard>
        <span className="section-header">Style lab</span>
        <h2>Move common creative controls out of raw JSON</h2>
        <p className="helper">
          This first pass keeps the current delivery form, but frames it as a creative control
          surface with progressive disclosure instead of a payload editor.
        </p>
      </SurfaceCard>

      <JobForm value={form} onChange={onFormChange} configOptions={configOptions} />

      <SurfaceCard muted>
        <span className="section-header">Coming next</span>
        <h3>Structured recipe controls</h3>
        <ul>
          <li>Subtitle presets and emphasis settings</li>
          <li>Music mode, volume, and loop defaults</li>
          <li>Alpha fill and background treatment recipes</li>
          <li>Provider visibility and compatibility hints</li>
        </ul>
      </SurfaceCard>

      <div className="button-row">
        <Button onClick={onPreview} disabled={!canPreview}>
          Refresh render plan
        </Button>
      </div>
    </div>
  );
}

export function StudioReviewView({
  preview,
  previewError,
  isPreviewLoading,
  canPreview,
  onPreview,
  onLaunch,
}: StudioLayoutProps) {
  const navigate = useNavigate();

  return (
    <ReviewWorkspace
      preview={preview}
      previewError={previewError}
      isLoading={isPreviewLoading}
      canLaunch={canPreview && Boolean(preview)}
      onGeneratePreview={onPreview}
      onLaunch={onLaunch}
      onOpenBatch={() => navigate("/batch/import")}
    />
  );
}

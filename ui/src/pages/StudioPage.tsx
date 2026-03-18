import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import type {
  ClipInput,
  ConfigOptions,
  JobInput,
  JobPreviewResponse,
  PresetDetail,
  PresetListItem,
  Profile,
} from "../types";
import { Button, EmptyState, PanelShell, SurfaceCard, ToolbarPill } from "../components/primitives";
import { ClipList } from "../components/ClipList";
import { JobForm } from "../components/JobForm";
import { ProfileSelector } from "../components/ProfileSelector";
import { PresetCards } from "../components/PresetCards";
import { ReviewWorkspace } from "../features/review/ReviewWorkspace";
import { SubtitleStylePanel } from "../components/style/SubtitleStylePanel";
import { AlphaFillPanel } from "../components/style/AlphaFillPanel";
import { TransitionsPanel } from "../components/style/TransitionsPanel";
import { PostProcessPanel } from "../components/style/PostProcessPanel";

export interface StudioLayoutProps {
  children?: ReactNode;
  preview: JobPreviewResponse | null;
  previewError: string | null;
  isPreviewLoading: boolean;
  presets: PresetListItem[];
  selectedPreset: PresetDetail | null;
  selectedProfile: Profile | null;
  form: JobInput;
  configOptions: ConfigOptions | null;
  isConfigLoading: boolean;
  isPresetsLoading: boolean;
  canPreview: boolean;
  onPresetSelect: (presetName: string) => void;
  onProfileSelect: (profile: Profile | null) => void;
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

      <div className="surface-card panel-shell custom-scrollbar">
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
      </div>
    </div>
  );
}

export function StudioBriefView({
  form,
  configOptions,
  presets,
  isConfigLoading,
  isPresetsLoading,
  selectedPreset,
  selectedProfile,
  canPreview,
  onPresetSelect,
  onProfileSelect,
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

      {isPresetsLoading ? (
        <SurfaceCard muted>
          <EmptyState
            title="Loading presets"
            description="Fetching server presets. You can still continue with manual setup."
          />
        </SurfaceCard>
      ) : (
        <PresetCards presets={presets} onSelect={onPresetSelect} />
      )}

      {selectedPreset ? (
        <SurfaceCard muted>
          <span className="section-header">Recipe inspector</span>
          <h3>{selectedPreset.label}</h3>
          {selectedPreset.description ? <p>{selectedPreset.description}</p> : null}
          {selectedPreset.recommended_for ? <p className="helper">{selectedPreset.recommended_for}</p> : null}
        </SurfaceCard>
      ) : null}

      <ProfileSelector
        selectedProfileId={selectedProfile?.profile_id ?? null}
        onSelectProfile={onProfileSelect}
        appliedProfileId={selectedProfile?.profile_id ?? null}
      />

      {isConfigLoading ? (
        <SurfaceCard muted>
          <EmptyState
            title="Loading form options"
            description="Fetching geos, clip types, and editor defaults."
          />
        </SurfaceCard>
      ) : (
        <JobForm value={form} onChange={onFormChange} configOptions={configOptions} />
      )}

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
  onFormChange,
  onPreview,
  canPreview,
}: StudioLayoutProps) {
  const styleOverrides = (form.style_overrides ?? {}) as Record<string, unknown>;

  const handleStyleChange = (patch: Record<string, unknown>) => {
    onFormChange({ style_overrides: patch });
  };

  return (
    <div className="shell-page" style={{ gap: "var(--space-4)" }}>
      <SurfaceCard>
        <span className="section-header">Style Lab</span>
        <h2>Creative Controls</h2>
        <p className="helper">
          Fine-tune subtitle styling, alpha compositing, transitions, and post-processing.
          All changes are reflected in the render plan as style_overrides.
        </p>
      </SurfaceCard>

      <SubtitleStylePanel
        styleOverrides={styleOverrides}
        onChange={handleStyleChange}
      />

      <AlphaFillPanel
        styleOverrides={styleOverrides}
        onChange={handleStyleChange}
      />

      <TransitionsPanel
        styleOverrides={styleOverrides}
        onChange={handleStyleChange}
      />

      <PostProcessPanel
        styleOverrides={styleOverrides}
        onChange={handleStyleChange}
      />

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

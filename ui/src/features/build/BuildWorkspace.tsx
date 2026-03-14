import { ClipList } from "../../components/ClipList";
import { JobForm } from "../../components/JobForm";
import { PresetCards } from "../../components/PresetCards";
import type { ClipInput, ConfigOptions, JobInput, PresetListItem } from "../../types";

interface BuildWorkspaceProps {
  configOptions: ConfigOptions | null;
  presets: PresetListItem[];
  form: JobInput;
  basicFields?: string[];
  onChange: (patch: Partial<JobInput>) => void;
  onClipsChange: (clips: ClipInput[]) => void;
  onAddClip: () => void;
  onSelectPreset: (presetName: string) => void;
  onPreview: () => void;
  canPreview: boolean;
  previewBlockedMessage?: string;
}

export function BuildWorkspace({
  configOptions,
  presets,
  form,
  basicFields,
  onChange,
  onClipsChange,
  onAddClip,
  onSelectPreset,
  onPreview,
  canPreview,
  previewBlockedMessage,
}: BuildWorkspaceProps) {
  return (
    <section aria-labelledby="build-workspace-title">
      <header>
        <h2 id="build-workspace-title">Build your run</h2>
        <p>Start from a preset, confirm the clip order, then preview the final request before launch.</p>
      </header>

      <PresetCards presets={presets} onSelect={onSelectPreset} />
      {basicFields?.length ? (
        <p>Preset defaults keep these fields front and center: {basicFields.join(", ")}.</p>
      ) : null}
      <JobForm value={form} onChange={onChange} configOptions={configOptions} />
      <ClipList
        clips={form.clips}
        onAdd={onAddClip}
        onChange={onClipsChange}
        clipTypes={configOptions?.clipTypes}
      />

      {previewBlockedMessage ? <p>{previewBlockedMessage}</p> : null}
      <button type="button" onClick={onPreview} disabled={!canPreview}>
        Preview launch plan
      </button>
    </section>
  );
}

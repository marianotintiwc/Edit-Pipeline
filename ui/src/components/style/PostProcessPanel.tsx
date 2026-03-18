import { SurfaceCard } from "../primitives";

interface PostProcessPanelProps {
  styleOverrides: Record<string, unknown>;
  onChange: (patch: Record<string, unknown>) => void;
}

export function PostProcessPanel({ styleOverrides, onChange }: PostProcessPanelProps) {
  const postprocess = (styleOverrides.postprocess ?? {}) as Record<string, unknown>;
  const enabled = Boolean(postprocess.enabled ?? true);

  return (
    <SurfaceCard>
      <span className="section-header">Post-process</span>
      <h3>Output polish</h3>
      <label>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) =>
            onChange({
              ...styleOverrides,
              postprocess: { ...postprocess, enabled: event.target.checked },
            })
          }
        />
        Enable post-process
      </label>
    </SurfaceCard>
  );
}

import { SurfaceCard } from "../primitives";

interface AlphaFillPanelProps {
  styleOverrides: Record<string, unknown>;
  onChange: (patch: Record<string, unknown>) => void;
}

export function AlphaFillPanel({ styleOverrides, onChange }: AlphaFillPanelProps) {
  const alpha = (styleOverrides.alpha_fill ?? {}) as Record<string, unknown>;
  const enabled = Boolean(alpha.enabled);

  return (
    <SurfaceCard>
      <span className="section-header">Alpha Fill</span>
      <h3>Compositing safety</h3>
      <label>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) =>
            onChange({
              ...styleOverrides,
              alpha_fill: { ...alpha, enabled: event.target.checked },
            })
          }
        />
        Enable alpha fill
      </label>
    </SurfaceCard>
  );
}

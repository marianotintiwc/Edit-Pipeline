import { SurfaceCard } from "../primitives";

interface TransitionsPanelProps {
  styleOverrides: Record<string, unknown>;
  onChange: (patch: Record<string, unknown>) => void;
}

export function TransitionsPanel({ styleOverrides, onChange }: TransitionsPanelProps) {
  const transitions = (styleOverrides.transitions ?? {}) as Record<string, unknown>;

  return (
    <SurfaceCard>
      <span className="section-header">Transitions</span>
      <h3>Flow continuity</h3>
      <label>
        Duration (seconds)
        <input
          type="number"
          step="0.1"
          value={Number(transitions.duration ?? 0.4)}
          onChange={(event) =>
            onChange({
              ...styleOverrides,
              transitions: { ...transitions, duration: Number(event.target.value) || 0.4 },
            })
          }
        />
      </label>
    </SurfaceCard>
  );
}

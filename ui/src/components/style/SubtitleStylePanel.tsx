import { SurfaceCard } from "../primitives";

interface SubtitleStylePanelProps {
  styleOverrides: Record<string, unknown>;
  onChange: (patch: Record<string, unknown>) => void;
}

function patchStyle(
  current: Record<string, unknown>,
  path: string,
  value: unknown,
): Record<string, unknown> {
  if (path === "fontsize" || path === "stroke_width" || path === "stroke_color" || path === "color") {
    return { ...current, [path]: value };
  }
  if (path.startsWith("highlight.")) {
    const key = path.slice("highlight.".length);
    const highlight = (current.highlight ?? {}) as Record<string, unknown>;
    return { ...current, highlight: { ...highlight, [key]: value } };
  }
  return current;
}

export function SubtitleStylePanel({ styleOverrides, onChange }: SubtitleStylePanelProps) {
  const strokeWidth = Number(styleOverrides.stroke_width ?? 2);
  const strokeOn = strokeWidth > 0;
  const strokeColor = String(styleOverrides.stroke_color ?? "#333333");
  const color = String(styleOverrides.color ?? strokeColor);
  const fontsize = Number(styleOverrides.fontsize ?? 60);
  const highlight = (styleOverrides.highlight ?? {}) as Record<string, unknown>;
  const highlightStrokeOn = Number(highlight.stroke_width ?? 4) > 0;
  const highlightStrokeWidth = Number(highlight.stroke_width ?? 4);
  const highlightTextColor = String(highlight.text_color ?? highlight.stroke_color ?? strokeColor);
  const highlightStrokeColor = String(highlight.stroke_color ?? strokeColor);

  const apply = (path: string, value: unknown) => {
    onChange(patchStyle(styleOverrides, path, value));
  };

  return (
    <SurfaceCard>
      <span className="section-header">Subtitle Style</span>
      <h3>Readability controls</h3>
      <div className="surface-stack">
        <label>
          Font size
          <input
            type="number"
            min={12}
            max={120}
            value={fontsize}
            onChange={(e) => apply("fontsize", Number(e.target.value) || 60)}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={strokeOn}
            onChange={(e) => apply("stroke_width", e.target.checked ? 10 : 0)}
          />
          Stroke on
        </label>
        {strokeOn && (
          <label>
            Stroke color
            <input
              type="color"
              value={strokeColor}
              onChange={(e) => apply("stroke_color", e.target.value)}
            />
            <input
              type="text"
              value={strokeColor}
              onChange={(e) => apply("stroke_color", e.target.value)}
              placeholder="#333333"
            />
          </label>
        )}
        <label>
          Text color (when stroke off, uses stroke color as fill)
          <input
            type="color"
            value={color}
            onChange={(e) => apply("color", e.target.value)}
          />
          <input
            type="text"
            value={color}
            onChange={(e) => apply("color", e.target.value)}
            placeholder="#333333"
          />
        </label>
        <details>
          <summary>Highlight (cajita) style</summary>
          <div className="surface-stack">
            <label>
              <input
                type="checkbox"
                checked={highlightStrokeOn}
                onChange={(e) =>
                  apply("highlight.stroke_width", e.target.checked ? 4 : 0)
                }
              />
              Highlight stroke on
            </label>
            {highlightStrokeOn && (
              <>
                <label>
                  Highlight stroke color
                  <input
                    type="color"
                    value={highlightStrokeColor}
                    onChange={(e) => apply("highlight.stroke_color", e.target.value)}
                  />
                </label>
                <label>
                  Highlight stroke width
                  <input
                    type="number"
                    min={0}
                    max={20}
                    value={highlightStrokeWidth}
                    onChange={(e) =>
                      apply("highlight.stroke_width", Number(e.target.value) || 0)
                    }
                  />
                </label>
              </>
            )}
            <label>
              Highlight text color
              <input
                type="color"
                value={highlightTextColor}
                onChange={(e) => apply("highlight.text_color", e.target.value)}
              />
            </label>
          </div>
        </details>
      </div>
    </SurfaceCard>
  );
}

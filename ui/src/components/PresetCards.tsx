import type { PresetListItem } from "../types";
import { Button } from "./primitives";

interface PresetCardsProps {
  presets: PresetListItem[];
  onSelect: (presetName: string) => void;
}

export function PresetCards({ presets, onSelect }: PresetCardsProps) {
  return (
    <section>
      <span className="section-header">Start from a preset</span>
      <h2>Recipes for Meli and beyond</h2>
      <div className="home-grid home-grid--cards" style={{ marginTop: "var(--space-4)" }}>
        {presets.map((preset) => (
          <article
            key={preset.name}
            className="preset-card animate-fade-in"
            role="button"
            tabIndex={0}
            onClick={() => onSelect(preset.name)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(preset.name);
              }
            }}
          >
            <div className="preset-card__preview" aria-hidden />
            <div className="preset-card__content">
              <h3>{preset.label}</h3>
              {preset.description ? <p>{preset.description}</p> : null}
              {preset.recommended_for ? <p className="helper">{preset.recommended_for}</p> : null}
              <div className="button-row" style={{ marginTop: "var(--space-3)" }} onClick={(e) => e.stopPropagation()}>
                <Button onClick={() => onSelect(preset.name)}>Use {preset.label}</Button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

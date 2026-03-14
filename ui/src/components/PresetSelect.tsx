import type { PresetListItem } from "../types";

interface PresetSelectProps {
  presets: PresetListItem[];
  value: string;
  onChange: (value: string) => void;
}

export function PresetSelect({ presets, value, onChange }: PresetSelectProps) {
  return (
    <label>
      Preset
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Custom</option>
        {presets.map((preset) => (
          <option key={preset.name} value={preset.name}>
            {preset.label}
          </option>
        ))}
      </select>
    </label>
  );
}

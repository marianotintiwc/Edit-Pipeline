import { JsonTextarea } from "./JsonTextarea";
import type { ConfigOptions, JobInput, SubtitleMode } from "../types";

interface JobFormProps {
  value: JobInput;
  onChange: (patch: Partial<JobInput>) => void;
  configOptions?: ConfigOptions | null;
}

const GEO_OPTIONS = ["MLA", "MLB", "BR", "MLC", "MLM"];
const PRESET_OPTIONS = [
  "standard_vertical",
  "no_interpolation",
  "no_subtitles",
  "simple_concat",
  "horizontal",
];
const SUBTITLE_OPTIONS: SubtitleMode[] = ["auto", "manual", "none"];
const ASPECT_RATIO_OPTIONS = ["9:16", "16:9"];

function parseNumber(value: string): number | undefined {
  return value === "" ? undefined : Number(value);
}

export function JobForm({ value, onChange, configOptions }: JobFormProps) {
  const geoOptions = configOptions?.geos ?? GEO_OPTIONS.map((geo) => ({ value: geo, label: geo }));
  const presetOptions =
    configOptions?.editPresets ??
    PRESET_OPTIONS.map((preset) => ({ value: preset, label: preset }));
  const subtitleOptions =
    configOptions?.subtitleModes ??
    SUBTITLE_OPTIONS.map((mode) => ({ value: mode, label: mode }));

  return (
    <section>
      <h2>Delivery settings</h2>
      <p>Keep the common delivery controls visible, and tuck specialist knobs into Advanced settings.</p>
      <div>
        <label>
          Market / country configuration
          <select
            aria-label="Market / country configuration"
            value={value.geo ?? ""}
            onChange={(event) => onChange({ geo: event.target.value })}
          >
            <option value="">Select a geo</option>
            {geoOptions.map((geo) => (
              <option key={geo.value} value={geo.value}>
                {geo.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div>
        <label>
          Edit preset
          <select
            value={value.edit_preset ?? "standard_vertical"}
            onChange={(event) => onChange({ edit_preset: event.target.value })}
          >
            {presetOptions.map((preset) => (
              <option key={preset.value} value={preset.value}>
                {preset.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div>
        <label>
          Music URL
          <input
            value={value.music_url ?? "random"}
            onChange={(event) => onChange({ music_url: event.target.value })}
          />
        </label>
      </div>
      <div>
        <label>
          Aspect ratio
          <select
            value={value.aspect_ratio ?? ""}
            onChange={(event) => onChange({ aspect_ratio: event.target.value || undefined })}
          >
            <option value="">Use preset default</option>
            {ASPECT_RATIO_OPTIONS.map((aspectRatio) => (
              <option key={aspectRatio} value={aspectRatio}>
                {aspectRatio}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div>
        <label>
          Subtitle mode
          <select
            value={value.subtitle_mode ?? "auto"}
            onChange={(event) =>
              onChange({ subtitle_mode: event.target.value as SubtitleMode })
            }
          >
            {subtitleOptions.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {(value.subtitle_mode ?? "auto") === "manual" ? (
        <div>
          <label>
            Manual SRT URL
            <input
              value={value.manual_srt_url ?? ""}
              onChange={(event) => onChange({ manual_srt_url: event.target.value })}
            />
          </label>
        </div>
      ) : null}
      <details>
        <summary>Advanced settings</summary>
        <div>
          <label>
            Music volume
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={value.music_volume ?? ""}
              onChange={(event) => onChange({ music_volume: parseNumber(event.target.value) })}
            />
          </label>
        </div>
        <div>
          <label>
            <input
              type="checkbox"
              checked={value.loop_music ?? true}
              onChange={(event) => onChange({ loop_music: event.target.checked })}
            />
            Loop music
          </label>
        </div>
        <div>
          <label>
            <input
              type="checkbox"
              checked={value.enable_interpolation ?? true}
              onChange={(event) => onChange({ enable_interpolation: event.target.checked })}
            />
            Enable interpolation
          </label>
        </div>
        <div>
          <label>
            Input FPS
            <input
              type="number"
              min="1"
              step="1"
              value={value.input_fps ?? ""}
              onChange={(event) => onChange({ input_fps: parseNumber(event.target.value) })}
            />
          </label>
        </div>
        <div>
          <label>
            RIFE model
            <input
              value={value.rife_model ?? ""}
              onChange={(event) => onChange({ rife_model: event.target.value || undefined })}
            />
          </label>
        </div>
        <div>
          <label>
            Request text
            <textarea
              value={value.request_text ?? ""}
              onChange={(event) => onChange({ request_text: event.target.value || undefined })}
            />
          </label>
        </div>
        <div>
          <label>
            Output filename
            <input
              value={value.output_filename ?? ""}
              onChange={(event) =>
                onChange({ output_filename: event.target.value || undefined })
              }
            />
          </label>
        </div>
        <div>
          <label>
            Output folder
            <input
              value={value.output_folder ?? ""}
              onChange={(event) => onChange({ output_folder: event.target.value || undefined })}
            />
          </label>
        </div>
        <div>
          <label>
            Output bucket
            <input
              value={value.output_bucket ?? ""}
              onChange={(event) => onChange({ output_bucket: event.target.value || undefined })}
            />
          </label>
        </div>
        <div>
          <label>
            <input
              type="checkbox"
              checked={value.plan_only ?? false}
              onChange={(event) => onChange({ plan_only: event.target.checked })}
            />
            Plan only
          </label>
        </div>
        <div>
          <JsonTextarea
            label="Style overrides JSON"
            value={value.style_overrides}
            onChange={(nextValue) => onChange({ style_overrides: nextValue })}
          />
        </div>
      </details>
    </section>
  );
}

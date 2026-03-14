import { Button } from "./primitives";
import { JsonTextarea } from "./JsonTextarea";
import type { ClipInput, ClipType, SelectOption } from "../types";

interface ClipListProps {
  clips: ClipInput[];
  onAdd: () => void;
  onChange: (clips: ClipInput[]) => void;
  clipTypes?: SelectOption[];
}

const CLIP_TYPES: ClipType[] = ["scene", "broll", "endcard", "introcard"];

function parseNumber(value: string): number | undefined {
  return value === "" ? undefined : Number(value);
}

export function ClipList({ clips, onAdd, onChange, clipTypes }: ClipListProps) {
  const availableClipTypes =
    clipTypes ?? CLIP_TYPES.map((clipType) => ({ value: clipType, label: clipType }));

  const updateClip = (index: number, patch: Partial<ClipInput>) => {
    onChange(
      clips.map((clip, clipIndex) =>
        clipIndex === index ? { ...clip, ...patch } : clip,
      ),
    );
  };

  const removeClip = (index: number) => {
    onChange(clips.filter((_, clipIndex) => clipIndex !== index));
  };

  const moveClip = (index: number, direction: -1 | 1) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= clips.length) {
      return;
    }

    const next = [...clips];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    onChange(next);
  };

  return (
    <section>
      <h2>Add clips and assets</h2>
      {clips.length === 0 ? (
        <p className="helper">No clips added yet. Add at least one clip with a URL to preview and launch.</p>
      ) : null}
      {clips.map((clip, index) => (
        <fieldset key={`${index}-${clip.type}`}>
          <legend>Clip {index + 1}</legend>
          <label>
            Clip type
            <select
              aria-label="Clip type"
              value={clip.type}
              onChange={(event) =>
                updateClip(index, { type: event.target.value as ClipType })
              }
            >
              {availableClipTypes.map((clipType) => (
                <option key={clipType.value} value={clipType.value}>
                  {clipType.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Clip URL
            <input
              aria-label="Clip URL"
              value={clip.url}
              onChange={(event) => updateClip(index, { url: event.target.value })}
            />
          </label>
          <label>
            Start time
            <input
              type="number"
              value={clip.start_time ?? ""}
              onChange={(event) =>
                updateClip(index, {
                  start_time: parseNumber(event.target.value),
                })
              }
            />
          </label>
          <label>
            End time
            <input
              type="number"
              value={clip.end_time ?? ""}
              onChange={(event) =>
                updateClip(index, {
                  end_time: parseNumber(event.target.value),
                })
              }
            />
          </label>
          <details>
            <summary>Advanced clip settings</summary>
            <label>
              Endcard overlap seconds
              <input
                type="number"
                min="0"
                step="0.1"
                value={clip.overlap_seconds ?? ""}
                onChange={(event) =>
                  updateClip(index, { overlap_seconds: parseNumber(event.target.value) })
                }
              />
            </label>
            <JsonTextarea
              label="Alpha fill JSON"
              value={clip.alpha_fill}
              onChange={(nextValue) => updateClip(index, { alpha_fill: nextValue })}
            />
            <JsonTextarea
              label="Effects JSON"
              value={clip.effects}
              onChange={(nextValue) => updateClip(index, { effects: nextValue })}
            />
          </details>
          <div className="button-row" style={{ marginTop: "var(--space-2)" }}>
            <Button variant="secondary" onClick={() => moveClip(index, -1)}>
              Move up
            </Button>
            <Button variant="secondary" onClick={() => moveClip(index, 1)}>
              Move down
            </Button>
            <Button variant="ghost" onClick={() => removeClip(index)}>
              Remove clip
            </Button>
          </div>
        </fieldset>
      ))}
      <Button onClick={onAdd}>Add clip</Button>
    </section>
  );
}

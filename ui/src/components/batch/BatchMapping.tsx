import { SurfaceCard } from "../primitives";

interface BatchMappingProps {
  headers: string[];
  mapping: Record<string, string>;
  onMappingChange: (mapping: Record<string, string>) => void;
}

export function BatchMapping({ headers, mapping, onMappingChange }: BatchMappingProps) {
  return (
    <SurfaceCard>
      <span className="section-header">Schema mapping</span>
      <h3>Map CSV headers to payload fields</h3>
      <div className="surface-stack">
        {headers.map((header) => (
          <label key={header}>
            {header}
            <input
              value={mapping[header] ?? ""}
              placeholder="e.g. clips[0].url"
              onChange={(event) =>
                onMappingChange({
                  ...mapping,
                  [header]: event.target.value,
                })
              }
            />
          </label>
        ))}
      </div>
    </SurfaceCard>
  );
}

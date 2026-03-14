import type { BatchDetail } from "../types";
import { Badge } from "./primitives";

interface BatchPreviewProps {
  batch: BatchDetail;
}

export function BatchPreview({ batch }: BatchPreviewProps) {
  const validLabel = `${batch.valid_rows} valid row${batch.valid_rows === 1 ? "" : "s"}`;
  const invalidLabel = `${batch.invalid_rows} row${batch.invalid_rows === 1 ? "" : "s"} needs attention`;

  return (
    <div className="batch-results-grid">
      <div className="surface-stack">
        <Badge tone="success">{validLabel}</Badge>
        {batch.invalid_rows > 0 ? (
          <Badge tone="warning">{invalidLabel}</Badge>
        ) : null}
      </div>
      {batch.rows.map((row) => (
        <article key={row.row_number} className="result-card surface-card">
          <div className="result-card__header">
            <h3 style={{ margin: 0, fontSize: "0.82rem", fontWeight: 600 }}>
              Row {row.row_number}
            </h3>
            <Badge
              tone={
                row.status === "ready"
                  ? "success"
                  : row.status === "failed"
                    ? "error"
                    : "default"
              }
            >
              {row.status}
            </Badge>
          </div>
          <div style={{ padding: "var(--space-3)" }}>
            {row.input?.geo ? <p className="helper" style={{ margin: 0 }}>Geo: {row.input.geo}</p> : null}
            {row.warnings.length > 0 ? (
              <ul style={{ margin: "var(--space-2) 0 0", paddingLeft: "var(--space-4)" }}>
                {row.warnings.map((w) => (
                  <li key={w} className="helper">{w}</li>
                ))}
              </ul>
            ) : null}
            {row.errors.length > 0 ? (
              <ul style={{ margin: "var(--space-2) 0 0", paddingLeft: "var(--space-4)", color: "var(--error)" }}>
                {row.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}

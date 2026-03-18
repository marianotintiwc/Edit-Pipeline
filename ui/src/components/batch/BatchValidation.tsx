import type { BatchRowResult } from "../../types";
import { Button, SurfaceCard } from "../primitives";

interface BatchValidationProps {
  rows: BatchRowResult[];
  onExportErrors: () => void;
}

export function BatchValidation({ rows, onExportErrors }: BatchValidationProps) {
  const invalidRows = rows.filter((row) => row.errors.length > 0);

  return (
    <SurfaceCard>
      <span className="section-header">Validation</span>
      <h3>Row-level checks</h3>
      <p>{rows.length} total rows</p>
      <p>{invalidRows.length} rows with errors</p>
      <div className="button-row">
        <Button variant="secondary" onClick={onExportErrors}>
          Export errors as CSV
        </Button>
      </div>
    </SurfaceCard>
  );
}

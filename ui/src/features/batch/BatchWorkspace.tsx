import { Link } from "react-router-dom";
import { useState } from "react";

import type { BatchDetail } from "../../types";
import type { Recipe } from "../../data/recipes";
import { BatchPreview } from "../../components/BatchPreview";
import { BatchUpload } from "../../components/BatchUpload";
import { BatchMapping } from "../../components/batch/BatchMapping";
import { BatchValidation } from "../../components/batch/BatchValidation";
import { BatchRecipe } from "../../components/batch/BatchRecipe";
import { CsvTemplateGenerator } from "../../components/batch/CsvTemplateGenerator";
import { Button, EmptyState, SurfaceCard } from "../../components/primitives";

interface BatchWorkspaceProps {
  activeStepId?: string;
}

export function BatchWorkspace({ activeStepId }: BatchWorkspaceProps) {
  const [batch, setBatch] = useState<BatchDetail | null>(null);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [selectedRecipeId, setSelectedRecipeId] = useState<string | null>(null);
  const [selectedRecipeInput, setSelectedRecipeInput] = useState<Record<string, unknown> | null>(null);

  const getInputPaths = (value: unknown, prefix = ""): string[] => {
    if (Array.isArray(value)) {
      return value.flatMap((item, index) => getInputPaths(item, `${prefix}[${index}]`));
    }
    if (value !== null && typeof value === "object") {
      return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) => {
        const nextPrefix = prefix ? `${prefix}.${key}` : key;
        return getInputPaths(nested, nextPrefix);
      });
    }
    return prefix ? [prefix] : [];
  };

  const handleExportErrors = () => {
    if (!batch) return;
    const errorRows = batch.rows.filter((r) => r.errors.length > 0);
    const csv = [
      "row_number,status,errors",
      ...errorRows.map(
        (r) => `${r.row_number},${r.status},"${r.errors.join("; ")}"`,
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `batch_errors_${batch.batch_id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleRecipeSelect = (recipe: Recipe) => {
    setSelectedRecipeId(recipe.id);
    setSelectedRecipeInput((recipe.input ?? null) as Record<string, unknown> | null);
  };

  if (activeStepId === "preview") {
    return (
      <div className="batch-split-layout custom-scrollbar">
        <div className="batch-split-layout__input">
          <span className="section-header">Batch config</span>
          <BatchUpload
            externalPreview
            onBatchChange={setBatch}
            mapping={mapping}
            recipeInput={selectedRecipeInput}
            onCsvHeadersChange={setCsvHeaders}
          />
        </div>
        <div className="batch-split-layout__results">
          <span className="section-header">Batch results</span>
          {batch ? (
            <BatchPreview batch={batch} />
          ) : (
            <EmptyState
              title="No batch loaded"
              description="Upload a CSV or load an existing batch to see preview and results here."
              action={
                <Link to="/batch/import">
                  <Button variant="secondary" style={{ marginTop: "var(--space-2)" }}>
                    Go to import
                  </Button>
                </Link>
              }
            />
          )}
        </div>
      </div>
    );
  }

  if (activeStepId === "mapping") {
    return (
      <section className="surface-stack">
        {csvHeaders.length > 0 ? (
          <BatchMapping
            headers={csvHeaders}
            mapping={mapping}
            onMappingChange={setMapping}
          />
        ) : (
          <SurfaceCard muted>
            <EmptyState
              title="No CSV loaded yet"
              description="Import a CSV first, then return here to map columns to pipeline fields."
              action={
                <Link to="/batch/import">
                  <Button variant="secondary">Go to import</Button>
                </Link>
              }
            />
          </SurfaceCard>
        )}
      </section>
    );
  }

  if (activeStepId === "validation") {
    return (
      <section className="surface-stack">
        {batch && batch.rows.length > 0 ? (
          <BatchValidation
            rows={batch.rows}
            onExportErrors={handleExportErrors}
          />
        ) : (
          <SurfaceCard muted>
            <EmptyState
              title="No batch to validate"
              description="Import and map a CSV first. Validation results will appear here."
              action={
                <Link to="/batch/import">
                  <Button variant="secondary">Go to import</Button>
                </Link>
              }
            />
          </SurfaceCard>
        )}
      </section>
    );
  }

  if (activeStepId === "recipe") {
    return (
      <section className="surface-stack">
          <BatchRecipe selectedRecipeId={selectedRecipeId} onSelectRecipe={handleRecipeSelect} />
          {selectedRecipeId ? (
            <p className="helper">Selected recipe will be applied on upload/submit.</p>
          ) : (
            <p className="helper">No recipe selected. Rows keep CSV-provided values only.</p>
          )}
      </section>
    );
  }

  return (
    <section className="surface-stack">
      <CsvTemplateGenerator />
      <BatchUpload
        mapping={mapping}
        recipeInput={selectedRecipeInput}
        onCsvHeadersChange={setCsvHeaders}
        onBatchChange={(b) => {
          setBatch(b);
          if (b && b.rows.length > 0 && b.rows[0].input) {
            const keys = getInputPaths(b.rows[0].input);
            if (csvHeaders.length === 0) {
              setCsvHeaders(keys);
            }
          }
        }}
      />
    </section>
  );
}

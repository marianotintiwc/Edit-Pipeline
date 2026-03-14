import { useState } from "react";

import type { BatchDetail } from "../../types";
import { BatchPreview } from "../../components/BatchPreview";
import { BatchUpload } from "../../components/BatchUpload";

interface BatchWorkspaceProps {
  activeStepId?: string;
}

export function BatchWorkspace({ activeStepId }: BatchWorkspaceProps) {
  const useSplitLayout = activeStepId === "preview";
  const [batch, setBatch] = useState<BatchDetail | null>(null);

  if (useSplitLayout) {
    return (
      <div className="batch-split-layout custom-scrollbar">
        <div className="batch-split-layout__input">
          <span className="section-header">Batch config</span>
          <BatchUpload externalPreview onBatchChange={setBatch} />
        </div>
        <div className="batch-split-layout__results">
          <span className="section-header">Batch results</span>
          {batch ? (
            <BatchPreview batch={batch} />
          ) : (
            <p className="helper">Upload a CSV or load a batch to see preview and results here.</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <section aria-labelledby="batch-workspace-title">
      <h2 id="batch-workspace-title">Batch queue</h2>
      <BatchUpload />
    </section>
  );
}

import type { JobPreviewResponse } from "../types";
import { Button } from "./primitives";

interface ReviewPanelProps {
  preview: JobPreviewResponse | null;
  previewError?: string | null;
  canLaunch: boolean;
  blockingMessage?: string;
  onGeneratePreview: () => void;
  onLaunch: () => void;
  onOpenBatch: () => void;
}

export function ReviewPanel({
  preview,
  previewError,
  canLaunch,
  blockingMessage,
  onGeneratePreview,
  onLaunch,
  onOpenBatch,
}: ReviewPanelProps) {
  return (
    <section className="surface-stack">
      <h2>Submission preview</h2>
      <p className="helper">Review the normalized request, warnings, and execution plan before launching a live job.</p>
      <div className="button-row" style={{ gap: "var(--space-3)" }}>
        <Button onClick={onGeneratePreview} variant="secondary">
          Refresh preview
        </Button>
        {previewError ? <p style={{ margin: 0 }}>{previewError}</p> : null}
      </div>
      {(preview?.warnings ?? []).map((warning) => (
        <p key={warning}>{warning}</p>
      ))}
      {preview ? (
        <>
          <p>{preview.resolved_clips.length} resolved clips</p>
          <p>Primary preset: {preview.normalized_input.edit_preset ?? "standard_vertical"}</p>
          <p>Geo: {preview.normalized_input.geo ?? "Not set"}</p>
          <ul>
            {preview.execution_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </>
      ) : (
        <p>Generate a preview from the Build workspace to inspect the final payload.</p>
      )}
      {blockingMessage ? (
        <p className="helper" style={{ margin: 0 }}>{blockingMessage}</p>
      ) : null}
      <div className="button-row" style={{ marginTop: "var(--space-4)", gap: "var(--space-2)" }}>
        <Button onClick={onLaunch} disabled={!canLaunch}>
          Launch run
        </Button>
        <Button variant="ghost" onClick={onOpenBatch}>
          Upload CSV batch
        </Button>
      </div>
    </section>
  );
}

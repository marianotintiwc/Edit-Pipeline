import { ReviewPanel } from "../../components/ReviewPanel";
import type { JobPreviewResponse } from "../../types";

interface ReviewWorkspaceProps {
  preview: JobPreviewResponse | null;
  previewError?: string | null;
  isLoading: boolean;
  canLaunch: boolean;
  onGeneratePreview: () => void;
  onLaunch: () => void;
  onOpenBatch: () => void;
}

export function ReviewWorkspace({
  preview,
  previewError,
  isLoading,
  canLaunch,
  onGeneratePreview,
  onLaunch,
  onOpenBatch,
}: ReviewWorkspaceProps) {
  if (isLoading) {
    return (
      <section aria-labelledby="review-workspace-title" aria-busy="true">
        <h2 id="review-workspace-title">Review & submit</h2>
        <div className="surface-stack" style={{ paddingTop: "var(--space-4)" }}>
          <div className="skeleton-shimmer" style={{ height: 24, width: "60%", borderRadius: "var(--radius-sm)" }} aria-hidden />
          <div className="skeleton-shimmer" style={{ height: 16, width: "90%", borderRadius: "var(--radius-sm)" }} aria-hidden />
          <div className="skeleton-shimmer" style={{ height: 16, width: "75%", borderRadius: "var(--radius-sm)" }} aria-hidden />
          <p className="helper" style={{ marginTop: "var(--space-2)" }}>Preparing your submission preview…</p>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="review-workspace-title">
      <h2 id="review-workspace-title">Review & submit</h2>
      <ReviewPanel
        preview={preview}
        previewError={previewError}
        canLaunch={canLaunch}
        blockingMessage={canLaunch ? undefined : "Add at least one clip before previewing this run."}
        onGeneratePreview={onGeneratePreview}
        onLaunch={onLaunch}
        onOpenBatch={onOpenBatch}
      />
    </section>
  );
}

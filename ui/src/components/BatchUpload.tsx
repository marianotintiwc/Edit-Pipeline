import { useEffect, useRef, useState } from "react";

import {
  cancelBatch as cancelBatchApi,
  createBatchFromCsv as createBatchFromCsvApi,
  getBatch as getBatchApi,
  listBatches as listBatchesApi,
  submitBatch as submitBatchApi,
} from "../api";
import type { BatchDetail, BatchListItem } from "../types";
import { Button, UploadZone } from "./primitives";
import { BatchPreview } from "./BatchPreview";
import { BatchProgress } from "./BatchProgress";

interface BatchUploadProps {
  createBatch?: (
    file: File,
    options?: { mapping?: Record<string, string>; recipeInput?: Record<string, unknown> | null },
  ) => Promise<BatchDetail>;
  getBatch?: (batchId: string) => Promise<BatchDetail>;
  listBatches?: () => Promise<{ items: BatchListItem[] }>;
  pollIntervalMs?: number;
  submitBatch?: (
    batchId: string,
    options?: { recipeInput?: Record<string, unknown> | null },
  ) => Promise<BatchDetail>;
  /** When true, preview is rendered by parent (for split layout) */
  externalPreview?: boolean;
  /** Called when batch changes so parent can render preview */
  onBatchChange?: (batch: BatchDetail | null) => void;
  mapping?: Record<string, string>;
  recipeInput?: Record<string, unknown> | null;
  onCsvHeadersChange?: (headers: string[]) => void;
}

export function BatchUpload({
  createBatch = createBatchFromCsvApi,
  getBatch = getBatchApi,
  listBatches = listBatchesApi,
  pollIntervalMs = 2500,
  submitBatch = submitBatchApi,
  externalPreview = false,
  onBatchChange,
  mapping,
  recipeInput,
  onCsvHeadersChange,
}: BatchUploadProps) {
  const [batch, setBatch] = useState<BatchDetail | null>(null);
  const [batchId, setBatchId] = useState("");
  const [recentBatches, setRecentBatches] = useState<BatchListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingBatch, setIsLoadingBatch] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isLoadingRecent, setIsLoadingRecent] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const hasPendingRows =
    batch?.rows.some((row) => ["ready", "failed"].includes(row.status) && row.input) ?? false;
  const activeRowCount =
    batch?.rows.filter((row) =>
      ["submitted", "queued", "in_progress"].includes(row.status),
    ).length ?? 0;
  const hasActiveRows = activeRowCount > 0;

  const loadRecentBatches = async () => {
    setIsLoadingRecent(true);
    try {
      const response = await listBatches();
      setRecentBatches(response.items);
    } catch {
      setRecentBatches([]);
    } finally {
      setIsLoadingRecent(false);
    }
  };

  useEffect(() => {
    void loadRecentBatches();
  }, [listBatches]);

  useEffect(() => {
    if (externalPreview && batch) onBatchChange?.(batch);
  }, [externalPreview, batch, onBatchChange]);

  useEffect(() => {
    if (!batch?.batch_id) {
      return undefined;
    }

    const hasProcessingRows = batch.rows.some((row) =>
      ["submitted", "queued", "in_progress"].includes(row.status),
    );
    if (!hasProcessingRows) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      void handleLoadBatch(batch.batch_id);
    }, pollIntervalMs);

    return () => {
      window.clearTimeout(timer);
    };
  }, [batch, pollIntervalMs]);

  const detectCsvHeaders = async (file: File): Promise<string[]> => {
    try {
      const text = await file.text();
      const [headerLine = ""] = text.split(/\r?\n/, 1);
      return headerLine
        .split(",")
        .map((header) => header.trim().replace(/^"|"$/g, ""))
        .filter(Boolean);
    } catch {
      return [];
    }
  };

  const handleUpload = async (file: File | null) => {
    if (!file) {
      return;
    }

    setError(null);
    setIsUploading(true);
    try {
      const headers = await detectCsvHeaders(file);
      if (headers.length > 0) {
        onCsvHeadersChange?.(headers);
      }
      const nextBatch = await createBatch(file, { mapping, recipeInput });
      setBatch(nextBatch);
      onBatchChange?.(nextBatch);
      setBatchId(nextBatch.batch_id);
      await loadRecentBatches();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to parse CSV batch");
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadBatch = async (targetBatchId: string) => {
    if (!targetBatchId.trim()) {
      return;
    }

    setError(null);
    setIsLoadingBatch(true);
    try {
      const nextBatch = await getBatch(targetBatchId.trim());
      setBatch(nextBatch);
      onBatchChange?.(nextBatch);
      setBatchId(nextBatch.batch_id);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load batch");
    } finally {
      setIsLoadingBatch(false);
    }
  };

  const handleSubmit = async () => {
    if (!batch) {
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      const nextBatch = await submitBatch(batch.batch_id, { recipeInput });
      setBatch(nextBatch);
      onBatchChange?.(nextBatch);
      await loadRecentBatches();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to submit batch");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelBatch = async () => {
    if (!batch) return;
    if (
      !window.confirm(
        `Cancel ${activeRowCount} active job(s)? Only queued and in-progress jobs will be stopped.`,
      )
    ) {
      return;
    }
    setError(null);
    setIsCancelling(true);
    try {
      await cancelBatchApi(batch.batch_id);
      const nextBatch = await getBatch(batch.batch_id);
      setBatch(nextBatch);
      onBatchChange?.(nextBatch);
      await loadRecentBatches();
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Failed to cancel batch");
    } finally {
      setIsCancelling(false);
    }
  };

  const renderPreviewInline = !externalPreview;

  return (
    <div className="surface-stack">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files[0];
          if (f?.name.endsWith(".csv")) void handleUpload(f);
        }}
      >
        <UploadZone
          text={isUploading ? "Uploading CSV..." : "Drop CSV or click to upload"}
          hint=".csv only · Max 5MB recommended. Use template columns for correct format."
          dragging={dragging}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            aria-label="CSV batch file"
            onChange={(e) => void handleUpload(e.target.files?.[0] ?? null)}
          />
        </UploadZone>
      </div>

      <div className="field-shell">
        <span className="section-header">Load existing batch</span>
        <label style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", marginBottom: 0 }}>
          <input
            value={batchId}
            onChange={(e) => setBatchId(e.target.value)}
            placeholder="Batch ID"
            aria-label="Batch ID"
          />
          <Button variant="secondary" onClick={() => void handleLoadBatch(batchId)}>
            {isLoadingBatch ? "Loading..." : "Load batch"}
          </Button>
        </label>
      </div>

      {isLoadingRecent ? (
        <p className="helper" aria-busy="true">
          Loading recent batches...
        </p>
      ) : null}
      {recentBatches.length > 0 ? (
        <div>
          <span className="section-header">Recent batches</span>
          <div className="surface-stack" style={{ marginTop: "var(--space-2)" }}>
            {recentBatches.slice(0, 5).map((recentBatch) => (
              <div
                key={recentBatch.batch_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--bg-tertiary)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>{recentBatch.batch_id}</p>
                  <p className="helper" style={{ margin: 0 }}>{recentBatch.filename}</p>
                </div>
                <Button variant="ghost" onClick={() => void handleLoadBatch(recentBatch.batch_id)}>
                  Open
                </Button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="status-banner status-banner--error" role="alert">
          <strong>Upload failed</strong>
          <p style={{ margin: 0 }}>{error}</p>
          <p className="helper" style={{ marginTop: "var(--space-1)", marginBottom: 0 }}>
            Check CSV format and size, then try again.
          </p>
        </div>
      ) : null}

      {batch && renderPreviewInline ? <BatchPreview batch={batch} /> : null}

      {batch && hasPendingRows ? (
        <Button onClick={() => void handleSubmit()} disabled={isSubmitting}>
          {isSubmitting ? "Submitting..." : "Submit pending rows"}
        </Button>
      ) : null}

      {batch && hasActiveRows ? (
        <Button
          variant="secondary"
          onClick={() => void handleCancelBatch()}
          disabled={isCancelling}
          aria-label={`Cancel ${activeRowCount} active jobs`}
        >
          {isCancelling ? "Cancelling..." : `Cancel ${activeRowCount} active job(s)`}
        </Button>
      ) : null}

      {batch && (batch.submitted_rows ?? 0) > 0 ? <BatchProgress batch={batch} /> : null}
    </div>
  );
}

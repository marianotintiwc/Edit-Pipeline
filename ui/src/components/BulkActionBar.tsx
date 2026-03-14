import type { ReactNode } from "react";

export interface BulkAction {
  id: string;
  label: ReactNode;
  onClick: () => void;
  variant?: "default" | "danger";
}

interface BulkActionBarProps {
  selectedCount: number;
  actions: BulkAction[];
}

export function BulkActionBar({ selectedCount, actions }: BulkActionBarProps) {
  if (selectedCount === 0) {
    return null;
  }

  return (
    <div className="bulk-action-bar" role="toolbar" aria-label="Bulk actions">
      <span className="bulk-action-bar__btn" style={{ pointerEvents: "none" }}>
        {selectedCount} selected
      </span>
      <span style={{ width: 1, height: 20, background: "var(--border-default)", flexShrink: 0 }} aria-hidden />
      {actions.map((action) => (
        <button
          key={action.id}
          type="button"
          className={`bulk-action-bar__btn ${action.variant === "danger" ? "bulk-action-bar__btn--danger" : ""}`.trim()}
          onClick={action.onClick}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}

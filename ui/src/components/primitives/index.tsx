import type { ComponentPropsWithoutRef, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ComponentPropsWithoutRef<"button"> {
  variant?: ButtonVariant;
}

export function Button({ className = "", variant = "primary", type = "button", ...props }: ButtonProps) {
  return <button type={type} className={`btn btn-${variant} ${className}`.trim()} {...props} />;
}

export function IconButton({ className = "", ...props }: ButtonProps) {
  return <Button className={`btn-icon ${className}`.trim()} {...props} />;
}

interface BadgeProps {
  children: ReactNode;
  tone?: "default" | "success" | "warning" | "error";
}

export function Badge({ children, tone = "default" }: BadgeProps) {
  const toneClass = tone === "default" ? "" : `badge-${tone}`;
  return <span className={`badge ${toneClass}`.trim()}>{children}</span>;
}

export function Chip({ children }: { children: ReactNode }) {
  return <span className="chip">{children}</span>;
}

interface SegmentedOption {
  id: string;
  label: string;
}

interface SegmentedControlProps {
  options: SegmentedOption[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function SegmentedControl({ options, selectedId, onSelect }: SegmentedControlProps) {
  return (
    <div className="button-row" role="tablist" aria-label="Segmented control">
      {options.map((option) => (
        <Button
          key={option.id}
          variant={selectedId === option.id ? "primary" : "secondary"}
          aria-pressed={selectedId === option.id}
          onClick={() => onSelect(option.id)}
        >
          {option.label}
        </Button>
      ))}
    </div>
  );
}

interface SurfaceCardProps {
  children: ReactNode;
  className?: string;
  compact?: boolean;
  muted?: boolean;
}

export function SurfaceCard({ children, className = "", compact = false, muted = false }: SurfaceCardProps) {
  return (
    <div
      className={[
        "surface-card",
        compact ? "surface-card--compact" : "",
        muted ? "surface-card--muted" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}

export function PanelShell({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <aside className={`surface-card panel-shell ${className}`.trim()}>{children}</aside>;
}

export function ModalShell({ children }: { children: ReactNode }) {
  return <div className="surface-card">{children}</div>;
}

interface UploadZoneProps {
  children: ReactNode;
  dragging?: boolean;
  text?: string;
  hint?: string;
  onClick?: () => void;
}

export function UploadZone({ children, dragging = false, text, hint, onClick }: UploadZoneProps) {
  return (
    <div
      className={`upload-zone ${dragging ? "upload-zone--dragging" : ""}`}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {text ? (
        <>
          <span className="upload-zone__text">{text}</span>
          {hint ? <span className="upload-zone__hint">{hint}</span> : null}
          {children}
        </>
      ) : (
        children
      )}
    </div>
  );
}

export function FieldShell({
  label,
  helper,
  children,
}: {
  label: ReactNode;
  helper?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="field-shell">
      <span>{label}</span>
      {children}
      {helper ? <small className="helper">{helper}</small> : null}
    </div>
  );
}

export function ToolbarPill({ children }: { children: ReactNode }) {
  return <span className="toolbar-pill">{children}</span>;
}

interface MediaResultCardProps {
  title: string;
  meta?: ReactNode;
  ratio?: string;
  children?: ReactNode;
  actions?: ReactNode;
}

export function MediaResultCard({ title, meta, ratio, children, actions }: MediaResultCardProps) {
  return (
    <div className="result-card media-card">
      <div className="result-card__header">
        <h3 style={{ margin: 0, fontSize: "0.82rem", fontWeight: 600 }}>{title}</h3>
        {ratio ? <span className="result-card__ratio">{ratio}</span> : null}
      </div>
      <div style={{ position: "relative" }}>
        <div className="media-card__preview" />
        {actions ? <div className="result-card__actions">{actions}</div> : null}
      </div>
      <div>
        {meta ? <p className="helper">{meta}</p> : null}
      </div>
      {children}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function StatusBanner({
  title,
  tone = "default",
  children,
}: {
  title: string;
  tone?: "default" | "warning" | "error" | "success";
  children?: ReactNode;
}) {
  const toneClass = tone === "default" ? "" : `status-banner--${tone}`;
  return (
    <div className={`status-banner ${toneClass}`.trim()}>
      <strong>{title}</strong>
      {children ? <div>{children}</div> : null}
    </div>
  );
}

interface StepRailStep {
  id: string;
  title: string;
}

export function StepRail({
  steps,
  activeStepId,
}: {
  steps: StepRailStep[];
  activeStepId: string;
}) {
  const activeIndex = steps.findIndex((s) => s.id === activeStepId);
  return (
    <div className="step-rail" aria-label="Step rail">
      {steps.map((step, index) => {
        const isActive = step.id === activeStepId;
        const isCompleted = activeIndex >= 0 && index < activeIndex;
        const cn = [
          "step-rail__item",
          isActive ? "step-rail__item--active" : "",
          isCompleted ? "step-rail__item--completed" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <div key={step.id} className={cn} aria-current={isActive ? "step" : undefined}>
            <span className="micro-label">Step {index + 1}</span>
            <span>{step.title}</span>
          </div>
        );
      })}
    </div>
  );
}

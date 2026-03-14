import type { ComponentPropsWithoutRef, ReactNode } from "react";

interface FormatPillProps extends Omit<ComponentPropsWithoutRef<"button">, "children"> {
  children: ReactNode;
  ratio?: string;
  active?: boolean;
  platform?: string;
}

export function FormatPill({
  children,
  ratio,
  active = false,
  platform,
  className = "",
  ...props
}: FormatPillProps) {
  return (
    <button
      type="button"
      className={`format-pill ${active ? "format-pill--active" : ""} ${className}`.trim()}
      {...props}
    >
      {ratio ? (
        <span className="format-pill__ratio" aria-hidden>
          {ratio}
        </span>
      ) : null}
      <span style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0, textAlign: "left" }}>
        <span>{children}</span>
        {platform ? <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{platform}</span> : null}
      </span>
    </button>
  );
}

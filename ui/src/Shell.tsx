import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { Badge } from "./components/primitives";
import { ThemeToggle } from "./components/ThemeToggle";

interface ShellProps {
  children: ReactNode;
  alertSlot?: ReactNode;
}

const NAV_ITEMS = [
  { to: "/", label: "Home", end: true },
  { to: "/studio/brief", label: "Studio" },
  { to: "/batch/import", label: "Batch" },
  { to: "/runs", label: "Runs" },
  { to: "/library", label: "Library" },
  { to: "/admin", label: "Admin" },
];

export function Shell({ children, alertSlot }: ShellProps) {
  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <div className="app-shell__header-inner">
          <div className="app-shell__branding">
            <span className="micro-label">Creative Operating System</span>
            <h1>UGC Video Editor</h1>
            <p className="helper">Creative Studio on top, operations underneath.</p>
          </div>
          <div className="button-row" style={{ alignItems: "center" }}>
            <Badge>Studio + Ops</Badge>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="app-shell__content">
        <nav className="top-nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `top-nav__link ${isActive ? "top-nav__link--active" : ""}`.trim()
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        {alertSlot}
        {children}
      </main>
    </div>
  );
}

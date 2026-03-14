export type WorkspaceId = "build" | "review" | "monitor" | "batch";

interface WorkspaceOption {
  id: WorkspaceId;
  label: string;
  description: string;
}

const WORKSPACES: WorkspaceOption[] = [
  {
    id: "build",
    label: "Build",
    description: "Start from a preset, add clips, and adjust delivery settings.",
  },
  {
    id: "review",
    label: "Review & Submit",
    description: "Preview the normalized request, warnings, and launch readiness.",
  },
  {
    id: "monitor",
    label: "Monitor Runs",
    description: "Reopen recent runs and inspect live job status or outputs.",
  },
  {
    id: "batch",
    label: "Batch Queue",
    description: "Upload CSV batches or reopen existing batch previews.",
  },
];

interface WorkspaceNavProps {
  currentWorkspace: WorkspaceId;
  onChange: (workspace: WorkspaceId) => void;
}

export function WorkspaceNav({ currentWorkspace, onChange }: WorkspaceNavProps) {
  return (
    <nav aria-label="Workspaces">
      {WORKSPACES.map((workspace) => (
        <button
          key={workspace.id}
          type="button"
          aria-pressed={workspace.id === currentWorkspace}
          onClick={() => onChange(workspace.id)}
        >
          {workspace.label}
        </button>
      ))}
      <p>{WORKSPACES.find((workspace) => workspace.id === currentWorkspace)?.description}</p>
    </nav>
  );
}

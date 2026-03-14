# Overnight Guardian Mode v2 — UGC Edit Pipeline UI

**Branch:** `ui-overnight-v2-2025-03-15`  
**Started:** 2025-03-15  
**Scope:** Creative freedom + Node-and-link UX research + Tier-1 polish  
**Estimated runtime:** 6–10h

## Mission

Execute Overnight Guardian Mode v2: research-before-decide, iterative gap analysis, Tier-1 upgrades only, and capability surfacing for a future node-and-link creative freedom layer. Never touch business logic, IA, or form submission.

## Phases (v2)

| Phase | Status | Output |
|-------|--------|--------|
| 0. Planning & Branching | Done | This file, branch ui-overnight-v2-2025-03-15 |
| 1. Deep Inventory | In progress | inventory.md (component map + Canvas Flow comparison) |
| 2. Flow Classification & Persona | Pending | Purpose per area, success metrics |
| 3. Node-and-Link Benchmark Research | Pending | benchmark-references.md (node patterns, capability mapping) |
| 4. Per-Area Iterative Gap & Heuristic Loop | Pending | findings-per-area.md |
| 5. Obvious Tier-1 Upgrades | Pending | Patches + diffs |
| 6. Node-and-Link Capability Surfacing | Pending | capability-surface-log.md |
| 7. Verification & Regression | Pending | verification-log.md |
| 8. Documentation Artifacts | Pending | All logs consolidated |
| 9. Morning Handoff | Done | 10-point handoff, HANDOFF.md, draft PR body |

## Scope

- **Routes:** `/`, `/batch/*`, `/studio/*`, `/runs`, `/library`, `/admin`
- **Primary flows:** Batch (import → mapping → validation → recipe → preview), Studio (brief → style → review), Home hub
- **Tech stack:** React 19, Vite 7, Tailwind 4, react-router-dom 7
- **Canvas Flow alignment:** Staged flows (resize→translate→iterate) as node-graph mental model; semantic tokens, motion, batch utility from UI_PLAYBOOK as design constraints
- **Node-and-link research:** ComfyUI, Runway Workflows, n8n, React Flow/Xyflow; hybrid "Simple mode" vs "Graph mode" strategy

## Phase 2: Classification (baseline)

- **Home:** Dashboard — KPIs, action cards, workspace hub. Primary persona: operator/creator starting a session.
- **Batch:** Wizard + CRUD workbench — ordered steps (import → mapping → validation → recipe → preview), split layout on Preview. Primary persona: operator processing CSV queues.
- **Studio:** Form flow + wizard (Brief → Style → Review). Primary persona: creator configuring a video edit.
- **Success metric:** Reduce time-to-first-submit and validation friction; increase trust via clear status and next actions; surface creative freedom for AI creators.
- **Risk flags:** None (no payments, no destructive actions without confirmation). API/config errors surface as "Not Found" — needs clearer empty/error treatment.

## Safety rules

- **Tier 1 (auto-apply):** Visual polish, spacing, labels, states, empty states, microcopy, minor a11y
- **Tier 2 (recommend only):** Layout reordering, progressive disclosure, node graph prototype
- **Tier 3 (never):** IA/nav changes, form field changes affecting submission, business logic

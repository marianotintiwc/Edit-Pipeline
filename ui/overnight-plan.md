# Overnight UX Benchmark & Modernization Mode — UGC Edit Pipeline UI

**Branch:** `ui-overnight-batch-studio-2025-03-14`  
**Started:** 2025-03-14  
**Flow scope:** Batch assistant + Studio + Home hub

## Mission

Autonomous UX benchmarking and Tier-1 safe improvements for the UGC Video Editor creative-operations shell. Never touch business logic, IA, or form submission.

## Phases

| Phase | Status | Output |
|-------|--------|--------|
| 1. Inventory | In progress | inventory.md |
| 2. Classification | Done | See below |
| 3. Research | Done | benchmark-references.md (project root) |
| 4. Benchmark & gap | Pending | Gap scorecard |
| 5. Heuristic review | Pending | Nielsen scorecard |
| 6. Tier-1 upgrades | Pending | Patches + diffs |
| 7. Verification | Pending | verification-log.md |
| 8. Draft PR | Pending | 9-point handoff |

## Scope

- **Routes:** `/`, `/batch/*`, `/studio/*`, `/runs`, `/library`, `/admin`
- **Primary flows:** Batch (import → mapping → validation → recipe → preview), Studio (brief → style → review), Home hub
- **Tech stack:** React 19, Vite 7, Tailwind 4, react-router-dom 7

## Phase 2: Classification

- **Home:** Dashboard — KPIs, action cards, workspace hub. Primary persona: operator/creator starting a session.
- **Batch:** Wizard + CRUD workbench — ordered steps (import → mapping → validation → recipe → preview), split layout on Preview. Primary persona: operator processing CSV queues.
- **Studio:** Form flow + wizard (Brief → Style → Review). Primary persona: creator configuring a video edit.
- **Success metric:** Reduce time-to-first-submit and validation friction; increase trust via clear status and next actions.
- **Risk flags:** None (no payments, no destructive actions without confirmation). API/config errors surface as "Not Found" — needs clearer empty/error treatment.

## Safety rules

- **Tier 1 (auto-apply):** Visual polish, spacing, labels, states, empty states, microcopy, minor a11y
- **Tier 2 (recommend only):** Layout reordering, progressive disclosure
- **Tier 3 (never):** IA/nav changes, form field changes affecting submission, business logic

# Overnight Guardian Mode v2 — Morning Handoff (10-Point)

**Branch:** `ui-overnight-v2-2025-03-15`  
**Date:** 2025-03-15

---

1. **What this UI is** — UGC Video Editor: creative-operations shell (Studio, Batch, Runs, Home). Current state: forms + wizards; many capabilities (style_overrides, alpha_fill) hidden in JSON.

2. **Purpose + creator success metrics** — Time-poor AI creator; reduce time-to-first-submit; increase trust via clear status; surface creative freedom as discoverable controls.

3. **Research sources used** — Runway Workflows, ComfyUI App View, React Flow/Xyflow, n8n, Canvas Flow UI_PLAYBOOK, Stripe/CSVBox/Linear for CSV and dashboard patterns.

4. **Usability scorecard** — Nielsen heuristic gaps addressed: Visibility (loading aria-busy), Consistency (Button usage), Error prevention (helper text), Error recovery (banner helper), Help (ClipList URL hint). Remaining: tooltips, skeleton loading (Tier-1 deferred).

5. **Tier-1 changes applied**
   - ValidationErrors: heading "Something went wrong"
   - ClipList: helper "Add at least one clip with a URL to preview and launch"
   - MonitorWorkspace: EmptyState + CTA "Start in Studio"; Button instead of raw button; loading aria-busy
   - BatchWorkspace: EmptyState for results pane with "Go to import" CTA
   - BatchUpload: error banner with "Upload failed" + "Check CSV format and size, then try again"; role="alert"

6. **New capabilities surfaced** — `capability-surface-log.md`: node graph concept (Input/Processing/Output nodes), typed ports, hybrid Simple/Graph mode, React Flow + ElkJS sketch, P0/P1/P2 priorities.

7. **Deferred Tier-2 opportunities** — Node graph prototype; Alpha/Subtitles/Postprocess nodes; live preview in nodes; minimap; UploadZone size hint; skeleton loading; tooltips.

8. **Risks & verification** — No regressions. Build + 17/17 tests pass. App.test.tsx updated for ClipList copy.

9. **QA checklist**
   - [ ] Studio Brief: ClipList shows helper when empty
   - [ ] Batch Import: error banner shows helper on upload fail
   - [ ] Runs: MonitorWorkspace empty state with "Start in Studio" CTA
   - [ ] Batch Preview: results pane EmptyState when no batch
   - [ ] ValidationErrors: heading "Something went wrong"
   - [ ] Accessibility: aria-busy on loading; role="alert" on error banner

10. **Draft PR**
    - **Title:** ui: overnight v2 — error UX, empty states, microcopy, node-capability surface
    - **Body:** See HANDOFF PR body below
    - **Follow-ups:** Add screenshots; manual QA; merge

---

## PR Body (for copy-paste)

```markdown
## Summary
- Tier-1 UI polish—error headings, helper text, empty states, consistent Button usage, loading aria-busy, plus node-and-link capability surface (docs) and benchmark references.
- Align with Nielsen heuristics and prepare for future graph-mode UX.
- Scope: Visual/microcopy only; no form behavior or API changes.

## What Changed
- Workflow: Empty states with CTAs in MonitorWorkspace and BatchWorkspace
- Forms: ClipList helper for URL requirement
- Visual: ValidationErrors "Something went wrong"; MonitorWorkspace Button
- Accessibility: aria-busy on loading; role="alert" on error banner

## UX Impact
- Reduced friction: clear URL requirement; actionable error copy
- Better states: EmptyState + CTA; loading aria-busy

## Risks
- None. Tier-1 only.

## Test Plan
- [x] npm run build
- [x] npm test — 17/17 passed
- [ ] Manual QA; accessibility spot checks

## Follow-Ups
- capability-surface-log.md P1/P2; remaining Tier-1 (skeleton, tooltips)
```

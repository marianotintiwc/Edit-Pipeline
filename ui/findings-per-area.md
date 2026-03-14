# Findings per Area — Overnight Guardian Mode v2

## Flow classification & persona

### Persona: AI creator (time-poor, wants creative control)

- **Time-poor:** Needs fast path from idea to submit; minimal friction in validation and mapping.
- **Creative control:** Wants to tweak style, alpha, postprocess without raw JSON; trusts UI when status and next actions are clear.
- **Success metric:** Reduce time-to-first-submit; increase trust via clear status; surface creative freedom (style, alpha, postprocess) as discoverable controls.

### One-sentence purpose per area

| Area | Purpose |
|------|---------|
| Home | Single entry point for session snapshot, shortcuts to Studio/Batch/Runs, and KPIs. |
| Studio Brief | Configure recipe, geo, clips before style; primary creation surface. |
| Studio Style | Creative controls, delivery settings, advanced options. |
| Studio Review | Inspect normalized plan and launch or plan-only. |
| Batch Import | Upload CSV or load batch; first step of batch pipeline. |
| Batch Mapping/Validation/Recipe | Schema mapping, validation, recipe assignment (placeholder content). |
| Batch Preview | Split layout: config left, results right; submit pending rows. |
| Runs | Monitor active jobs, drill to run detail, recover failures. |

### Success metrics

- **Studio:** Job submitted, run ID visible, user navigated to Runs.
- **Batch:** CSV parsed, rows validated, pending rows submitted; BatchProgress shows status.
- **Runs:** Run status visible; user can open run detail.
- **Creative freedom (future):** style_overrides, alpha_fill, postprocess exposed as nodes or guided controls, not only raw JSON.

---

## Heuristic scorecard (Phase 4)

### Nielsen 10 — Issues

| # | Heuristic | Severity |
|---|-----------|----------|
| 1 | Visibility of system status | Medium — plain "Loading..." text; minimal visual feedback |
| 2 | Match real world | Low |
| 3 | User control | Medium — Batch steps reuse same content |
| 4 | Consistency | Medium — raw button vs Button; mixed label styles |
| 5 | Error prevention | High — no client-side CSV validation; blocking message easy to overlook |
| 6 | Recognition over recall | Medium — Batch ID recall; no template download |
| 7 | Flexibility | Low |
| 8 | Aesthetic/minimalist | High — JobForm/ClipList dense; placeholder clutter |
| 9 | Error recovery | High — no CSV export of errors; no retry guidance |
| 10 | Help | Critical — no tooltips; helper text inconsistent |

### Tier-1 opportunities (safe to apply)

1. Labels & microcopy: ValidationErrors heading; ClipList URL hint; UploadZone size hint
2. Loading states: MonitorWorkspace skeleton/EmptyState; JobStatus spinner
3. Empty states: Runs EmptyState with CTA "Start in Studio"; Batch results pane EmptyState
4. Consistency: MonitorWorkspace raw button → Button
5. Error UX: Add helper text near error banners

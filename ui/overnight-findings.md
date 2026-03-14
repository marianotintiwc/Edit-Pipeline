# UGC Edit Pipeline — Heuristic Evaluation Report

**Date:** March 14, 2026  
**Scope:** Batch flow, Studio flow, Home hub  
**Reference:** `benchmark-references.md` (CSVBox/Stripe, Canva/Shotstack, Linear/Vercel)

---

## 1. Benchmark Gap Analysis

### Batch Flow (vs CSVBox / Stripe)
- Split layout: **Partial** — only on preview step
- Progressive disclosure: **Gap** — mapping/validation/recipe share same content
- Column mapping: **Missing**
- Row-level feedback: **Partial** — errors in BatchPreview; no downloadable CSV
- Empty state: **Partial** — text/hint; no template download, no size limits
- Dry-run: **Not exposed**

**Score:** 2/6 full, 2/6 partial, 2/6 missing

### Studio Flow (vs Canva / Adobe / Shotstack)
- Template selection: **Partial** — PresetCards, no search/filters
- Step clarity: **Gap** — nav links, not stepper; multiple CTAs
- CTA hierarchy: **Gap** — all buttons same level
- Config before creation: **Met**
- Review step: **Partial** — blocking state not visually distinct

**Score:** 1/5 full, 2/5 partial, 2/5 gap

### Home Hub (vs Linear / Vercel)
- Primary actions: **Met**
- KPI placement: **Met**
- Session snapshot: **Met**
- Split layout: **Partial**
- Drill-down: **Gap**

**Score:** 3/5 met, 1/5 partial, 1/5 gap

---

## 2. Nielsen Heuristic Scorecard

| # | Heuristic | Severity | Evidence |
|---|-----------|----------|----------|
| 1 | Visibility of system status | Medium | Review loading = text only; no upload progress |
| 2 | Match real world | Cosmetic | Terms fit domain; some generic labels |
| 3 | User control | Medium | Dead steps; no cancel batch |
| 4 | Consistency | Medium | Raw button vs Button; mixed patterns |
| 5 | Error prevention | High | No CSV size check; subtle blocking UX |
| 6 | Recognition over recall | Medium | No completion state in step rail |
| 7 | Flexibility | Cosmetic | No shortcuts/bulk actions |
| 8 | Minimalist design | High | Dense forms; placeholders add load |
| 9 | Error recovery | High | No download errors CSV |
| 10 | Help/documentation | Critical | No tooltips, contextual help |

---

## 3. Tier-1 Safe Improvements (Auto-apply)

1. Studio CTA hierarchy — Promote "Launch run" as primary, "Refresh preview" secondary
2. UploadZone empty state — Add template download link + size limit hint (copy only)
3. Consistent Button usage — Replace raw button in ReviewPanel, ClipList
4. EmptyState action slots — Add optional CTAs where useful
5. StepRail completion indication — Checkmarks for completed steps
6. Section spacing — Group Brief sections; primary action stand out
7. Loading state for Studio preview — Skeleton/spinner instead of plain text

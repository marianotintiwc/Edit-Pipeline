# LATAM Alpha Config – Architecture Review

## Requirement Restatement

- **Goal**: Ensure broll and endcard use alpha channel the same way as MELI (blurred background fill behind transparent areas).
- **Constraint**: No code or Docker changes; all tools already exist in the codebase.
- **Question**: Is alpha being replaced/applied for both broll and endcard in LATAM jobs?

## Current Data Flow

```
run_meli_from_latam_csv.py
  → style_overrides (broll_alpha_fill, endcard, highlight)
  → RunPod handler
  → generate_style_config() deep_merges with handler defaults
  → style.json written to work_dir
  → process_clips(clips_config, style)
  → ugc_pipeline/clips.py applies broll_alpha_fill / endcard_alpha_fill
```

## Findings

### Handler Defaults (handler.py:684–706)

- **broll_alpha_fill**: `enabled`, `blur_sigma: 60`, `slow_factor: 1.5`, `force_chroma_key: True`, `chroma_key_color: 0x1F1F1F`, etc.
- **endcard_alpha_fill**: `enabled: False`, `use_blur_background: False`

### LATAM Script (run_meli_from_latam_csv.py)

- **broll_alpha_fill**: Only `{enabled, invert_alpha, auto_invert_alpha}` — relies on handler defaults for blur/chroma.
- **endcard_alpha_fill**: Not set — inherits from base_style (`enabled: false`).

### MELI Reference (config/style.json, run_sellers)

- **broll_alpha_fill**: Full config with `blur_sigma: 60`, `force_chroma_key: true`, etc.
- **endcard_alpha_fill**: `enabled: false` for MELI users/sellers.

### Pipeline Logic (ugc_pipeline/clips.py)

- **Broll**: `alpha_fill_enabled` and (`broll_has_alpha` or `alpha_force_key`) → blurred background + composite.
- **Endcard**: `endcard_alpha_config.enabled` and `use_blur_background` → blurred background behind endcard; otherwise overlay only.

## Root Cause

1. **Broll**: LATAM override is minimal; handler merge should add defaults. To avoid any merge edge cases, use an explicit full config like MELI.
2. **Endcard**: `endcard_alpha_fill.enabled: false` means no blurred background behind the endcard. Alpha is still used for compositing (overlay), but transparent areas show the previous clip, not a blur. If LATAM endcard has alpha and should look like MELI broll (blur behind), we need `endcard_alpha_fill.enabled: true` and `use_blur_background: true`.

## Proposed Design

1. **Broll**: Use full explicit `broll_alpha_fill` (same as config/style.json / handler defaults).
2. **Endcard**: Add `endcard_alpha_fill` with `enabled: true` and `use_blur_background: true` so endcard transparent areas get blurred background like broll.

## Files to Change

- `Helper Scripts/run_meli_from_latam_csv.py`: Update `build_payload()` to send full alpha config.

## Trade-offs

- **Explicit config**: Slightly larger payload, but no dependency on handler defaults.
- **Endcard blur**: If LATAM endcard has no alpha, enabling blur has no visible effect. If it has alpha, transparent areas will show blur instead of previous clip.

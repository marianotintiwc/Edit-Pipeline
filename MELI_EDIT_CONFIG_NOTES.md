# MELI Local Edit Configuration Notes

## 🟡 MELI EDIT CLASSIC

The standard preset for all MercadoLibre UGC videos. Configuration saved in `presets/meli_edit_classic.json`.

### Clip Order (Always This Structure)

```
Position 1: Introcard → Branded frame (MARCO_MELI.mov)
Position 2: Scene 1   → Talent intro/hook
Position 3: Scene 2   → Talent explanation  
Position 4: B-Roll    → Product/feature demo
Position 5: Scene 3   → Talent CTA/closing
Position 6: Endcard   → Brand overlay (0.5s overlap)
```

### Style Settings (Copy-Paste Ready)

```python
# MELI EDIT CLASSIC - Python dict format
MELI_EDIT_CLASSIC = {
    "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
    "fontsize": 60,
    "stroke_color": "#333333",
    "stroke_width": 10,
    "highlight": {
        "color": "#333333",
        "stroke_color": "#333333",
        "stroke_width": 4
    },
    "introcard_alpha_fill": {
      "enabled": True,
      "use_blur_background": False,
      "invert_alpha": False,
      "auto_invert_alpha": False
    },
    "endcard": {"enabled": True, "overlap_seconds": 0.5},
    "interpolation": {"enabled": True, "target_fps": 60},
    "postprocess": {"color_grading": {"enabled": False}},
    "transcription": {"model": "large"}
}
```

```json
// MELI EDIT CLASSIC - JSON format
{
  "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
  "fontsize": 60,
  "stroke_color": "#333333",
  "stroke_width": 10,
  "highlight": {
    "color": "#333333",
    "stroke_color": "#333333",
    "stroke_width": 4
  },
  "introcard_alpha_fill": {
    "enabled": true,
    "use_blur_background": false,
    "invert_alpha": false,
    "auto_invert_alpha": false
  },
  "endcard": {"enabled": true, "overlap_seconds": 0.5},
  "interpolation": {"enabled": true, "target_fps": 60},
  "postprocess": {"color_grading": {"enabled": false}},
  "transcription": {"model": "large"}
}
```

### Quick Reference Table

| Setting | Value | Docker Path |
|---------|-------|-------------|
| Font | MELI Proxima Nova Bold | `/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF` |
| Font Size | 60 | - |
| Stroke Color | #333333 (dark gray) | - |
| Stroke Width | 10 | - |
| Highlight | #333333 | - |
| Introcard Alpha | embedded (no inversion) | controlled by `introcard_alpha_fill` |
| Endcard Overlap | 0.5 seconds | - |
| Frame Rate | 60 fps (RIFE) | - |
| Whisper Model | large | - |
| Color Grading | disabled | - |
| Audio Codec | AAC 320kbps | - |

---

## �🎯 Quick Reference: Natural Language → Configuration

This document shows how natural language requirements translate to actual API configuration.

### Example Conversation → Working Config

**User said:** "Use the MELI font, fontsize 60, stroke color #333333, stroke width 10, highlight color #333333"

**Translated to:**
```python
style_overrides = {
    # ⚠️ IMPORTANT: Font settings go at TOP LEVEL, not nested under "subtitle"!
    "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
    "fontsize": 60,
    "stroke_color": "#333333",
    "stroke_width": 10,
    "highlight": {
        "color": "#333333",
        "stroke_color": "#333333",
        "stroke_width": 4
    },
    "endcard": {"enabled": True, "overlap_seconds": 0.5},
    "postprocess": {"color_grading": {"enabled": False}},
    "transcription": {"model": "large"}
}
```

---

## 🔍 Introcard vs Endcard Alpha – Findings

- El introcard MELI (MARCO_MELI.mov, codec qtrle, pix_fmt argb) trae un canal alpha correcto de fábrica: el marco amarillo es opaco y la ventana central es transparente.
- La heurística de auto-inversión de máscaras del pipeline podía interpretar ese patrón como "mayormente transparente con algo de opacidad" y decidir invertirlo, haciendo transparente el marco y opaco el centro.
- Para evitar esto en MELI classic, ahora forzamos **no invertir nunca** el alpha del introcard:

```json
"introcard_alpha_fill": {
  "enabled": true,
  "use_blur_background": false,
  "invert_alpha": false,
  "auto_invert_alpha": false
}
```

Conclusión práctica:
- Para introcards diseñados con alpha correcto (como los de MELI), desactivar tanto `invert_alpha` como `auto_invert_alpha` y dejar que el pipeline use el canal alpha tal cual viene del archivo.
- Los endcards y b-rolls siguen pudiendo usar `alpha_fill` y la lógica de detección/inversión cuando haya dudas sobre el canal alpha de origen.

## ⚠️ Critical: style_overrides Structure

**WRONG** ❌ (font nested under "subtitle"):
```json
{
  "style_overrides": {
    "subtitle": {
      "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
      "fontsize": 60
    }
  }
}
```

**CORRECT** ✅ (font at TOP LEVEL):
```json
{
  "style_overrides": {
    "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
    "fontsize": 60,
    "stroke_color": "#333333",
    "stroke_width": 10,
    "highlight": {
      "color": "#333333"
    }
  }
}
```

---

## Clip Order
- scene_1 → scene_2 → broll → scene_3 → endcard

## Subtitle Styling (style_overrides)

| Setting | Value | Notes |
|---------|-------|-------|
| `font` | `/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF` | **TOP LEVEL** |
| `fontsize` | `60` | **TOP LEVEL** |
| `stroke_color` | `#333333` | **TOP LEVEL** |
| `stroke_width` | `10` | **TOP LEVEL** |
| `highlight.color` | `#333333` | Nested under highlight |
| `highlight.stroke_color` | `#333333` | Nested under highlight |
| `highlight.stroke_width` | `4` | Nested under highlight |

## Endcard
- Enabled: true
- Overlap seconds: 0.5
- URL: Passed via `style_overrides.endcard.url`

## Interpolation
- Enabled: true
- Target FPS: 60

## Postprocess
- Color grading: disabled (`enabled: false`)

## Audio
- Background music: `"random"` (picks from assets/audio/)
- Voice audio from scenes is preserved
- Output codec: AAC 320kbps

## Cache
- MELI cache directory: assets/meli_cache
- Clear cache to force re-download of updated B-rolls

---

## 🔧 Debugging Tips

1. **No audio in output?** Check that clips have audio tracks
2. **Wrong font?** Ensure font path is at TOP LEVEL in style_overrides
3. **Check logs:** Look for "Applied X style overrides" - should be 9+ for MELI config
4. **Audio codec:** AAC = correct, MP3 = might indicate older config

---

## 🌐 Uso MELI con RunPod y ugc_client

### Docker Image

La imagen Docker validada para presets MELI es:
- `marianotintiwc/ugc-pipeline:latestv_1.06`

### Cliente Externo (ugc_client.py)

Para disparar jobs MELI desde otros repos/workspaces:

1. Copia `ugc_client.py` al proyecto externo
2. Configura `RUNPOD_API_KEY` y `RUNPOD_ENDPOINT_ID`
3. Usa el preset MELI con per-clip customization:

```python
from ugc_client import UGCPipelineClient

client = UGCPipelineClient(api_key="...", endpoint_id="...")

payload = {
    "input": {
        "geo": "MLB",
        "clips": [
            {"type": "scene", "url": "..."},
            {"type": "scene", "url": "..."},
            {
                "type": "broll",
                "url": "...",
                "alpha_fill": {"enabled": True, "blur_sigma": 60}
            },
            {"type": "scene", "url": "...", "end_time": -0.1},
            {
                "type": "endcard",
                "url": "...",
                "overlap_seconds": 0.5,
                "alpha_fill": {"enabled": True, "blur_sigma": 30}
            }
        ],
        "music_url": "random",
        "subtitle_mode": "auto",
        "style_overrides": {
            "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
            "fontsize": 60,
            "stroke_color": "#333333",
            "stroke_width": 10,
            "transcription": {"model": "large"}
        }
    }
}

result = client.submit_job_sync(payload)
print(result["output"]["output_url"])
```

#### Caso puntual: 226_pix_no_credito-MLB-male_MELI_EDIT.mp4

Para este b-roll (alpha con ruido en negros), usar `alpha_levels` para aplastar el fondo antes del blur:

```json
{
  "type": "broll",
  "url": ".../226_pix_no_credito-MLB-male_MELI_EDIT.mp4",
  "alpha_fill": {
    "enabled": true,
    "force_chroma_key": true,
    "chroma_key_color": "0x000000",
    "alpha_levels": {
      "enabled": true,
      "black": 0.05,
      "white": 1.0,
      "gamma": 1.0
    }
  }
}
```

### Prioridad de Configuración

1. `clips[].alpha_fill` / `clips[].overlap_seconds` (per-clip) — **mayor prioridad**
2. `style_overrides` en el request
3. `style.json` global (defaults del servidor)

### Referencias

- **README.md** → Sección "Cliente Externo: ugc_client.py" con ejemplos completos
- **API_DOCUMENTATION.md** → Sección "Ejemplo Completo MELI" con payload JSON detallado
- **Helper Scripts/run_meli_edit.py** → Para casos MELI pre-configurados (batch processing)

---

## 📊 Batch Processing

### Running Large Batches

For processing many MLB projects (45+), use the batch scripts with persistent logging:

```powershell
cd Edit-Pipeline
python batch_even_mlb_3workers.py  # Even-numbered projects
python batch_odd_mlb_3workers.py   # Odd-numbered projects
```

### Monitoring Progress

**Log files created automatically:**
- `batch_log_YYYYMMDD_HHMMSS.txt` - Full timeline with timestamps
- `batch_progress_YYYYMMDD_HHMMSS.json` - JSON status for programmatic access

**Watch live progress:**
```powershell
Get-Content batch_log_*.txt -Wait -Tail 10
```

**Check JSON status:**
```powershell
Get-Content batch_progress_*.json | ConvertFrom-Json
```

### Why File Logging?

Terminal sessions can close unexpectedly during long-running batches. File-based logging ensures:
- Progress survives terminal closures
- Multiple monitoring options
- Post-mortem debugging of failures
- Clear record of completed/failed jobs

---

## 🛠️ Unified Tools CLI

All common operations are now available via a single `tools.py` script:

```bash
# Generate mapping files
python tools.py mapping              # MLB edit mapping
python tools.py assets               # MELI asset map

# Batch processing
python tools.py batch-runpod -w 3 -f even     # Even projects, 3 workers
python tools.py batch-runpod -w 3 -f odd      # Odd projects, 3 workers
python tools.py batch-runpod -w 3 -f "2,4,6"  # Specific projects

# Check status
python tools.py status --tail 20     # Latest progress + last 20 log lines
```

See README.md for full documentation.
---

## 📦 Batch Edit from S3 CSV (Production Workflow)

### Successful Production Run (February 2026)

Processed **229 videos** in a single batch submission:
- **SMART**: 174 videos (MLA:37, MLB:64, MLC:38, MLM:35)
- **TAP**: 55 videos (MLB only)

### Three-Step Workflow

```bash
# Step 1: Export S3 assets to CSV (s3_assets_report.csv)
# Contains: Parent Folder, Filename, Type, Public URL, Finished

# Step 2: Structure the CSV with product/GEO mapping
python3 assets/IGNOREASSETS/build_s3_assets_mapping.py
# Output: assets/IGNOREASSETS/s3_assets_structured.csv (229 rows)

# Step 3: Submit all jobs to RunPod
python3 "Helper Scripts/run_meli_from_structured_csv.py"
# Result: 229/229 jobs submitted
```

### Folder Naming Convention

The script parses folder names to extract product type and GEO:

| Pattern | Product | GEO | Detection |
|---------|---------|-----|-----------|
| `56_smart_2-MLB-male` | SMART | MLB | `_smart` + `-(MLB)-` |
| `500_tap-MLB-female` | TAP | MLB | `_tap` + `-(MLB)-` |
| `1_smart_2-MLA-female` | SMART | MLA | `_smart` + `-(MLA)-` |

**Regex patterns:**
- Product: `_tap` or `_tap-` → TAP, otherwise `_smart` → SMART
- GEO: `-(ML[ABLCM])-` captures MLA/MLB/MLC/MLM

### Asset Mapping by Product

| Product | GEO | Endcard File | B-Roll File |
|---------|-----|--------------|-------------|
| **SMART** | MLA | `MLA- Conseguí tu Point Smart.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLA_9X16.mov` |
| **SMART** | MLB | `MLB- Compre sua maquininha.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLB_9X16.mov` |
| **SMART** | MLC | `MLC- Compra tu Point Smart.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLC_9X16.mov` |
| **SMART** | MLM | `MLM- Consigue tu Terminal.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLM_9X16.mov` |
| **TAP** | MLB | `MLB - Venda com Tap do Mercado Pago.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_TAP_MLB_9X16.mov` |

### Final Clip Structure

Each job uses this exact clip order:
```
introcard → scene1 → scene2 → broll → scene3 → endcard
```

### Key Files

| File | Purpose |
|------|---------|
| `s3_assets_report.csv` | Raw S3 bucket export (input) |
| `assets/IGNOREASSETS/mov_mapping.csv` | Maps (GEO, Product) → Endcard + B-Roll |
| `assets/IGNOREASSETS/s3_assets_structured.csv` | Processed CSV ready for batch (output) |
| `assets/IGNOREASSETS/build_s3_assets_mapping.py` | Script to structure the CSV |
| `Helper Scripts/run_meli_from_structured_csv.py` | Script to submit batch jobs |
| `presets/meli_cases.json` | Base style config + default introcard URL |

### What Worked Well

1. **Automated product detection** - No manual tagging needed
2. **Single script submission** - 229 jobs in one command
3. **Rate limiting** - 0.5s delay every 10 jobs prevents API throttling
4. **Correct asset mapping** - TAP vs SMART automatically routed to correct endcard/b-roll
5. **Consistent output naming** - `{parent_folder}_MELI_EDIT.mp4`
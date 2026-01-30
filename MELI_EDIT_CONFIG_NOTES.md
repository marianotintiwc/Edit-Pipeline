# MELI Local Edit Configuration Notes

## � MELI EDIT CLASSIC

The standard preset for all MercadoLibre UGC videos. Configuration saved in `presets/meli_edit_classic.json`.

### Clip Order (Always This Structure)

```
Position 1: Scene 1   → Talent intro/hook
Position 2: Scene 2   → Talent explanation  
Position 3: B-Roll    → Product/feature demo
Position 4: Scene 3   → Talent CTA/closing
Position 5: Endcard   → Brand overlay (0.5s overlap)
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
- `marianotintiwc/ugc-pipeline:latestv_1.02`

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

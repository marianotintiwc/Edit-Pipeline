# UGC Pipeline - RunPod API Documentation

## Overview

This serverless API processes UGC-style videos with automatic subtitles, transitions, b-roll effects, endcards, and optional frame interpolation. Videos are automatically uploaded to S3.

---

## Endpoint

Once deployed to RunPod, your endpoint will be:
```
https://api.runpod.ai/v2/{YOUR_ENDPOINT_ID}/runsync
```

**Headers:**
```
Authorization: Bearer {YOUR_RUNPOD_API_KEY}
Content-Type: application/json
```

---

## Request Format

### Basic Example (3 Scenes + B-roll + Endcard)

```json
{
  "input": {
    "project_name": "my_video-MLA",
    "geo": "MLA",
    "clips": [
      {
        "url": "https://your-bucket.s3.amazonaws.com/scene1.mp4",
        "type": "scene"
      },
      {
        "url": "https://your-bucket.s3.amazonaws.com/scene2.mp4",
        "type": "scene"
      },
      {
        "url": "https://your-bucket.s3.amazonaws.com/broll.mp4",
        "type": "broll"
      },
      {
        "url": "https://your-bucket.s3.amazonaws.com/scene3.mp4",
        "type": "scene"
      }
    ],
    "music_url": "random",
    "subtitle_mode": "auto"
  }
}
```

### Private S3 Assets (Presigned URLs)

If your assets are private, you **must** send **presigned URLs**. The RunPod container cannot access your local AWS profile.

**Important:** Do not pre-encode keys before signing; double-encoding produces 404s. Normalize MP-Users asset keys to **NFD** and treat `+` as space when building the presigned URL.

### Full Example (All Options)

```json
{
  "input": {
    "project_name": "campaign_video-MLB",
    "geo": "MLB",
    "clips": [
      {
        "url": "https://bucket.s3.amazonaws.com/intro.mp4",
        "type": "scene",
        "start_time": 0.5,
        "end_time": 10.0
      },
      {
        "url": "https://bucket.s3.amazonaws.com/talking.mp4",
        "type": "scene"
      },
      {
        "url": "https://bucket.s3.amazonaws.com/product_shot.mp4",
        "type": "broll"
      },
      {
        "url": "https://bucket.s3.amazonaws.com/outro.mp4",
        "type": "scene",
        "end_time": -0.5
      }
    ],
    "music_url": "https://bucket.s3.amazonaws.com/background_music.mp3",
    "music_volume": 0.25,
    "loop_music": true,
    "subtitle_mode": "auto",
    "enable_interpolation": true,
    "rife_model": "rife-v4",
    "style_overrides": {
      "transcription": {
        "model": "large"
      },
      "postprocess": {
        "grain": {
          "enabled": false
        }
      }
    }
  }
}
```

---

## Input Parameters

### Required

| Parameter | Type | Description |
|-----------|------|-------------|
| `clips` | array | List of video clips to process (see Clip Object below) |

### Optional

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_name` | string | auto-generated | Project identifier. **Include GEO suffix for endcard** (e.g., `"my_video-MLA"`) |
| `geo` | string | `null` | Geographic region. Accepts MercadoLibre geos (`MLA`, `MLB`, `MLC`, `MLM`) or country codes (`AR`, `BR`, `CL`, `MX`). Maps: CL→MLC, AR→MLA, BR→MLB, MX→MLM, etc. Affects Whisper language. |
| `output_bucket` | string | `S3_BUCKET` env | Override S3 bucket for output. Use with `output_folder` to write to a specific bucket. If `ALLOWED_S3_BUCKETS` env is set, bucket must be in allowed list. |
| `music_url` | string | `null` | URL to music file, `"random"` for random from assets, or `null` for no music |
| `music_volume` | float | `0.3` | Music volume (0.0 - 1.0) |
| `loop_music` | bool | `true` | Loop music to match video length |
| `subtitle_mode` | string | `"auto"` | `"auto"` (Whisper), `"manual"` (provide SRT), or `"none"` |
| `manual_srt_url` | string | `null` | URL to SRT file (required if `subtitle_mode: "manual"`) |
| `enable_interpolation` | bool | `true` | Enable RIFE frame interpolation |
| `input_fps` | float | `24` | Source video frame rate for RIFE interpolation (e.g., 24, 30). Must match your source clips. |
| `rife_model` | string | `"rife-v4"` | RIFE model: `"rife-v4"` or `"rife-v4.6"` |
| `style_overrides` | object | `null` | Override any `style.json` settings. Use `resolution: [1920, 1080]` for 16:9, `[1080, 1920]` for 9:16. Use `endcard: { enabled: true, overlap_seconds: 0.5 }` for endcard overlap with scene 3. |
| `output_filename` | string | auto | Custom output filename |
| `output_folder` | string | `outputs/{job_id}/` | S3 key prefix (folder path) for output. Combined with `output_bucket` or `S3_BUCKET` env. |
| `aspect_ratio` | string | `"9:16"` | Output aspect ratio: `"9:16"` (1080x1920 vertical) or `"16:9"` (1920x1080 horizontal). Pass via `style_overrides.resolution` as `[width, height]` for custom sizes. |

### Common 404 Cause (Assets Not Found)
- The asset **filename in S3 must match exactly** (including accents/spacing).
- If you see 404s on endcards/b-rolls, list the bucket and update the CSV with the real key name.

### Clip Object

```json
{
  "url": "https://...",      // Required: Video URL (http/https/s3)
  "type": "scene",           // Required: "scene", "broll", "endcard" or "introcard"
  "start_time": 0.0,         // Optional: Trim start (seconds)
  "end_time": 10.0,          // Optional: Trim end (seconds, use negative to cut from end)
  "alpha_fill": {},          // Optional: Per-clip override for alpha-fill (broll/endcard)
  "overlap_seconds": 0.5,    // Optional: Per-clip endcard overlap
  "effects": {}              // Optional: Per-clip effects (future)
}
```

**Clip Types:**
- `"scene"` / `"talking_head"` — Main footage with subtitles
- `"broll"` — B-roll with blur/transparency background fill (chroma key effect)
- `"endcard"` — Branded endcard with optional alpha fill and overlap
- `"introcard"` — Intro frame overlay; for MELI classic we use the embedded alpha as-is (no inversion)

**Trim Examples:**
- `"end_time": 10.0` — Cut video at 10 seconds
- `"end_time": -0.5` — Cut 0.5 seconds before the natural end
- `"start_time": 2.0, "end_time": 8.0` — Use only seconds 2-8

**Nota:** `"end_time": -1` recorta **1 segundo completo** del final del clip.

---

## Frame Interpolation (RIFE)

RIFE interpolates source frames to achieve smooth 60fps output.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enable_interpolation` | `true` | Enable/disable RIFE |
| `input_fps` | `24` | Source video FPS. **Must match your clips** (e.g., 24 for lipsync outputs, 30 for raw camera footage) |
| `rife_model` | `"rife-v4"` | Model variant |

**Target FPS:** Always 60 (hardcoded).

**Example:** If your source videos are 30fps:
```json
{
  "input": {
    "clips": [...],
    "input_fps": 30
  }
}
```

---

## Audio Processing

| Parameter | Default | Description |
|-----------|---------|-------------|
| `music_volume` | `0.03` | Background music volume (0.0-1.0) |
| `music_peak` | `0.04` | Peak limiter threshold — prevents volume spikes |
| `loop_music` | `true` | Loop music to match video length |

The peak limiter automatically reduces music volume if it exceeds the threshold, preventing harsh spikes in the final mix.

**Override via style_overrides:**
```json
{
  "input": {
    "clips": [...],
    "style_overrides": {
      "audio": {
        "music_volume": 0.04,
        "music_peak": 0.06
      }
    }
  }
}
```

---

## Per-Clip Customization (broll/endcard)

**Priority (highest → lowest):**
1. `clips[].alpha_fill` / `clips[].overlap_seconds`
2. `style_overrides` in the request
3. `style.json` defaults

**Nota:** `alpha_detection` es global (no por-clip). Se define en `style_overrides.alpha_detection` o en `style.json`.

### Endcard Overlap + Audio Fade (Scene 3)

- The last **N seconds** of Scene 3 overlap the first **N seconds** of the endcard when `endcard.overlap_seconds = N`.
- Scene 3 audio fades out during that overlap using `endcard.audio_fade_seconds` (default: `0.1s`).
- The fade only applies when overlap is greater than 0.

### B-roll Alpha Channel Fix (Important!)

**Problem:** Some b-roll assets (especially TAP/MLB .mov files) appear with inverted alpha channels in the output—the transparent areas become opaque and vice versa.

**Cause:** The `auto_invert_alpha` feature incorrectly detects these assets as needing inversion.

**Solution:** Explicitly disable auto-inversion in `style_overrides`:

```json
{
  "input": {
    "clips": [...],
    "style_overrides": {
      "broll_alpha_fill": {
        "enabled": true,
        "invert_alpha": false,
        "auto_invert_alpha": false
      }
    }
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `false` | Enable alpha compositing for b-roll |
| `invert_alpha` | bool | `false` | Manually invert the alpha channel |
| `auto_invert_alpha` | bool | `true` | Auto-detect if alpha needs inversion (can cause issues!) |

**Recommendation:** For MELI TAP assets, always set `auto_invert_alpha: false` to preserve the original alpha channel.

**Example:** b-roll con blur fuerte y endcard con overlap distinto

```json
{
  "input": {
    "project_name": "demo-MLA",
    "geo": "MLA",
    "clips": [
      {"type": "scene", "url": "https://.../scene1.mp4"},
      {"type": "scene", "url": "https://.../scene2.mp4"},
      {
        "type": "broll",
        "url": "https://.../broll.mp4",
        "alpha_fill": {
          "enabled": true,
          "blur_sigma": 60,
          "slow_factor": 1.6,
          "alpha_levels": {
            "enabled": true,
            "black": 0.05,
            "white": 1.0,
            "gamma": 1.0
          }
        }
      },
      {"type": "scene", "url": "https://.../scene3.mp4"},
      {
        "type": "endcard",
        "url": "https://.../endcard.mov",
        "overlap_seconds": 1.25,
        "alpha_fill": {
          "enabled": true,
          "blur_sigma": 30,
          "slow_factor": 1.2
        }
      }
    ],
    "music_url": "random",
    "subtitle_mode": "auto",
    "style_overrides": {
      "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
      "fontsize": 60,
      "stroke_color": "#333333",
      "stroke_width": 10,
      "alpha_detection": {
        "use_ffprobe": true,
        "verbose": true
      },
      "transcription": {"model": "large"}
    }
  }
}
```

---

## 🎬 Ejemplo Completo MELI (3 escenas + b-roll + endcard)

Payload listo para copiar que ilustra todas las opciones de customización per-clip.

```json
{
  "input": {
    "project_name": "campaign_MLB_cofrinhos",
    "geo": "MLB",
    "output_folder": "MLB_Exports/2026-01",
    "output_filename": "cofrinhos_MELI_EDIT.mp4",
    "clips": [
      {
        "type": "scene",
        "url": "https://bucket.s3.amazonaws.com/scene_1_lipsync.mp4"
      },
      {
        "type": "scene",
        "url": "https://bucket.s3.amazonaws.com/scene_2_lipsync.mp4"
      },
      {
        "type": "broll",
        "url": "https://bucket.s3.amazonaws.com/broll_cofrinhos.mp4",
        "alpha_fill": {
          "enabled": true,
          "blur_sigma": 60,
          "slow_factor": 1.5,
          "force_chroma_key": true,
          "chroma_key_color": "0x1F1F1F",
          "chroma_key_similarity": 0.01,
          "edge_feather": 5
        }
      },
      {
        "type": "scene",
        "url": "https://bucket.s3.amazonaws.com/scene_3_lipsync.mp4",
        "end_time": -0.1
      },
      {
        "type": "endcard",
        "url": "https://bucket.s3.amazonaws.com/endcard_MLB.mov",
        "overlap_seconds": 0.5,
        "alpha_fill": {
          "enabled": true,
          "blur_sigma": 30,
          "slow_factor": 1.2,
          "force_chroma_key": true,
          "chroma_key_color": "0x1F1F1F"
        }
      }
    ],
    "music_url": "random",
    "subtitle_mode": "auto",
    "enable_interpolation": true,
    "style_overrides": {
      "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
      "fontsize": 60,
      "stroke_color": "#333333",
      "stroke_width": 10,
      "highlight": {
        "color": "#333333",
        "stroke_color": "#333333",
        "stroke_width": 4
      },
      "transcription": {"model": "large"},
      "postprocess": {"color_grading": {"enabled": false}},
      "endcard": {"enabled": true, "overlap_seconds": 0.5}
    }
  }
}
```

### Campos alpha_fill Soportados

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Activa el efecto de fondo blur |
| `blur_sigma` | float | `8` | Intensidad del blur de fondo |
| `slow_factor` | float | `1.5` | Factor de slowmo del fondo (≥1.0) |
| `force_chroma_key` | bool | `false` | Fuerza chroma key aunque el asset tenga alpha |
| `chroma_key_color` | string | `"0x000000"` | Color a eliminar (hex) |
| `chroma_key_similarity` | float | `0.08` | Tolerancia del chroma key |
| `chroma_key_blend` | float | `0.0` | Blend del chroma key |
| `edge_feather` | int | `0` | Suavizado de bordes |
| `alpha_levels.enabled` | bool | `false` | Activa niveles sobre la máscara alpha |
| `alpha_levels.black` | float | `0.0` | Umbral de negros (aplastar ruido) |
| `alpha_levels.white` | float | `1.0` | Umbral de blancos |
| `alpha_levels.gamma` | float | `1.0` | Gamma de la máscara |
| `alpha_levels.clamp_min` | float | `0.0` | Clamp mínimo posterior |
| `alpha_levels.clamp_max` | float | `1.0` | Clamp máximo posterior |

### Campos alpha_detection Soportados

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `use_ffprobe` | bool | `true` | Usa ffprobe para detectar alpha (fallback a ffmpeg si no está disponible) |
| `verbose` | bool | `false` | Imprime logs detallados de detección y decisiones de alpha |

### Notas sobre alpha en introcard y endcard (Hallazgos)

- Los assets de endcard (por ejemplo, ProRes 4444) siguen usando la detección automática de alpha y `alpha_fill` según configuración.
- Para el introcard MELI (MARCO_MELI.mov, qtrle/argb) verificamos que el canal alpha de origen ya es correcto: marco amarillo opaco y ventana central transparente.
- La heurística de auto-inversión podía invertir erróneamente esta máscara y hacer transparente el marco, por lo que **para MELI classic se desactivó cualquier inversión de alpha en introcard**.

Config recomendada para evitar inversiones inesperadas en MELI classic:

```json
"introcard_alpha_fill": {
  "enabled": true,
  "use_blur_background": false,
  "invert_alpha": false,
  "auto_invert_alpha": false
}
```

Esto asegura que el introcard utilice el alpha tal como viene del archivo de diseño y que solo los endcards/b-rolls sigan usando lógica de detección/inversión automática cuando sea necesario.

### Notas

- **`end_time` negativo**: `-0.1` recorta 0.1s antes del final real del clip.
- **`overlap_seconds`**: Solo aplica a clips tipo `endcard`; controla cuánto se solapa con el clip anterior.
- **`effects`**: Campo reservado para futuras extensiones (validado pero sin impacto actual).

---

## Response Format

### Success

```json
{
  "output": {
    "output_url": "https://your-bucket.s3.amazonaws.com/outputs/job123/final.mp4",
    "message": "Video processed successfully in 120.5s",
    "duration_seconds": 45.2,
    "file_size_mb": 28.5,
    "logs": [
      "Starting job job123",
      "Validating input parameters...",
      "Step 1/6: Downloading 4 clips...",
      "Step 2/6: Processing clips...",
      "Step 3/6: Generating subtitles...",
      "Step 4/6: Applying postprocess...",
      "Step 5/6: Exporting video...",
      "Step 6/6: Uploading to S3...",
      "Job completed successfully in 120.5s"
    ]
  }
}
```

### Error

```json
{
  "output": {
    "error": "Invalid clip format: missing 'url' field",
    "error_type": "ValidationError",
    "logs": ["Starting job job123", "Validating input parameters..."]
  }
}
```

---

## GEO & Language Detection

| GEO | Language | Endcard |
|-----|----------|---------|
| `MLA` | Spanish | Argentina endcard |
| `MLB` | Portuguese | Brazil endcard |
| `MLM` | Spanish | Mexico endcard |
| `MLC` | Spanish | Chile endcard |

**Endcard is auto-added** based on the `-MLA`, `-MLB`, or `-MLM` suffix in `project_name`.

---

## Automatic Processing Features

Based on `style.json` configuration:

| Feature | Description |
|---------|-------------|
| **Subtitles** | Auto-transcribed via Whisper (large model), animated pop-in style |
| **B-roll Effect** | Blur background + chroma key for transparency (type: "broll") |
| **Transitions** | Slide transitions between clips |
| **Color Grading** | Brightness, contrast, saturation adjustments |
| **Film Grain** | Subtle grain overlay for cinematic look |
| **Vignette** | Edge darkening effect |
| **Frame Interpolation** | RIFE `input_fps`→60fps upscaling (default input: 24fps, configurable via payload) |
| **Music Peak Limiter** | Prevents music volume spikes above threshold (default: 0.08) |
| **Endcard** | Auto-appended based on GEO with 1.25s overlap |

---

## S3 Configuration

The final video is automatically uploaded to S3. Configure via environment variables in RunPod:

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_ACCESS_KEY_ID` | ✅ | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | ✅ | AWS secret key |
| `AWS_REGION` | ❌ | Default: `us-east-1` |
| `S3_BUCKET` | ✅ | Default bucket for output videos |
| `ALLOWED_S3_BUCKETS` | ❌ | Comma-separated list of allowed buckets when using `output_bucket`. If set, per-job `output_bucket` must be in this list. |

**Output Path:** `s3://{bucket}/{output_folder}/{filename}` — bucket is `output_bucket` (if provided) or `S3_BUCKET`; folder is `output_folder` or `outputs/{job_id}/`.

**Endcards Path:** `s3://{S3_BUCKET}/assets/endcards/` (upload your endcard files here)

### Geo Mapping (Country Codes)

The `geo` parameter accepts both MercadoLibre geos and ISO country codes:

| Country | Code | Meli Geo |
|---------|------|----------|
| Argentina | AR | MLA |
| Brazil | BR | MLB |
| Chile | CL | MLC |
| Mexico | MX | MLM |
| Colombia | CO | MCO |
| Peru | PE | MPE |
| Uruguay | UY | MLU |
| Ecuador | EC | MEC |
| Venezuela | VE | MLV |

---

## cURL Example

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "project_name": "test_video-MLA",
      "geo": "MLA",
      "clips": [
        {"url": "https://bucket.s3.amazonaws.com/scene1.mp4", "type": "scene"},
        {"url": "https://bucket.s3.amazonaws.com/scene2.mp4", "type": "scene"},
        {"url": "https://bucket.s3.amazonaws.com/broll.mp4", "type": "broll"},
        {"url": "https://bucket.s3.amazonaws.com/scene3.mp4", "type": "scene"}
      ],
      "music_url": "random",
      "subtitle_mode": "auto"
    }
  }'
```

---

## Python Example

```python
import requests

RUNPOD_API_KEY = "your_api_key"
ENDPOINT_ID = "your_endpoint_id"

response = requests.post(
    f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync",
    headers={
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "input": {
            "project_name": "campaign_001-MLA",
            "geo": "MLA",
            "clips": [
                {"url": "https://...", "type": "scene"},
                {"url": "https://...", "type": "scene"},
                {"url": "https://...", "type": "broll"},
                {"url": "https://...", "type": "scene"}
            ],
            "music_url": "random",
            "subtitle_mode": "auto"
        }
    },
    timeout=600  # 10 minutes for long videos
)

result = response.json()
if "output" in result and "output_url" in result["output"]:
    print(f"Video URL: {result['output']['output_url']}")
else:
    print(f"Error: {result}")
```

---

## Style Overrides

You can override any setting from `style.json`:

```json
{
  "input": {
    "clips": [...],
    "style_overrides": {
      "fontsize": 90,
      "highlight": {
        "color": "#FF0000"
      },
      "transcription": {
        "model": "medium",
        "max_words_per_segment": 3
      },
      "postprocess": {
        "grain": {"enabled": false},
        "frame_interpolation": {"enabled": false}
      }
    }
  }
}
```

---

## Presets

| Preset | Description |
|--------|-------------|
| `standard_vertical` | Full processing (default) |
| `no_interpolation` | Skip RIFE frame interpolation |
| `no_subtitles` | Skip subtitle generation |
| `simple_concat` | Basic concatenation only |

```json
{
  "input": {
    "clips": [...],
    "edit_preset": "no_interpolation"
  }
}
```

---

## Error Types

| Error Type | Description |
|------------|-------------|
| `ValidationError` | Invalid input parameters |
| `DownloadError` | Failed to download video/music/SRT |
| `S3Error` | Failed to upload to S3 |
| `InfrastructureError` | RIFE/Vulkan not available |
| `ProcessingError` | Video processing failed |

---

## Limits & Recommendations

- **Max video duration:** ~10 minutes (longer videos may timeout)
- **Recommended GPU:** A40 or A100 (48GB+ VRAM for large Whisper + RIFE)
- **Typical processing time:** 2-3x video duration
- **Supported formats:** MP4, MOV, MKV, WebM

---

## Deployment Checklist

**Docker Image:** `marianotintiwc/ugc-pipeline:latestv_1.06`

1. ✅ Build Docker image: `docker build -t marianotintiwc/ugc-pipeline:latestv_1.06 .`
2. ✅ Push to Docker Hub: `docker push marianotintiwc/ugc-pipeline:latestv_1.06`
3. ✅ Create RunPod serverless endpoint with `marianotintiwc/ugc-pipeline:latestv_1.06`
5. ✅ Set environment variables (AWS credentials, S3_BUCKET)
6. ✅ Upload endcards to S3: `s3://{bucket}/assets/endcards/`
7. ✅ Test with a simple request

---

## ugc_client.py (Cliente Externo)

Para enviar jobs desde otros proyectos/workspaces, copia `ugc_client.py` a tu repo y usa:

```python
from ugc_client import UGCPipelineClient

client = UGCPipelineClient(api_key="...", endpoint_id="...")

# Validar payload antes de enviar
warnings, errors = client.validate_payload(payload, strict=False)

# Enviar job bloqueante
result = client.submit_job_sync(payload)
print(result["output"]["output_url"])
```

Ver README.md para ejemplos completos con preset MELI.

---

## Support

For issues, check the `logs` array in the response for detailed processing information.

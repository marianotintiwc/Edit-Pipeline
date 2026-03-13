# UGC Video Pipeline

A video editing automation pipeline for UGC-style content (9:16 vertical format). Can run locally as a CLI or as a **RunPod Serverless API**.

Note: After a RunPod rollback, manual redeploy or a fresh commit may be required to resume builds.

**Releases:** See [GitHub Releases](https://github.com/marianotintiwc/Edit-Pipeline/releases) for version history. RunPod builds from tags (e.g. `v1.4`, `v1.33`). After pushing a new tag, update the endpoint image or trigger a rebuild so RunPod picks up the new version. **v1.4:** Endpoint auto-detects native alpha on b-roll (ffprobe); uses alpha + blurred background when present, chroma key only when no alpha.

## Features
- Concatenate video clips with smooth transitions
- Add background music with loop and volume control
- Generate "CapCut-style" animated subtitles (auto-transcription via Whisper)
- **RIFE frame interpolation** (24fps → 60fps for smoother motion)
- Post-processing effects: color grading, grain, vignette
- Export to vertical MP4 (1080x1920)
- **RunPod Serverless deployment** for scalable cloud processing

---

## 🎬 MELI EDIT CLASSIC Preset

The standard configuration for MercadoLibre UGC videos. Full preset saved in `presets/meli_edit_classic.json`.

### Clip Order

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Scene 1 │ → │ Scene 2 │ → │ B-Roll  │ → │ Scene 3 │ → │ Endcard │
│ (talent)│   │ (talent)│   │ (demo)  │   │ (talent)│   │ (brand) │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

### Style Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| **Font** | `MELIPROXIMANOVAA-BOLD.OTF` | MELI Proxima Nova Bold |
| **Font Size** | `60` | Optimized for mobile |
| **Stroke Color** | `#333333` | Dark gray outline |
| **Stroke Width** | `10` | Thick for visibility |
| **Highlight Color** | `#333333` | Karaoke highlight |
| **Endcard Overlap** | `0.5s` | Smooth transition |
| **Endcard Audio Fade** | `0.1s` | Applies only when overlap > 0 |
| **Input FPS** | `24` | Source video FPS (lipsync outputs) |
| **Target FPS** | `60` | RIFE interpolation output |
| **Music Volume** | `0.03` | Background music level |
| **Music Peak** | `0.04` | Peak limiter threshold |
| **Whisper Model** | `large` | Best accuracy |
| **Color Grading** | `disabled` | Raw look |

#### Safe Zones & Margins (Subtitles)

The pipeline enforces safe zones so subtitles stay within approved content areas. Margins are applied by default regardless of profile.

**TikTok (9:16 vertical)** — Reference `margenesdeseguridad_tiktok_new` (540×960):

| Edge | Pixels | Notes |
|------|--------|-------|
| top | 126 | |
| bottom | 54 | |
| left | 60 | |
| right | 120 | |
| zone_height | 780 | |

**UAC 16:9 (horizontal)** — Reference `Margenes UAC_16x9.png` (4000×2250). Zona prohibida en rojo; zona segura en blanco. Calculado con maximal rectangle sobre la imagen.

| Edge | 4000×2250 | 1920×1080 | 1280×720 |
|------|-----------|-----------|----------|
| top | 83 | 40 | 27 |
| bottom | 1050 | 504 | 336 |
| left | 218 | 105 | 70 |
| right | 1074 | 516 | 344 |

Config structure (16:9 reference 1920×1080):

```json
{
  "uac_16x9_margins": {
    "ref_width": 1920,
    "ref_height": 1080,
    "top": 40,
    "bottom": 504,
    "left": 105,
    "right": 516
  }
}
```

#### Subtitle Box (Cajita Aesthetic) and Phrase Length

When `highlight.enabled` is true (MELI/LATAM style), subtitles use a **content-sized box** (“cajita”) per phrase instead of a full-width bar:

- **Background:** The yellow (or `bg_color`) box wraps only the phrase, centered in the safe zone.
- **Wrap:** Long phrases wrap to multiple lines via `highlight.max_chars_per_line` (default: 30). Set in `style_overrides.highlight`.
- **Shorter phrases:** With `word_level: false`, segments can be split by `transcription.max_chars_per_phrase` (e.g. 45) in presets or `style_overrides.transcription`. Long Whisper segments are split at word boundaries with time distributed proportionally.

Config example:

```json
"highlight": {
  "enabled": true,
  "bg_color": "#FFE600",
  "text_color": "#333333",
  "stroke_color": "#333333",
  "stroke_width": 4,
  "max_chars_per_line": 30
},
"transcription": {
  "model": "large",
  "word_level": false,
  "max_chars_per_phrase": 45
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `highlight.max_chars_per_line` | 30 | Max characters per line before wrap (content-sized box) |
| `transcription.max_chars_per_phrase` | — | Optional; split long segments when `word_level` is false |

### S3 Assets (Presigned + Normalization)

- For **private S3 assets**, always send **presigned URLs** (RunPod cannot use your local AWS profile).
- **Do not pre-encode** S3 keys before presigning. Double-encoding can cause 404s.
- For MP-Users assets, treat `+` as space and normalize filenames to **NFD** (macOS-style).
- If you see 404s, verify the exact key in S3 and update the CSV to the real filename.

#### Endcard Alpha Handling

Endcards preserve transparency by default. To fill transparent areas, enable `endcard_alpha_fill` and set `use_blur_background` to `true` (blurred background from the previous clip). Leave `use_blur_background` as `false` to keep transparency.

#### Endcard Audio Overlap + Fade (Scene 3)

- The last **0.5s** of Scene 3 overlaps with the first **0.5s** of the endcard when `endcard.overlap_seconds = 0.5`.
- The Scene 3 audio fades out during that overlap using `endcard.audio_fade_seconds` (default: `0.1s`).
- This fade only applies when overlap is greater than 0.

#### Introcard Alpha Handling (Findings)

For the MELI introcard asset (MARCO_MELI.mov, qtrle/argb), the embedded alpha channel is already correct: the yellow frame is opaque and the central window is transparent. During debugging we confirmed that the previous auto-inversion heuristic could wrongly flip this mask and make the frame transparent while blocking the center.

- The introcard mask is now used as-is for MELI classic: inversion is disabled via `introcard_alpha_fill`.
- Endcards continue to use their own alpha (ProRes 4444) and auto-detection logic unless explicitly overridden.

Recommended config for MELI classic:

```json
"introcard_alpha_fill": {
  "enabled": true,
  "use_blur_background": false,
  "invert_alpha": false,
  "auto_invert_alpha": false
}
```

This keeps the original compositing intent from design: solid yellow frame + transparent center window over the talent video.

#### B-roll Alpha Channel Fix (TAP/MLB Issue - Feb 2026)

**Problem:** TAP b-roll assets (e.g., `MP_SELLERS_AI_VIDEO_GENERICO_TAP_MLB_9X16.mov`) appeared with inverted alpha channels in the final output. The transparent phone screen area showed as opaque, and the opaque hand/phone showed as transparent.

**Root Cause:** The pipeline's `auto_invert_alpha` feature was incorrectly detecting the b-roll alpha channel as needing inversion. This happens when `broll_alpha_fill.enabled` is true but `auto_invert_alpha` is not explicitly disabled.

**Solution:** Explicitly configure `broll_alpha_fill` with `auto_invert_alpha: false` to preserve the original alpha channel:

```json
"broll_alpha_fill": {
  "enabled": true,
  "invert_alpha": false,
  "auto_invert_alpha": false
}
```

**When to Apply:** Use this configuration when:
- B-roll assets have pre-rendered alpha channels (ProRes 4444, QuickTime Animation, etc.)
- TAP product videos where the phone screen should be transparent
- Any b-roll where the alpha channel appears inverted in output

**Debug Process:**
1. Submit a DEBUG job with explicit `broll_alpha_fill` settings
2. Compare output with/without `auto_invert_alpha: false`
3. If alpha is correct with the fix, update your submission script to include this config

### Complete Payload Example

```json
{
  "input": {
    "geo": "MLB",
    "output_folder": "MLB_Exports/2026-01",
    "output_filename": "project_MELI_EDIT.mp4",
    "clips": [
      {"type": "introcard", "url": "https://.../introcard.mov"},
      {"type": "scene", "url": "https://...scene_1_lipsync.mp4"},
      {"type": "scene", "url": "https://...scene_2_lipsync.mp4"},
      {"type": "broll", "url": "https://drive.google.com/uc?export=download&id=..."},
      {"type": "scene", "url": "https://...scene_3_lipsync.mp4"}
    ],
    "music_url": "random",
    "subtitle_mode": "auto",
    "edit_preset": "standard_vertical",
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
      "endcard": {
        "enabled": true,
        "overlap_seconds": 0.5,
        "audio_fade_seconds": 0.1,
        "url": "https://drive.google.com/uc?export=download&id=..."
      },
      "endcard_alpha_fill": {
        "enabled": false,
        "use_blur_background": false
      },
      "introcard_alpha_fill": {
        "enabled": true,
        "use_blur_background": false,
        "invert_alpha": false,
        "auto_invert_alpha": false
      },
      "broll_alpha_fill": {
        "enabled": true,
        "invert_alpha": false,
        "auto_invert_alpha": false
      },
      "interpolation": {"enabled": true, "target_fps": 60},
      "postprocess": {"color_grading": {"enabled": false}},
      "transcription": {"model": "large"}
    }
  }
}
```

### GEO Language Settings

| GEO | Language | Whisper |
|-----|----------|---------|
| `MLB` | Portuguese (Brazil) | `pt` |
| `MLA` | Spanish (Argentina) | `es` |
| `MLC` | Spanish (Chile) | `es` |
| `MLM` | Spanish (Mexico) | `es` |

---

## 📋 Guía Rápida de Requests

### Ejemplo Completo: 3 escenas + 2 b-roll

```json
{
  "input": {
    "geo": "MLA",
    "clips": [
      {"type": "scene", "url": "https://bucket.s3.amazonaws.com/escena1.mp4"},
      {"type": "scene", "url": "https://bucket.s3.amazonaws.com/escena2.mp4"},
      {"type": "broll", "url": "https://bucket.s3.amazonaws.com/broll1.mp4"},
      {"type": "scene", "url": "https://bucket.s3.amazonaws.com/escena3.mp4"},
      {"type": "broll", "url": "https://bucket.s3.amazonaws.com/broll2.mp4"}
    ],
    "music_url": "random",
    "subtitle_mode": "auto",
    "edit_preset": "standard_vertical",
    "style_overrides": {
      "transcription": {"model": "large"}
    }
  }
}
```

### Con Recorte (cortar 0.1s antes del final)

⚠️ **Nota:** `end_time: -1` recorta **1 segundo completo** del final del clip. Usá `-0.1` si solo querés cortar 0.1s.

```json
{
  "input": {
    "geo": "MLA",
    "clips": [
      {"type": "scene", "url": "https://.../escena1.mp4"},
      {"type": "scene", "url": "https://.../escena2.mp4"},
      {"type": "broll", "url": "https://.../broll1.mp4"},
      {"type": "scene", "url": "https://.../escena3.mp4", "end_time": -0.1},
      {"type": "broll", "url": "https://.../broll2.mp4"}
    ],
    "music_url": "random",
    "subtitle_mode": "auto"
  }
}
```

### Para Brasil (Portugués)

```json
{
  "input": {
    "geo": "MLB",
    "clips": [
      {"type": "scene", "url": "https://.../cena1.mp4"},
      {"type": "scene", "url": "https://.../cena2.mp4"},
      {"type": "broll", "url": "https://.../broll1.mp4"},
      {"type": "scene", "url": "https://.../cena3.mp4"},
      {"type": "broll", "url": "https://.../broll2.mp4"}
    ],
    "music_url": "random",
    "subtitle_mode": "auto"
  }
}
```

---

## 🎯 Easy Runner: `run_meli_edit.py`

Simplified interface to run MELI edits using pre-configured cases.

### List Available Cases

```bash
python run_meli_edit.py --list
```

Output:
```
🌎 MLB (Portuguese)
   MLB_COFRINHOS                   Endcard: ✓
   MLB_INCENTIVOS                  Endcard: ✓
   MLB_PIX                         Endcard: ✓
   MLB_PIX_NA_CREDITO              Endcard: ✓
   MLB_PRESTAMO_PERSONAL           Endcard: ✓
   MLB_TARJETA_CREDITO             Endcard: ✓

🌎 MLA (Spanish)
   MLA_CUOTAS_SIN_TARJETA          Endcard: ✓
   MLA_INCENTIVOS                  Endcard: ✓
   ...
```

### Run Single Job

```bash
# Basic usage
python run_meli_edit.py --case MLB_PIX --scenes scene1.mp4 scene2.mp4 scene3.mp4

# With custom output name
python run_meli_edit.py --case MLB_PIX --scenes s1.mp4 s2.mp4 s3.mp4 --output my_project

# Just print the payload (don't submit)
python run_meli_edit.py --case MLB_PIX --scenes s1.mp4 s2.mp4 s3.mp4 --payload-only
```

### Run Batch from JSON File

Create a `jobs.json`:
```json
{
  "output_folder": "MELI_Exports/2026-01",
  "jobs": [
    {
      "case": "MLB_PIX",
      "output_name": "project_001",
      "scenes": ["https://s3.../scene1.mp4", "https://s3.../scene2.mp4", "https://s3.../scene3.mp4"]
    },
    {
      "case": "MLB_COFRINHOS",
      "output_name": "project_002", 
      "scenes": ["https://s3.../scene1.mp4", "https://s3.../scene2.mp4", "https://s3.../scene3.mp4"]
    }
  ]
}
```

Run it:
```bash
python run_meli_edit.py --jobs jobs.json --workers 3
```

### Configuration Files

| File | Purpose |
|------|---------|
| `presets/meli_cases.json` | All GEO + Value Prop → B-roll + Endcard mappings |
| `presets/meli_edit_classic.json` | Base style configuration |
| `presets/jobs_example.json` | Example batch jobs file |

---

### 🔑 Campos Clave

| Campo | Valores | Descripción |
|-------|---------|-------------|
| `geo` | `MLA`, `MLC`, `MLM` = español<br>`MLB` = portugués | Determina idioma de Whisper |
| `clips[].type` | `scene` \| `broll` | Tipo de clip |
| `clips[].url` | URL http/https | Video a descargar |
| `clips[].start_time` | `float` \| `null` | Segundo donde empieza el recorte |
| `clips[].end_time` | `float` \| `null` | Segundo donde termina. **Negativo = cortar desde el final** (ej: `-0.1`) |
| `music_url` | `"random"` \| URL \| `null` | `"random"` = música aleatoria de `assets/audio/` |
| `subtitle_mode` | `auto` \| `manual` \| `none` | Modo de subtítulos |
| `input_fps` | `float` (default: `24`) | FPS del video fuente para interpolación RIFE. Usar `24` para lipsync, `30` para cámara raw |
| `style_overrides.audio.music_volume` | `float` (default: `0.03`) | Volumen de música de fondo |
| `style_overrides.audio.music_peak` | `float` (default: `0.04`) | Límite de picos de volumen de música |
| `style_overrides.transcription.model` | `tiny`, `base`, `small`, `medium`, `large` | Modelo Whisper |

### 📍 Orden de Clips

El orden en el array `clips` es el orden final del video:

```
clips[0] → clips[1] → clips[2] → clips[3] → clips[4]
escena1  → escena2  → broll1   → escena3  → broll2
```

### 🎨 Style Overrides (Personalización de Subtítulos)

**⚠️ IMPORTANTE:** Los settings de fuente van en el **NIVEL SUPERIOR**, no anidados bajo "subtitle".

**CORRECTO ✅:**
```json
{
  "input": {
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
      "endcard": {"enabled": true, "overlap_seconds": 0.5, "url": "https://..."},
      "endcard_alpha_fill": {"enabled": false, "use_blur_background": false},
      "postprocess": {"color_grading": {"enabled": false}},
      "transcription": {"model": "large"}
    }
  }
}
```

**INCORRECTO ❌:**
```json
{
  "style_overrides": {
    "subtitle": {
      "font": "...",
      "fontsize": 60
    }
  }
}
```

| Campo | Nivel | Descripción |
|-------|-------|-------------|
| `font` | TOP | Ruta de fuente (en Docker: `/app/assets/fonts/...`) |
| `fontsize` | TOP | Tamaño de fuente |
| `stroke_color` | TOP | Color del borde del texto |
| `stroke_width` | TOP | Ancho del borde |
| `highlight.color` | Nested | Color del highlight/karaoke |
| `endcard.url` | Nested | URL del endcard |
| `endcard_alpha_fill.use_blur_background` | Nested | Fondo blur para transparencia de endcard |
| `transcription.model` | Nested | Modelo Whisper: `tiny`, `base`, `small`, `medium`, `large` |

---

## 🐍 Cliente Externo: ugc_client.py

Un cliente Python **copiable** para enviar jobs al pipeline desde otros workspaces/proyectos.

### Instalación

1. Copia `ugc_client.py` a tu proyecto
2. Instala dependencias: `pip install requests`
3. Configura variables de entorno:
   ```bash
   export RUNPOD_API_KEY="tu_api_key"
   export RUNPOD_ENDPOINT_ID="tu_endpoint_id"
   ```

### Uso Básico

```python
from ugc_client import UGCPipelineClient

client = UGCPipelineClient(
    api_key="tu_api_key",
    endpoint_id="tu_endpoint_id"
)

payload = client.build_payload({
    "geo": "MLB",
    "clips": [
        {"type": "scene", "url": "https://.../scene1.mp4"},
        {"type": "scene", "url": "https://.../scene2.mp4"},
        {"type": "broll", "url": "https://.../broll.mp4"},
        {"type": "scene", "url": "https://.../scene3.mp4"}
    ],
    "music_url": "random",
    "subtitle_mode": "auto"
})

# Validar antes de enviar (detecta typos y campos inválidos)
warnings, errors = client.validate_payload(payload, strict=False)
for w in warnings:
    print(f"⚠️ {w}")

# Enviar job (bloqueante)
result = client.submit_job_sync(payload)
print(f"Output: {result['output']['output_url']}")
```

### Ejemplo MELI Completo (geo=MLB)

```python
from ugc_client import UGCPipelineClient
import os

client = UGCPipelineClient(
    api_key=os.environ["RUNPOD_API_KEY"],
    endpoint_id=os.environ["RUNPOD_ENDPOINT_ID"]
)

# Payload MELI EDIT CLASSIC con per-clip customization
payload = {
    "input": {
        "project_name": "campaign_MLB_001",
        "geo": "MLB",
        "output_folder": "MLB_Exports/2026-01",
        "clips": [
            {"type": "scene", "url": "https://.../scene_1_lipsync.mp4"},
            {"type": "scene", "url": "https://.../scene_2_lipsync.mp4"},
            {
                "type": "broll",
                "url": "https://.../broll_product.mp4",
                "alpha_fill": {
                    "enabled": True,
                    "blur_sigma": 60,
                    "slow_factor": 1.5,
                    "force_chroma_key": True,
                  "chroma_key_color": "0x1F1F1F",
                  "alpha_levels": {
                    "enabled": True,
                    "black": 0.05,
                    "white": 1.0,
                    "gamma": 1.0
                  }
                }
            },
            {"type": "scene", "url": "https://.../scene_3_lipsync.mp4", "end_time": -0.1},
            {
                "type": "endcard",
                "url": "https://.../endcard_MLB.mov",
                "overlap_seconds": 0.5,
                "alpha_fill": {
                    "enabled": True,
                    "blur_sigma": 30,
                    "slow_factor": 1.2
                }
            }
        ],
        "music_url": "random",
        "subtitle_mode": "auto",
        "enable_interpolation": True,
        "style_overrides": {
            "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
            "fontsize": 60,
            "stroke_color": "#333333",
            "stroke_width": 10,
            "highlight": {"color": "#333333", "stroke_width": 4},
            "transcription": {"model": "large"},
            "postprocess": {"color_grading": {"enabled": False}}
        }
    }
}

# Validar y enviar
warnings, _ = client.validate_payload(payload, strict=False)
for w in warnings:
    print(f"⚠️ {w}")

result = client.submit_job_sync(payload)
print(f"✅ Video: {result['output']['output_url']}")
```

### Alpha Levels (opcional)

Si el alpha del b-roll tiene ruido en negros (manchas/chorreado en el blur), podés “aplastar” esos negros con `alpha_levels` dentro de `alpha_fill`.
Esto normaliza la máscara antes de componer el fondo blur.

### Alpha Detection (ffprobe + verbose)

Para hacer la detección de alpha más clara y auditable, se agregó un bloque opcional en el `style`:

```json
"alpha_detection": {
  "use_ffprobe": true,
  "verbose": true
}
```

Con `verbose=true` se imprimen logs explícitos de:
- pixel format detectado (`pix_fmt`)
- decisión de alpha (detectado/forzado/skipped)
- decisiones de auto-tune (si aplica)

Podés activar esto con `style_overrides` cuando envías el payload.

### Métodos Disponibles

| Método | Descripción |
|--------|-------------|
| `build_payload(input_data)` | Envuelve input en `{"input": ...}` |
| `validate_payload(payload, strict=True)` | Valida tipos y campos; retorna `(warnings, errors)` |
| `submit_job_sync(payload)` | Envía y espera resultado (bloqueante) |
| `submit_job_async(payload)` | Envía y retorna `job_id` inmediatamente |
| `get_job_status(job_id)` | Consulta estado de un job async |

---

## Requirements

### Local Development
- Python 3.10+
- FFmpeg (must be installed and in PATH)
- ImageMagick (required for moviepy TextClip)
- CUDA-capable GPU (recommended for Whisper)

### RunPod Serverless (Docker)
- Docker with NVIDIA GPU support
- RunPod account with serverless access
- AWS S3 bucket for output storage

### Environment Variables

| Variable | Uso | Descripción |
|----------|-----|-------------|
| `RUNPOD_API_KEY` | Cliente externo | API key de RunPod |
| `RUNPOD_ENDPOINT_ID` | Cliente externo | ID del endpoint serverless |
| `AWS_ACCESS_KEY_ID` | Handler (Docker) | Credenciales S3 |
| `AWS_SECRET_ACCESS_KEY` | Handler (Docker) | Credenciales S3 |
| `AWS_REGION` | Handler (Docker) | Región S3 (default: `us-east-1`) |
| `S3_BUCKET` | Handler (Docker) | Bucket para outputs |

---

## 🚀 RunPod Serverless Deployment

**Docker Image:** `docker.io/marianotintiwc/edit-pipeline:latest`

### Quick Start

1. **Build the Docker image:**
   ```bash
  docker build -t docker.io/marianotintiwc/edit-pipeline:latest .
   ```

2. **Test locally with GPU:**
   ```bash
  docker run --gpus all -it docker.io/marianotintiwc/edit-pipeline:latest python startup_check.py
   ```

3. **Tag and push to Docker Hub:**
   ```bash
   # Tag adicional con fecha
  docker tag docker.io/marianotintiwc/edit-pipeline:latest docker.io/marianotintiwc/edit-pipeline:2026-01-30
   
  # Push todos los tags
  docker push docker.io/marianotintiwc/edit-pipeline:latest
  docker push docker.io/marianotintiwc/edit-pipeline:2026-01-30
   ```

4. **Deploy on RunPod:**
   - Go to RunPod Console → Serverless → New Endpoint
  - Docker image: `docker.io/marianotintiwc/edit-pipeline:latest`
   - Set environment variables (see below)
   - Deploy!

**Cold start with auto subtitles:** The image skips Whisper model preload at startup (`SKIP_WHISPER_PRELOAD=1`) for faster worker readiness. The first job with `subtitle_mode=auto` will download the Whisper large model (~2.9GB) on demand, so that job may take several minutes longer. Set `SKIP_WHISPER_PRELOAD=0` in the endpoint env to preload at startup (slower cold start, faster first subtitle job).

#### Deploy from Docker Hub (recommended when GitHub build hangs)

If deploying from **GitHub** gets stuck at "pulling image moby/buildkit:v0.17.2" (RunPod's build infrastructure), use the **Docker Hub flow** instead—it bypasses RunPod's buildkit entirely:

1. Build locally: `docker build --platform linux/amd64 -t docker.io/marianotintiwc/edit-pipeline:latest .`
2. Push: `docker push docker.io/marianotintiwc/edit-pipeline:latest`
3. In RunPod Console → Serverless → your endpoint → **Container Image** → Import from Docker Registry → `docker.io/marianotintiwc/edit-pipeline:latest`

Use `--platform linux/amd64` if building on Apple Silicon. If the GitHub build still hangs after retries, disable EU regions in the endpoint (known to cause image pull issues).

### RunPod Helper CLI (Consolidated)

All RunPod helper scripts were consolidated into a single CLI:

`Helper Scripts/runpod_cli.py`

This is useful for humans and agents because it standardizes:
- Submitting jobs from a payload file
- Polling and status checks
- Updating the endpoint image (rolling release)

Examples:

```bash
# Submit a job using the default payload
python3 "Helper Scripts/runpod_cli.py" submit

# Submit with a custom payload
python3 "Helper Scripts/runpod_cli.py" submit --payload /path/to/payload.json

# Poll a job
python3 "Helper Scripts/runpod_cli.py" poll <job_id>

# Check status once
python3 "Helper Scripts/runpod_cli.py" status <job_id>

# Update the endpoint image
python3 "Helper Scripts/runpod_cli.py" update-image --image docker.io/marianotintiwc/edit-pipeline:latest
```

Environment variables loaded from `.env`:
- RUNPOD_API_KEY
- RUNPOD_ENDPOINT_ID

Note: Legacy RunPod helper scripts were removed in favor of the consolidated CLI.

### Environment Variables

Set these in your RunPod endpoint configuration:

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS credentials for S3 upload |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS credentials for S3 upload |
| `AWS_REGION` | No | AWS region (default: `us-east-1`) |
| `S3_BUCKET` | Yes | S3 bucket name for output videos |

### API Input Schema

Send a POST request to your RunPod endpoint with this JSON body:

#### New Format (Recommended) - With Scenes + B-Roll

```json
{
  "input": {
    "geo": "MLA",
    "clips": [
      {"type": "scene", "url": "https://example.com/scene1.mp4"},
      {"type": "scene", "url": "https://example.com/scene2.mp4"},
      {"type": "broll", "url": "https://example.com/broll1.mp4"},
      {"type": "scene", "url": "https://example.com/scene3.mp4", "end_time": -0.1},
      {"type": "broll", "url": "https://example.com/broll2.mp4"}
    ],
    "music_url": "random",
    "subtitle_mode": "auto",
    "edit_preset": "standard_vertical",
    "style_overrides": {
      "transcription": {"model": "large"}
    }
  }
}
```

#### Legacy Format (Still Supported)

```json
{
  "input": {
    "video_urls": [
      "https://example.com/video1.mp4",
      "https://example.com/video2.mp4",
      "https://example.com/video3.mp4",
      "https://example.com/video4.mp4"
    ],
    "edit_preset": "standard_vertical",
    "music_url": "https://example.com/background.mp3",
    "music_volume": 0.3,
    "subtitle_mode": "auto"
  }
}
```

#### Input Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| **Video Input (use ONE)** |
| `video_urls` | `string[]` | No* | - | Legacy: list of video URLs (all treated as scenes) |
| `clips` | `object[]` | No* | - | **NEW:** Ordered list of clips with metadata (see below) |
| **Geo & Language** |
| `geo` | `string` | No | `null` | `MLA`, `MLB`, `MLC`, `MLM` - determines Whisper language (MLB=Portuguese, others=Spanish) |
| **Music** |
| `music_url` | `string` | No | `null` | Background music URL, or `"random"` to pick from `assets/audio` |
| `music_volume` | `float` | No | `0.3` | Music volume (0.0-1.0) |
| `loop_music` | `bool` | No | `true` | Loop music to video length |
| **Subtitles** |
| `subtitle_mode` | `string` | No | `auto` | `auto`, `manual`, or `none` |
| `manual_srt_url` | `string` | No | `null` | SRT URL if `subtitle_mode=manual` |
| **Processing** |
| `edit_preset` | `string` | No | `standard_vertical` | Editing preset (see below) |
| `enable_interpolation` | `bool` | No | `true` | Enable RIFE frame interpolation |
| `input_fps` | `float` | No | `24` | Source video FPS for RIFE interpolation (e.g., 24, 30). Must match your source clips. |
| `rife_model` | `string` | No | `rife-v4` | RIFE model variant |
| `style_overrides` | `object` | No | `null` | Override style.json settings |

*Either `video_urls` or `clips` must be provided.

#### Clips Object Schema

Each clip in the `clips` array:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | `string` | No | `scene` | `scene` or `broll` |
| `url` | `string` | Yes | - | Video URL (http/https) |
| `start_time` | `float` | No | `null` | Trim start (seconds) |
| `end_time` | `float` | No | `null` | Trim end (seconds). **Use negative values to cut from end** (e.g., `-0.1` = cut 0.1s before end) |

#### Geo & Language Mapping

| Geo | Country | Whisper Language |
|-----|---------|------------------|
| `MLA` | Argentina | Spanish (`es`) |
| `MLB` | Brazil | Portuguese (`pt`) |
| `MLC` | Chile | Spanish (`es`) |
| `MLM` | Mexico | Spanish (`es`) |
| `music_volume` | `float` | No | `0.3` | Music volume (0.0-1.0) |
| `loop_music` | `bool` | No | `true` | Loop music to video length |
| `subtitle_mode` | `string` | No | `auto` | `auto`, `manual`, or `none` |
| `manual_srt_url` | `string` | No | `null` | SRT URL if `subtitle_mode=manual` |
| `enable_interpolation` | `bool` | No | `true` | Enable RIFE frame interpolation |
| `input_fps` | `float` | No | `24` | Source video FPS for RIFE interpolation (e.g., 24, 30). Must match your source clips. |
| `rife_model` | `string` | No | `rife-v4` | RIFE model variant |
| `style_overrides` | `object` | No | `null` | Override style.json settings |

#### Edit Presets

| Preset | Description |
|--------|-------------|
| `standard_vertical` | Full UGC: 9:16, animated subs, music, RIFE (default) |
| `no_interpolation` | Skip RIFE frame interpolation |
| `no_subtitles` | Disable subtitle generation |
| `simple_concat` | Just concatenate videos, minimal processing |

### API Response

**Success:**
```json
{
  "output_url": "https://your-bucket.s3.amazonaws.com/outputs/job-id/output.mp4",
  "message": "Video processed successfully in 145.2s",
  "duration_seconds": 62.5,
  "file_size_mb": 48.3,
  "logs": ["[12:00:00] [INFO] Starting job abc123", "..."]
}
```

**Error:**
```json
{
  "error": "RIFE binary not found",
  "error_type": "RIFENotAvailableError",
  "logs": ["[12:00:00] [ERROR] Validation failed..."]
}
```

### Example: Python Client (New Format)

```python
import runpod

runpod.api_key = "your-api-key"

# Example: 3 scenes + 2 b-rolls with random music
response = runpod.run_sync(
    endpoint_id="your-endpoint-id",
    input={
        "geo": "MLA",  # Argentina = Spanish
        "clips": [
            {"type": "scene", "url": "https://example.com/scene1.mp4"},
            {"type": "scene", "url": "https://example.com/scene2.mp4"},
            {"type": "broll", "url": "https://example.com/broll1.mp4"},
            {"type": "scene", "url": "https://example.com/scene3.mp4", "end_time": -0.1},
            {"type": "broll", "url": "https://example.com/broll2.mp4"}
        ],
        "music_url": "random",
        "subtitle_mode": "auto",
        "edit_preset": "standard_vertical",
        "style_overrides": {
            "transcription": {"model": "large"}
        }
    }
)

print(f"Output URL: {response['output_url']}")
```

### Example: cURL (New Format)

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "geo": "MLB",
      "clips": [
        {"type": "scene", "url": "https://example.com/scene1.mp4"},
        {"type": "scene", "url": "https://example.com/scene2.mp4"},
        {"type": "broll", "url": "https://example.com/broll1.mp4"},
        {"type": "scene", "url": "https://example.com/scene3.mp4"},
        {"type": "broll", "url": "https://example.com/broll2.mp4"}
      ],
      "music_url": "random",
      "subtitle_mode": "auto"
    }
  }'
```

### Docker Image Details

The Dockerfile uses:
- **Base:** `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
- **RIFE:** `rife-ncnn-vulkan` v20221029 (pinned release)
- **Vulkan:** Full GPU support for RIFE acceleration
- **Whisper:** GPU-accelerated transcription

### Startup Validation

The container validates environment on startup:
- ✅ FFmpeg available
- ✅ ImageMagick available
- ✅ Vulkan GPU support
- ✅ RIFE binary functional
- ✅ CUDA available

If RIFE or Vulkan is missing and `enable_interpolation=true`, jobs will fail with a clear error message.

---

## 💻 Local CLI Usage (Original)

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    py -m pip install -r requirements.txt
    ```

## Modo Fácil (Principiantes)

1.  **Preparar archivos:**
    *   **Videos:**
        *   Opción A (Recomendada): Pon tus videos en la carpeta `assets/video`. Nómbralos con números para ordenarlos (ej: `1.mp4`, `2.mp4`, `10.mp4`).
        *   Opción B: Usa el archivo `config/clips.json` para un control manual.
    *   Pon tu música en `assets/audio/music.mp3`.
    *   **Subtítulos:**
        *   Opción A: Pon tus subtítulos en `assets/subs/subtitles.srt`.
        *   Opción B: **¡No hagas nada!** Si no pones el archivo, el programa escuchará el video y creará los subtítulos automáticamente (necesita internet la primera vez).
    *   (Opcional) Ajusta el estilo en `config/style.json`.

2.  **Ejecutar:**
    *   Haz doble clic en el archivo `run.bat`.
    *   ¡Listo! Tu video aparecerá en la carpeta `exports`.

## Modo Avanzado (CLI)

Si prefieres usar la línea de comandos para especificar archivos distintos:

```bash
py ugc_pipeline.py --clips_config ./config/clips.json --music ./assets/audio/music.mp3 --subtitles ./assets/subs/subtitles.srt --output ./exports/video_final.mp4 --style ./config/style.json
```

### Configuration

See `config/clips.sample.json` and `config/style.sample.json` for configuration examples.
# MELI Local Edit Configuration Notes

## Clip Order
- scene_1  scene_2  broll  scene_3  endcard

## Subtitle Styling (override)
- Font: C:\Users\Usuario\Desktop\LatestEdit Script\Edit-Pipeline\assets\fonts\MELIPROXIMANOVAA-BOLD.OTF
- Font size: 60
- Stroke color: #333333
- Stroke width: 10
- Highlight color: #333333
- Highlight stroke color: #333333
- Highlight stroke width: 4

## Endcard
- Enabled: true
- Overlap seconds: 0.5
- Transparencia: usar `endcard_alpha_fill` (blur opcional con `use_blur_background=true`)

## Interpolation
- Enabled: true
- Target FPS: 60

## Postprocess
- Color grading: disabled (enabled = false)

## Cache
- MELI cache directory: assets/meli_cache
- Cleared to force re-download of updated B-rolls.
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
| `geo` | string | `null` | Geographic region: `"MLA"` (Argentina), `"MLB"` (Brazil), `"MLM"` (Mexico). Affects language detection. |
| `music_url` | string | `null` | URL to music file, `"random"` for random from assets, or `null` for no music |
| `music_volume` | float | `0.3` | Music volume (0.0 - 1.0) |
| `loop_music` | bool | `true` | Loop music to match video length |
| `subtitle_mode` | string | `"auto"` | `"auto"` (Whisper), `"manual"` (provide SRT), or `"none"` |
| `manual_srt_url` | string | `null` | URL to SRT file (required if `subtitle_mode: "manual"`) |
| `enable_interpolation` | bool | `true` | Enable RIFE frame interpolation (30→60fps) |
| `rife_model` | string | `"rife-v4"` | RIFE model: `"rife-v4"` or `"rife-v4.6"` |
| `style_overrides` | object | `null` | Override any `style.json` settings |
| `output_filename` | string | auto | Custom output filename |

### Clip Object

```json
{
  "url": "https://...",      // Required: Video URL (http/https/s3)
  "type": "scene",           // Required: "scene" or "broll"
  "start_time": 0.0,         // Optional: Trim start (seconds)
  "end_time": 10.0           // Optional: Trim end (seconds, use negative to cut from end)
}
```

**Clip Types:**
- `"scene"` / `"talking_head"` — Main footage with subtitles
- `"broll"` — B-roll with blur/transparency background fill (chroma key effect)

**Trim Examples:**
- `"end_time": 10.0` — Cut video at 10 seconds
- `"end_time": -0.5` — Cut 0.5 seconds before the natural end
- `"start_time": 2.0, "end_time": 8.0` — Use only seconds 2-8

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
| **Frame Interpolation** | RIFE 30→60fps upscaling |
| **Endcard** | Auto-appended based on GEO with 1.25s overlap |

---

## S3 Configuration

The final video is automatically uploaded to S3. Configure via environment variables in RunPod:

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_ACCESS_KEY_ID` | ✅ | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | ✅ | AWS secret key |
| `AWS_REGION` | ❌ | Default: `us-east-1` |
| `S3_BUCKET` | ✅ | Bucket for output videos |

**Output Path:** `s3://{S3_BUCKET}/outputs/{job_id}/final.mp4`

**Endcards Path:** `s3://{S3_BUCKET}/assets/endcards/` (upload your endcard files here)

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

1. ✅ Build Docker image: `docker build -t ugc-pipeline:latest .`
2. ✅ Push to registry: `docker push your-registry/ugc-pipeline:latest`
3. ✅ Create RunPod serverless endpoint with the image
4. ✅ Set environment variables (AWS credentials, S3_BUCKET)
5. ✅ Upload endcards to S3: `s3://{bucket}/assets/endcards/`
6. ✅ Test with a simple request

---

## Support

For issues, check the `logs` array in the response for detailed processing information.

# MELI Local Edit Configuration Notes

## 🎯 Quick Reference: Natural Language → Configuration

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

## 🔧 Debugging & Troubleshooting

### Common Issues

#### 1. Wrong Font / Default Font Used
**Symptom:** Subtitles appear in Impact or Arial instead of custom font.

**Cause:** Font settings were nested under `"subtitle"` instead of at **TOP LEVEL**.

**Fix:**
```json
// ❌ WRONG
{"style_overrides": {"subtitle": {"font": "..."}}}

// ✅ CORRECT  
{"style_overrides": {"font": "...", "fontsize": 60}}
```

**Verify:** Look for "Applied X style overrides" in logs. Should be 9+ for full MELI config.

#### 2. No Audio in Output
**Symptom:** Video plays but has no sound.

**Diagnosis:**
```bash
# Check audio with ffmpeg volumedetect
ffmpeg -i output.mp4 -af "volumedetect" -f null NUL
```

**Expected output:**
```
mean_volume: -20.3 dB
max_volume: -7.1 dB
n_samples: 1571422
```

If `n_samples: 0`, audio track is silent/missing.

#### 3. Audio Codec Differences
- **AAC 320kbps:** Correct (newer config)
- **MP3 127kbps:** May indicate older config or fallback

### Verifying Outputs

```python
# Quick Python check for audio
from moviepy.editor import VideoFileClip
clip = VideoFileClip("output.mp4")
print(f"Has audio: {clip.audio is not None}")
print(f"Duration: {clip.duration}s")
```

### Log Messages to Watch

| Log Message | Meaning |
|-------------|---------|
| `Applied 9 style overrides` | Full MELI config applied ✅ |
| `Applied 6 style overrides` | Partial config (check structure) ⚠️ |
| `Audio status: HAS AUDIO` | Audio track present ✅ |
| `Audio status: NO AUDIO!` | Missing audio ❌ |
| `RIFE validation: OK` | Interpolation available ✅ |

---

## 🤖 AI Assistant Notes

This project was developed with AI assistance. Key learnings for future AI interactions:

### Natural Language → Code Translation

When describing video editing requirements in natural language, AI correctly translated:

| User Said | AI Generated |
|-----------|--------------|
| "Use MELI font" | `"font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF"` |
| "fontsize 60" | `"fontsize": 60` |
| "stroke color #333333" | `"stroke_color": "#333333"` |
| "highlight color same as stroke" | `"highlight": {"color": "#333333"}` |
| "disable color grading" | `"postprocess": {"color_grading": {"enabled": false}}` |
| "use large Whisper model" | `"transcription": {"model": "large"}` |

### Common AI Mistakes to Avoid

1. **Nesting structure:** AI may incorrectly nest font settings under `"subtitle": {...}` - they belong at TOP LEVEL
2. **Path formats:** Docker paths use `/app/...`, local paths use Windows format
3. **Boolean values:** JSON uses `true`/`false`, Python uses `True`/`False`

---

## 📊 Batch Processing with Persistent Logging

### Why Persistent Logging?

When running batch jobs that process many videos (e.g., 45+ MLB projects), terminal sessions can become unreliable:
- Terminals may close unexpectedly
- Long-running processes lose visibility
- Progress tracking becomes difficult

### Solution: File-Based Logging

The batch scripts now create **persistent log files** that survive terminal closures:

```
Edit-Pipeline/
├── batch_log_20260122_225114.txt        # Full timestamped log
├── batch_progress_20260122_225114.json  # JSON progress snapshot
```

### Log File Contents

**`batch_log_*.txt`** - Human-readable timeline:
```
[22:51:14] 🚀 Worker 1 | Starting #2: 2_incentivos-MLB-male
[22:51:14] ✅ Worker 1 | #2 submitted: eaa55cc0-0354-4f1b-844c-dd3c61dafa8a-u2
[22:53:45] ✅ Worker 1 | #2 COMPLETED in 151s
[22:53:45] 📊 Progress: 1/45 completed, 0 failed
```

**`batch_progress_*.json`** - Machine-readable status:
```json
{
  "timestamp": "2026-01-22T22:53:45",
  "total": 45,
  "completed": 1,
  "failed": 0,
  "in_progress": 3,
  "elapsed_seconds": 151,
  "completed_jobs": ["2_incentivos-MLB-male"],
  "failed_jobs": []
}
```

### Monitoring Long-Running Batches

**Check progress from any terminal:**
```powershell
# View latest log entries
Get-Content batch_log_*.txt -Tail 20

# Watch live updates
Get-Content batch_log_*.txt -Wait -Tail 10

# Check JSON progress
Get-Content batch_progress_*.json | ConvertFrom-Json
```

**From Python:**
```python
import json
with open("batch_progress_20260122_225114.json") as f:
    progress = json.load(f)
    print(f"Completed: {progress['completed']}/{progress['total']}")
```

### Implementation Pattern

For any batch script processing RunPod jobs, add this logging infrastructure:

```python
import os
from datetime import datetime

LOG_FILE = None
PROGRESS_FILE = None

def init_logging(base_dir: str):
    """Initialize log files with timestamp"""
    global LOG_FILE, PROGRESS_FILE
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    LOG_FILE = os.path.join(base_dir, f"batch_log_{timestamp}.txt")
    PROGRESS_FILE = os.path.join(base_dir, f"batch_progress_{timestamp}.json")
    print(f"📝 Logging to: {LOG_FILE}")
    print(f"📊 Progress file: {PROGRESS_FILE}")

def log(msg: str):
    """Thread-safe logging to console AND file"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

def save_progress(stats: dict):
    """Save current stats to JSON file"""
    if PROGRESS_FILE:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
```

### Best Practices

1. **Call `init_logging()` early** - Before any processing starts
2. **Save progress after each job** - Not just at the end
3. **Include job identifiers** - For debugging specific failures
4. **Use timestamps** - Different files for each run

---

## 🛠️ Unified CLI Tool (`tools.py`)

A single command-line tool for all common pipeline operations.

Newer workflows now live in `python -m ugc_tools` (CSV prep, RunPod monitoring/retry,
and asset/S3 helpers). See `TOOLING.md` for the consolidated CLI usage and
legacy script mapping.

### 🧰 Utilities & Helper Scripts (Catalog)

There are **two layers** of utilities in this repo:

- **Recommended (reusable, configurable)**: `python -m ugc_tools ...`
- **Legacy/one-off scripts**: files in `Helper Scripts/` (many now act as wrappers that call `ugc_tools`)

If you’re trying to do a “common ops task” (prepare CSVs, upload assets to S3, monitor jobs, retry failed jobs),
start with `ugc_tools` and only fall back to `Helper Scripts/` if you need a very specific edge case.

#### `ugc_tools` (recommended entrypoint)

Entry point:

```bash
python -m ugc_tools --help
python -m ugc_tools <area> --help
```

Current areas/commands (see `TOOLING.md` for examples):

| Area | Commands | Purpose |
| --- | --- | --- |
| `csv` | `complete-folders`, `autofill-assets` | Generate/edit config CSVs; autofill assets via `config/ugc_assets_map.json` |
| `runpod` | `monitor`, `retry-from-log` | Poll job status from logs; generate retry CSVs (optionally resubmit) |
| `assets` | `upload-drive`, `replace-urls` | Download Drive assets, upload to S3, then rewrite CSV URLs using the report |
| `s3` | `rename`, `upload-folder` | Safe renames via plan/apply; bulk upload local folders to S3 |

Related configuration files:
- `config/ugc_assets_map.json` (SMART/TAP → GEO → {endcard,broll})
- `config/rename_map_mlm_endcards.json` (example rename map used by `ugc_tools s3 rename`)

#### Helper Scripts (legacy entrypoint, mostly wrappers)

`Helper Scripts/` contains many scripts created during past debugging/production runs.
To keep this maintainable, the canonical documentation is:
- `TOOLING.md` (how to run the tools)
- `TOOLING_INVENTORY.md` (script-by-script purpose + migration map)

Below is the **complete list** of python helper scripts currently in `Helper Scripts/`:

```text
add_broll_endcard_s3_to_belu.py
build_lipsync_routes_csv.py
build_scenes_from_lipsync_3000plus.py
check_belu_status.py
check_belu_status_sample.py
check_belus_basta_status.py
check_missing_job_status.py
check_missing_lipsync_in_s3.py
check_mlb_failed_errors.py
check_mlm_status.py
check_presigned_url.py
check_recent_s3.py
check_retry_errors.py
check_runpod_status_variants.py
check_s3_head.py
check_scene_broll_endcard_matches.py
check_sellers_status.py
check_users_outputs.py
check_users_s3_missing.py
debug_s3.py
download_mlb_assets_and_create_csv.py
download_mlm_assets_and_create_csv.py
extract_and_retry_failed.py
find_failed_latest.py
find_missing_lipsync_folders.py
find_mlb_asset_matches.py
find_mlb_asset_mismatches.py
find_outputs_scene_matches.py
fix_csv_urls.py
fix_users_scene_urls.py
generate_meli_video_asset_map.py
generate_users_url_report.py
list_s3_common_prefixes.py
list_s3_prefix.py
map_lipsync_urls_3000plus.py
meli_assets_mapper.py
monitor_mlb_jobs.py
monitor_sellers_scenes_jobs.py
monitor_users_jobs.py
poll_job.py
presign_users_csv.py
rename_mlb_endcards_s3_fix.py
rename_mlm_endcards_s3.py
replace_users_assets_with_s3.py
resubmit_missing_users_jobs.py
resubmit_mlb_failed.py
retry_failed_broll_tests.py
retry_failed_from_log.py
retry_failed_users_jobs.py
run_belu_batch_safe.py
run_docker_test.py
run_meli_edit.py
run_meli_from_belus_basta_csv.py
run_meli_from_cofrinhos_correction_csv.py
run_meli_from_csv.py
run_meli_from_csv_tap.py
run_meli_from_mla_mlc_mlm_csv.py
run_meli_from_mlb_csv.py
run_meli_from_mlc_csv.py
run_meli_from_mlm_csv.py
run_meli_from_mlm_csv_v2.py
run_meli_from_structured_csv.py
run_meli_from_users_csv.py
run_meli_from_ultimos_v3456789_csv.py
run_mlb_batch_with_poll.py
run_sellers_batch_over_1000.py
run_sellers_batch_parallel.py
run_sellers_from_scenes_csv.py
runpod_cli.py
runpod_poll.py
runpod_status.py
runpod_submit_and_poll.py
submit_broll_tests.py
submit_debug_job.py
submit_mlc_mla_mlm_alpha_fix.py
submit_mlm_jobs.py
submit_pix_no_credito_only.py
summarize_latest_errors.py
summarize_latest_errors_safe.py
update_csv_endcards.py
update_mlb_endcards_real.py
update_mlm_csv_urls.py
update_runpod_endpoint_image.py
upload_brolls_to_s3.py
upload_mlm_brolls.py
upload_users_assets_to_s3.py
```

### Quick Reference

```bash
# Show help
python tools.py --help

# Generate MLB edit mapping (scenes + B-roll + Endcard)
python tools.py mapping

# Generate MELI video asset map  
python tools.py assets

# Batch process on RunPod (cloud GPU)
python tools.py batch-runpod --workers 3 --filter even    # Even-numbered projects
python tools.py batch-runpod --workers 3 --filter odd     # Odd-numbered projects
python tools.py batch-runpod --workers 3 --filter all     # All projects
python tools.py batch-runpod --workers 3 --filter "2,4,6" # Specific projects
python tools.py batch-runpod -w 3 -f even -y              # Skip confirmation

# Process single project locally
python tools.py batch-local --folder "2_incentivos-MLB-male"
python tools.py batch-local --number 2

# Check batch progress
python tools.py status              # Show latest progress
python tools.py status --tail 20    # Show last 20 log lines
```

### Command Details

| Command | Description |
|---------|-------------|
| `mapping` | Parse S3 assets report → generate `mlb_edit_mapping.csv` with scenes + B-roll + Endcard URLs |
| `assets` | Generate `meli_video_asset_map.csv` mapping videos to their assets |
| `batch-runpod` | Submit jobs to RunPod with N workers, auto-retry, progress logging |
| `batch-local` | Run single project through local handler.py |
| `status` | Check batch progress from log files |

### Filter Options for `batch-runpod`

| Filter | Example | Description |
|--------|---------|-------------|
| `even` | `--filter even` | All even-numbered projects (2, 4, 6...) |
| `odd` | `--filter odd` | All odd-numbered projects (1, 3, 5...) |
| `all` | `--filter all` | All projects |
| Numbers | `--filter "2,4,6,8"` | Specific project numbers |
| Single | `--filter 16` | Single project by number |
| Name | `--filter "incentivos"` | Match folder name |
---

## 📦 Batch Edit from S3 CSV (MELI Production Workflow)

This is the **production workflow** for processing large batches of lipsync videos from S3. Successfully used to process 229 videos in a single batch (February 2026).

### Overview

The workflow processes lipsync videos stored in S3, automatically mapping them to the correct endcard and b-roll based on product type (SMART/TAP) and GEO (MLA/MLB/MLC/MLM).

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│ s3_assets_      │ → │ build_s3_assets_     │ → │ s3_assets_      │
│ report.csv      │    │ mapping.py           │    │ structured.csv  │
│ (raw S3 list)   │    │ (parse & map)        │    │ (ready for edit)│
└─────────────────┘    └──────────────────────┘    └─────────────────┘
                                                            │
                                                            ▼
                       ┌──────────────────────┐    ┌─────────────────┐
                       │ run_meli_from_       │ ← │ meli_cases.json │
                       │ structured_csv.py    │    │ (base style)    │
                       │ (submit to RunPod)   │    └─────────────────┘
                       └──────────────────────┘
                                │
                                ▼
                       ┌─────────────────────────────┐
                       │ RunPod Endpoint (v1.07)     │
                       │ 229 parallel jobs           │
                       │ Output: MELI_Exports/       │
                       └─────────────────────────────┘
```

### Step 1: Generate S3 Assets Report

Export your S3 bucket contents to CSV (can use AWS CLI or S3 console):

```csv
Parent Folder,Filename,Type,Public URL,Finished
56_smart_2-MLB-male,56_smart_2-MLB-male_scene_1_lipsync.mp4,video,https://s3.../..._scene_1_lipsync.mp4,Yes
56_smart_2-MLB-male,56_smart_2-MLB-male_scene_2_lipsync.mp4,video,https://s3.../..._scene_2_lipsync.mp4,Yes
56_smart_2-MLB-male,56_smart_2-MLB-male_scene_3_lipsync.mp4,video,https://s3.../..._scene_3_lipsync.mp4,Yes
```

Save as: `Edit-Pipeline/s3_assets_report.csv`

### Step 2: Structure the CSV

Run the mapping script to parse product type, GEO, and map endcard/b-roll:

```bash
python3 assets/IGNOREASSETS/build_s3_assets_mapping.py
```

This:
- Parses parent folder names (e.g., `56_smart_2-MLB-male` → SMART/MLB)
- Filters to only include folders with all 3 lipsync scenes
- Maps to correct endcard and b-roll from `mov_mapping.csv`
- Outputs: `assets/IGNOREASSETS/s3_assets_structured.csv`

**Output structure:**
```csv
Parent Folder,Type,GEO,Scene1_URL,Scene2_URL,Scene3_URL,Endcard_File,Endcard_Local_Path,Endcard_S3_URL,Broll_File,Broll_Local_Path,Broll_S3_URL
56_smart_2-MLB-male,SMART,MLB,https://...scene_1_lipsync.mp4,https://...scene_2_lipsync.mp4,https://...scene_3_lipsync.mp4,MLB- Compre sua maquininha.mov,...
500_tap-MLB-male,TAP,MLB,https://...scene_1_lipsync.mp4,https://...scene_2_lipsync.mp4,https://...scene_3_lipsync.mp4,MLB - Venda com Tap do Mercado Pago.mov,...
```

### Step 3: Submit Batch Jobs

```bash
python3 "Helper Scripts/run_meli_from_structured_csv.py"
```

This submits all rows to RunPod with the correct clip structure:
```
introcard → scene1 → scene2 → broll → scene3 → endcard
```

### Asset Mapping by Product Type

| Product | GEO | Endcard | B-Roll |
|---------|-----|---------|--------|
| **SMART** | MLA | `MLA- Conseguí tu Point Smart.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLA_9X16.mov` |
| **SMART** | MLB | `MLB- Compre sua maquininha.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLB_9X16.mov` |
| **SMART** | MLC | `MLC- Compra tu Point Smart.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLC_9X16.mov` |
| **SMART** | MLM | `MLM- Consigue tu Terminal.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLM_9X16.mov` |
| **TAP** | MLB | `MLB - Venda com Tap do Mercado Pago.mov` | `MP_SELLERS_AI_VIDEO_GENERICO_TAP_MLB_9X16.mov` |

### Folder Naming Convention

The script parses product type and GEO from folder names:

| Pattern | Product | GEO |
|---------|---------|-----|
| `56_smart_2-MLB-male` | SMART | MLB |
| `500_tap-MLB-female` | TAP | MLB |
| `1_smart_2-MLA-female` | SMART | MLA |
| `699_smart_2-MLM-male` | SMART | MLM |

**Regex patterns:**
- Product: `_tap` or `_tap-` → TAP, `_smart` → SMART
- GEO: `-(ML[ABLCM])-` captures MLA/MLB/MLC/MLM

### Configuration Files

| File | Purpose |
|------|---------|
| `assets/IGNOREASSETS/mov_mapping.csv` | Maps (GEO, Product) → Endcard + B-Roll files |
| `assets/IGNOREASSETS/s3_assets_report.csv` | Raw S3 bucket export |
| `assets/IGNOREASSETS/s3_assets_structured.csv` | Processed mapping ready for batch |
| `presets/meli_cases.json` | Base style + default introcard URL |

### Production Run Example (Feb 2026)

```bash
# Step 1: Build structured CSV
python3 assets/IGNOREASSETS/build_s3_assets_mapping.py
# Output: Wrote 229 parents to s3_assets_structured.csv
# Summary: SMART (MLA:37, MLB:64, MLC:38, MLM:35) + TAP (MLB:55)

# Step 2: Submit all jobs
python3 "Helper Scripts/run_meli_from_structured_csv.py"
# Output: Found 229 rows to process
# [1/229] 10_smart_2-MLB-female (SMART/MLB): submitted b69a0b2b-...
# [2/229] 10_tap-MLB-male (TAP/MLB): submitted e90c5f3c-...
# ...
# === Summary ===
# Submitted: 229/229 jobs
```

### Key Scripts

**`assets/IGNOREASSETS/build_s3_assets_mapping.py`:**
- Parses `s3_assets_report.csv`
- Extracts product type (SMART/TAP) and GEO from folder names
- Filters to folders with all 3 lipsync scenes
- Maps to endcard/b-roll from `mov_mapping.csv`
- Outputs `s3_assets_structured.csv`

**`Helper Scripts/run_meli_from_structured_csv.py`:**
- Reads `s3_assets_structured.csv`
- Loads base style from `presets/meli_cases.json`
- Builds payload with: introcard → scene1 → scene2 → broll → scene3 → endcard
- Submits to RunPod endpoint `h55ft9cy7fyi1d`
- Rate limiting: 0.5s delay every 10 jobs
- Output folder: `MELI_Exports/2026-02/{parent}_MELI_EDIT.mp4`

Based on the error logs and details you provided, the 403 Forbidden errors are almost certainly caused by the double URL-encoding in the object paths (e.g., %2520 instead of %20 for spaces). This is a common issue when URLs are generated or stored incorrectly, leading AWS S3 to interpret the path as a literal key that doesn't exist, resulting in a denial (shown as 403 for unauthenticated requests to prevent existence disclosure). Your permissions and policies look solid, so this isn't a pure access control problem—it's about the request not matching the actual stored object keys.
Why Double-Encoding Breaks It

S3 object keys can include spaces (e.g., "MLB - Venda com Tap do Mercado Pago.mov").
In HTTP URLs, spaces must be encoded as %20 (single encoding).
%2520 means the % character itself was encoded ( %25 is the code for %, plus 20), so S3 looks for a key literally containing %20 in the name (e.g., "MLB%20-%20Venda%20com%20Tap%20do%20Mercado%20Pago.mov"), which probably doesn't match what's actually stored.
For public/unauthenticated requests:
If the key exists and is public: 200 OK.
If the key doesn't exist or access is denied: S3 returns 403 (not 404) to avoid leaking info about object existence.

User reports on forums (e.g., Stack Overflow, AWS re:Post) confirm this exact pattern: double-encoding from app logic (like repeated urlencode calls in Python's urllib) causes "phantom" 403s on otherwise public objects.
The summary you shared ("URLs are double-encoded (%2520), which breaks S3 access") nails it. If these URLs are coming from a database, API, or script (e.g., in RunPod), that's where the encoding error originated.

Quick Test to Confirm

In the AWS S3 console, navigate to your bucket (meli-ai.filmmaker) > Find one of the failing objects (e.g., under MP-Sellers/Assets/).
Copy the exact object key (it should show with spaces, not %20).
Generate the correct URL: https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/<path-with-%20-for-spaces>.
Example fix for your first error: Replace %2520 with %20 everywhere, so https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB%20-%20Venda%20com%20Tap%20do%20Mercado%20Pago.mov.

Paste the fixed URL into a browser (incognito mode, no AWS login) and see if it downloads. If yes, encoding was the issue.
If it still 403s, check the exact key in console—maybe the files were uploaded with literal %20 in the name (unlikely, but possible; rename them if so).

How to Fix in Your Setup
Since this is happening in RunPod (likely a script or pod fetching these assets), focus on correcting the URLs at the source or during fetch:

Fix URL Generation/Storage:
Wherever these URLs are created (e.g., in your app code or database), ensure single encoding.
In Python (common for RunPod): Use urllib.parse.quote() once on the path, but not on an already-encoded string.
Bad: quote(quote("MLB - Venda...")) → produces %2520.
Good: quote("MLB - Venda com Tap do Mercado Pago.mov") → %20.

If URLs are stored encoded, decode them first with urllib.parse.unquote() before using.

Handle in Download Script (e.g., RunPod):
Modify the fetch code to decode double-encoding before requesting.
Example in Python (using requests):Pythonimport requests
from urllib.parse import unquote

bad_url = "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB%2520-%2520Venda%2520com%2520Tap%2520do%2520Mercado%2520Pago.mov"
fixed_path = unquote(unquote(bad_url.split('.com/')[1]))  # Double unquote to fix %2520 -> space
fixed_url = f"https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/{fixed_path}"

response = requests.get(fixed_url)
if response.status_code == 200:
    with open("file.mov", "wb") as f:
        f.write(response.content)
else:
    print(f"Failed: {response.status_code} - {response.text}")
This turns %2520 back to %20 in the URL. Test it on one file.
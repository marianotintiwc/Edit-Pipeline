# UGC Video Pipeline

A video editing automation pipeline for UGC-style content (9:16 vertical format). Can run locally as a CLI or as a **RunPod Serverless API**.

## Features
- Concatenate video clips with smooth transitions
- Add background music with loop and volume control
- Generate "CapCut-style" animated subtitles (auto-transcription via Whisper)
- **RIFE frame interpolation** (24fps → 60fps for smoother motion)
- Post-processing effects: color grading, grain, vignette
- Export to vertical MP4 (1080x1920)
- **RunPod Serverless deployment** for scalable cloud processing

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
| `style_overrides.transcription.model` | `tiny`, `base`, `small`, `medium`, `large` | Modelo Whisper |

### 📍 Orden de Clips

El orden en el array `clips` es el orden final del video:

```
clips[0] → clips[1] → clips[2] → clips[3] → clips[4]
escena1  → escena2  → broll1   → escena3  → broll2
```

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

---

## 🚀 RunPod Serverless Deployment

### Quick Start

1. **Build the Docker image:**
   ```bash
   docker build -t ugc-pipeline:latest .
   ```

2. **Test locally with GPU:**
   ```bash
   docker run --gpus all -it ugc-pipeline:latest python startup_check.py
   ```

3. **Push to Docker Hub (or your registry):**
   ```bash
   docker tag ugc-pipeline:latest your-username/ugc-pipeline:latest
   docker push your-username/ugc-pipeline:latest
   ```

4. **Deploy on RunPod:**
   - Go to RunPod Console → Serverless → New Endpoint
   - Select your Docker image
   - Set environment variables (see below)
   - Deploy!

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

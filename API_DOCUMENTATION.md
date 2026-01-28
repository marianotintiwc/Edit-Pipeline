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

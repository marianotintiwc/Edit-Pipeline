# UGC Video Pipeline (Python)

## Big picture
- Two execution modes: local CLI pipeline in `ugc_pipeline.py` and RunPod serverless handler in `handler.py`.
- Core pipeline stages are in `ugc-pipeline/`: `clips.py` (load/trim/resize/concat), `audio.py` (music mix), `subtitles.py` + `transcription.py` (Whisper SRT), `postprocess.py` (FFmpeg effects + RIFE/FILM), `export.py` (H.264 MP4).
- Serverless flow: handler downloads inputs → generates `clips.json` + `style.json` → runs pipeline → uploads to S3. See `run_pipeline()` in `handler.py`.

## Critical workflows
- Local CLI: `ugc_pipeline.py` orchestrates 5 steps (style → clips → audio → subtitles → export) and expects assets under `assets/` and configs under `config/`.
- Serverless: use `handler.py` with RunPod; environment variables for S3 are required (see `README.md`).
- RunPod helper CLI: use `Helper Scripts/runpod_cli.py` for submit/status/poll and endpoint image updates (consolidated helper).
- Validation: `startup_check.py` validates FFmpeg, ImageMagick, Vulkan/RIFE, CUDA; `test_local.py` exercises validation and handler parsing.

## Project-specific conventions
- Input format supports both legacy `video_urls` and new ordered `clips` with `scene`/`broll` types; negative `end_time` trims “from end” (handled in `generate_clips_config()` in `handler.py`).
- Post-processing is applied per-scene before concatenation (AI scenes only) in `ugc-pipeline/clips.py`; b-roll skips postprocess.
- Subtitles: `subtitle_mode=auto` triggers Whisper; `manual` downloads SRT; `none` skips. ImageMagick (`magick`) must be available for MoviePy `TextClip` (`ugc-pipeline/subtitles.py`).
- Music: `music_url="random"` selects from `assets/audio/`; loop/volume come from `style.json` or request overrides.
- Endcard transparency: `endcard_alpha_fill.enabled` controls alpha-fill; set `use_blur_background=true` only when you want blurred fill from the previous clip.
- Audio pop mitigation: tiny boundary fades (~0.05s) run even with transitions; endcard overlap fades are applied automatically.

## Config files & overrides
- Style presets: `config/style.json` (serverless also generates style in `generate_style_config()`), deep-merged with `style_overrides` from API input.
- Clips config: `config/clips.sample.json` (local) or generated in work dir (serverless).

## Frame interpolation (RIFE)
- `input_fps` is configurable via payload (default: 24). Set this to match your source video FPS for correct interpolation to 60fps.
- Example: if source is 30fps, use `"input_fps": 30` in the payload; if source is 24fps (lipsync outputs), use `"input_fps": 24`.
- The target FPS is always 60 (hardcoded in style generation).

## Audio processing
- Music volume default is 0.03 (configurable via `style_overrides.audio.music_volume`).
- Peak limiter prevents music spikes above `music_peak` threshold (default: 0.3).

## External dependencies
- FFmpeg is required (imageio-ffmpeg fallback); ImageMagick required for subtitles; RIFE Vulkan binary for interpolation; Whisper uses CUDA if available.
- Docker/RunPod uses `Dockerfile` base `runpod/pytorch:2.4.0-py3.11-cuda12.4.1` and `startup_check.py` on boot.

## When editing
- Keep pipeline step order consistent with `ugc_pipeline.py` / `handler.py`.
- Use MoviePy clips from `ugc-pipeline/` modules; export settings (H.264, CRF 23) are centralized in `ugc-pipeline/export.py`.

  wait for your confirmation that new docker builds are finished before sending a job when testing or debugging serverless.
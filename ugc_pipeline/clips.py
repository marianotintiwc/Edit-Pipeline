import json
import os
import re
import time
import sys
import shutil
import subprocess
import tempfile
from moviepy.editor import VideoFileClip, concatenate_videoclips, vfx, CompositeVideoClip, ImageClip, afx
import numpy as np
from PIL import Image
from typing import List, Dict, Any

TARGET_RESOLUTION = (1080, 1920)
TARGET_FPS = 30  # Default, can be overridden by frame_interpolation config
TRANSITION_AUDIO_FADE = 0.05  # seconds


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_geo_from_project_name(project_name: str) -> str:
    """Extract GEO code (MLA, MLB, MLM) from project name."""
    if project_name.endswith("-MLB"):
        return "MLB"
    elif project_name.endswith("-MLA"):
        return "MLA"
    elif project_name.endswith("-MLM"):
        return "MLM"
    return None


def get_endcard_path(style_config: Dict[str, Any], geo: str) -> str:
    """
    Get the endcard video path for the given GEO.
    
    Supports:
    1. Direct URL (http/https) - downloaded to temp
    2. S3 download (if s3_bucket configured or S3_BUCKET env var set)
    3. Local folder fallback (for local development)
    
    Downloaded endcards are cached in /tmp/endcards/ (Docker) or temp dir (local).
    """
    if not style_config:
        return None
    
    endcard_config = style_config.get("endcard", {})
    if not endcard_config.get("enabled", False):
        return None
    
    # Option 1: Direct URL (highest priority)
    direct_url = endcard_config.get("url")
    if direct_url and direct_url.startswith(("http://", "https://")):
        import requests
        import hashlib
        
        # Cache directory for downloaded endcards
        cache_dir = "/tmp/endcards" if os.path.exists("/tmp") else tempfile.gettempdir()
        cache_dir = os.path.join(cache_dir, "endcards")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Use URL hash for cache filename to handle URL-encoded names
        url_hash = hashlib.md5(direct_url.encode()).hexdigest()[:12]
        ext = os.path.splitext(direct_url.split('?')[0])[-1] or ".mov"
        cached_path = os.path.join(cache_dir, f"endcard_{url_hash}{ext}")
        
        # Return cached file if exists
        if os.path.exists(cached_path):
            print(f"Using cached endcard: {cached_path}")
            return cached_path
        
        # Check if this is an S3 URL - use boto3 instead of HTTP
        if '.amazonaws.com/' in direct_url or 's3.' in direct_url:
            try:
                import boto3
                import re
                
                # Parse S3 URL: https://s3.region.amazonaws.com/bucket/key or https://bucket.s3.region.amazonaws.com/key
                s3_match = re.match(r'https://s3\.([^.]+)\.amazonaws\.com/([^/]+)/(.+)', direct_url)
                if not s3_match:
                    s3_match = re.match(r'https://([^.]+)\.s3\.([^.]+)\.amazonaws\.com/(.+)', direct_url)
                    if s3_match:
                        bucket = s3_match.group(1)
                        region = s3_match.group(2)
                        key = s3_match.group(3)
                    else:
                        raise ValueError(f"Could not parse S3 URL: {direct_url}")
                else:
                    region = s3_match.group(1)
                    bucket = s3_match.group(2)
                    key = s3_match.group(3)
                
                print(f"Downloading endcard from S3: s3://{bucket}/{key}")
                s3 = boto3.client(
                    's3',
                    region_name=region,
                    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
                )
                s3.download_file(bucket, key, cached_path)
                
                size_mb = os.path.getsize(cached_path) / (1024 * 1024)
                print(f"Endcard downloaded from S3: {os.path.basename(cached_path)} ({size_mb:.1f} MB)")
                return cached_path
                
            except Exception as e:
                print(f"Warning: Failed to download endcard from S3: {e}")
                # Fall through to HTTP method as backup
        
        # Download from URL (HTTP/HTTPS)
        try:
            print(f"Downloading endcard from URL: {direct_url[:80]}...")
            response = requests.get(direct_url, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(cached_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            size_mb = os.path.getsize(cached_path) / (1024 * 1024)
            print(f"Endcard downloaded: {os.path.basename(cached_path)} ({size_mb:.1f} MB)")
            return cached_path
            
        except Exception as e:
            print(f"Warning: Failed to download endcard from URL: {e}")
            # Fall through to other methods
    
    # Option 2: S3 bucket + geo-based filename
    files = endcard_config.get("files", {})
    filename = files.get(geo)
    if not filename:
        return None
    
    # Try S3 first (for Docker/RunPod)
    s3_bucket = endcard_config.get("s3_bucket") or os.environ.get("S3_BUCKET")
    s3_prefix = endcard_config.get("s3_prefix", "assets/endcards/")
    
    if s3_bucket:
        # Cache directory for downloaded endcards
        cache_dir = "/tmp/endcards" if os.path.exists("/tmp") else tempfile.gettempdir()
        cache_dir = os.path.join(cache_dir, "endcards")
        os.makedirs(cache_dir, exist_ok=True)
        
        cached_path = os.path.join(cache_dir, filename)
        
        # Return cached file if exists
        if os.path.exists(cached_path):
            print(f"Using cached endcard: {cached_path}")
            return cached_path
        
        # Download from S3
        try:
            # Import here to avoid circular dependency
            import boto3
            s3_key = f"{s3_prefix.rstrip('/')}/{filename}"
            
            print(f"Downloading endcard from S3: s3://{s3_bucket}/{s3_key}")
            s3 = boto3.client(
                's3',
                aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
                region_name=os.environ.get('AWS_REGION', 'us-east-1')
            )
            s3.download_file(s3_bucket, s3_key, cached_path)
            
            size_mb = os.path.getsize(cached_path) / (1024 * 1024)
            print(f"Endcard downloaded: {filename} ({size_mb:.1f} MB)")
            return cached_path
            
        except Exception as e:
            print(f"Warning: Failed to download endcard from S3: {e}")
            # Fall through to local folder check
    
    # Fallback to local folder (for local development)
    local_folder = endcard_config.get("local_folder") or endcard_config.get("folder", "")
    if local_folder:
        path = os.path.join(local_folder, filename)
        if os.path.exists(path):
            return path
    
    return None


def get_target_fps(style_config: Dict[str, Any] = None) -> int:
    """Get target FPS from config, respecting frame interpolation settings."""
    if style_config:
        pp_config = style_config.get("postprocess", {})
        interp_config = pp_config.get("frame_interpolation", {})
        if interp_config.get("enabled", False):
            return interp_config.get("target_fps", TARGET_FPS)
    return TARGET_FPS

def print_clip_status(message: str, indent: int = 0):
    """Print a formatted status message for clip processing."""
    prefix = "  " * indent
    print(f"{prefix}→ {message}")
    sys.stdout.flush()


def _apply_transition_audio_fades(audio_clip, clip_duration: float):
    """Apply tiny audio fades to prevent pops at clip boundaries."""
    if audio_clip is None or not clip_duration:
        return audio_clip
    fade = min(TRANSITION_AUDIO_FADE, max(0.0, clip_duration / 4.0))
    if fade <= 0:
        return audio_clip
    return audio_clip.fx(afx.audio_fadein, fade).fx(afx.audio_fadeout, fade)


def _apply_transition_crossfade(prev_clip, next_clip, duration: float):
    """Apply audio crossfade on overlapping transition duration."""
    if duration <= 0:
        return prev_clip, next_clip
    if prev_clip is not None and prev_clip.audio:
        prev_audio = prev_clip.audio.fx(afx.audio_fadeout, duration)
        prev_clip = prev_clip.set_audio(prev_audio)
    if next_clip is not None and next_clip.audio:
        next_audio = next_clip.audio.fx(afx.audio_fadein, duration)
        next_clip = next_clip.set_audio(next_audio)
    return prev_clip, next_clip


def _resolve_endcard_alpha_config(style_config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve endcard alpha-fill config with b-roll config as fallback."""
    if not style_config:
        return {}
    endcard_cfg = style_config.get("endcard_alpha_fill", {}) or {}
    broll_cfg = style_config.get("broll_alpha_fill", {}) or {}

    if not endcard_cfg and broll_cfg:
        endcard_cfg = {"enabled": False, **broll_cfg}

    if not endcard_cfg:
        endcard_cfg = {"enabled": False}

    endcard_cfg.setdefault("force_chroma_key", False)
    endcard_cfg.setdefault("use_blur_background", False)

    # Fill missing keys from broll config
    for key, val in broll_cfg.items():
        endcard_cfg.setdefault(key, val)

    return endcard_cfg


def _resolve_introcard_alpha_config(style_config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve introcard alpha-fill config with endcard config as fallback."""
    if not style_config:
        return {}
    introcard_cfg = style_config.get("introcard_alpha_fill", {}) or {}
    endcard_cfg = style_config.get("endcard_alpha_fill", {}) or {}

    if not introcard_cfg and endcard_cfg:
        introcard_cfg = {**endcard_cfg}

    if not introcard_cfg:
        introcard_cfg = {"enabled": True}

    introcard_cfg.setdefault("force_chroma_key", False)
    introcard_cfg.setdefault("use_blur_background", False)

    return introcard_cfg


def _get_ffmpeg_path() -> str:
    """Get FFmpeg executable path."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    raise RuntimeError("FFmpeg not found. Install imageio-ffmpeg or add ffmpeg to PATH.")


def _get_ffprobe_path() -> str | None:
    """Get FFprobe executable path if available."""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        for candidate in ("ffprobe", "ffprobe.exe"):
            probe_path = os.path.join(ffmpeg_dir, candidate)
            if os.path.exists(probe_path):
                return probe_path
    except Exception:
        pass

    return shutil.which("ffprobe")


def _loop_pingpong(clip: VideoFileClip, duration: float) -> VideoFileClip:
    """Loop a clip using a forward+reverse (ping-pong) pattern to avoid hard resets."""
    if duration <= 0:
        return clip
    try:
        sym = clip.fx(vfx.time_symmetrize)
    except Exception:
        sym = clip
    if sym.duration >= duration:
        return sym.subclip(0, duration)
    return sym.loop(duration=duration)


def _invert_mask(mask_clip: VideoFileClip) -> VideoFileClip:
    """Invert a MoviePy mask clip (0->1, 1->0)."""
    return mask_clip.fl_image(lambda frame: 1.0 - frame)


def _should_invert_mask(mask_clip: VideoFileClip, threshold: float = 0.75, samples: int = 3) -> bool:
    """Heuristic: invert if mask is mostly opaque or mostly transparent but contains mixed values."""
    try:
        duration = float(getattr(mask_clip, "duration", 0.0) or 0.0)
        times = [0.0] if duration <= 0 else np.linspace(0.0, max(duration - 0.001, 0.0), max(samples, 1))
        means = []
        mins = []
        maxs = []
        for t in times:
            frame = mask_clip.get_frame(t)
            mask = frame if frame.ndim == 2 else frame[:, :, 0]
            means.append(float(mask.mean()))
            mins.append(float(mask.min()))
            maxs.append(float(mask.max()))
        if not means:
            return False
        mean_val = float(np.mean(means))
        min_val = float(np.min(mins))
        max_val = float(np.max(maxs))
        mostly_opaque = mean_val >= threshold and min_val < 0.98
        mostly_transparent = mean_val <= (1.0 - threshold) and max_val > 0.02
        return mostly_opaque or mostly_transparent
    except Exception:
        return False


def _log_mask_stats(mask_clip: VideoFileClip | None, label: str, indent: int = 0, samples: int = 3) -> None:
    """Log basic mask stats (min/max/mean) for a few frames."""
    if mask_clip is None:
        print_clip_status(f"{label}: mask is None", indent)
        return
    try:
        duration = float(getattr(mask_clip, "duration", 0.0) or 0.0)
        if duration <= 0:
            times = [0.0]
        else:
            end_time = max(duration - 0.001, 0.0)
            times = np.linspace(0.0, end_time, max(samples, 1))
        stats = []
        for t in times:
            frame = mask_clip.get_frame(t)
            mask = frame if frame.ndim == 2 else frame[:, :, 0]
            stats.append((float(mask.min()), float(mask.mean()), float(mask.max())))
        stats_str = ", ".join([f"t{i}:min={m:.3f},mean={a:.3f},max={x:.3f}" for i, (m, a, x) in enumerate(stats)])
        print_clip_status(f"{label}: {stats_str}", indent)
    except Exception as e:
        print_clip_status(f"{label}: failed to read mask stats ({e})", indent)


def _pix_fmt_has_alpha(pix_fmt: str | None) -> bool:
    if not pix_fmt:
        return False
    pix_fmt = pix_fmt.lower()
    return bool(re.search(r"\b(rgba|argb|bgra|abgr|yuva\w*|ya\w*)\b", pix_fmt))


def _ffprobe_stream_info(video_path: str) -> Dict[str, Any] | None:
    """Get basic stream info using ffprobe (pix_fmt, codec_name, codec_tag_string)."""
    ffprobe = _get_ffprobe_path()
    if not ffprobe:
        return None

    cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=pix_fmt,codec_name,codec_tag_string",
        "-of", "json",
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout or "{}")
        streams = payload.get("streams") or []
        if not streams:
            return None
        stream = streams[0]
        return {
            "pix_fmt": stream.get("pix_fmt"),
            "codec_name": stream.get("codec_name"),
            "codec_tag_string": stream.get("codec_tag_string")
        }
    except Exception:
        return None


def _has_alpha_channel(
    video_path: str,
    use_ffprobe: bool = True,
    verbose: bool = False,
    indent: int = 0,
    label: str | None = None,
    require_non_opaque: bool = False,
    sample_count: int = 3
) -> bool:
    """Detect if a video has an alpha channel using ffprobe (preferred) or ffmpeg parsing."""
    label_prefix = f"{label} " if label else ""

    if _is_image_file(video_path):
        has_alpha = _image_has_alpha(video_path)
        if verbose:
            print_clip_status(
                f"Alpha detect ({label_prefix}image): has_alpha={has_alpha}",
                indent
            )
        return has_alpha

    if use_ffprobe:
        info = _ffprobe_stream_info(video_path)
        if info is not None:
            pix_fmt = info.get("pix_fmt")
            has_alpha = _pix_fmt_has_alpha(pix_fmt)
            if verbose:
                codec = info.get("codec_name")
                tag = info.get("codec_tag_string")
                print_clip_status(
                    f"Alpha detect ({label_prefix}ffprobe): pix_fmt={pix_fmt}, codec={codec}, tag={tag}, has_alpha={has_alpha}",
                    indent
                )
            if has_alpha and require_non_opaque:
                return _mask_has_non_opaque_alpha(
                    video_path,
                    sample_count=sample_count,
                    verbose=verbose,
                    indent=indent,
                    label=label
                )
            if not has_alpha and require_non_opaque:
                return _mask_has_non_opaque_alpha(
                    video_path,
                    sample_count=sample_count,
                    verbose=verbose,
                    indent=indent,
                    label=label
                )
            return has_alpha

    ffmpeg = _get_ffmpeg_path()
    try:
        result = subprocess.run(
            [ffmpeg, "-i", video_path],
            capture_output=True,
            text=True
        )
        stderr = (result.stderr or "").lower()
        has_alpha = bool(re.search(r"video:.*\b(rgba|argb|bgra|abgr|yuva\w*|ya\w*)\b", stderr))
        if verbose:
            print_clip_status(
                f"Alpha detect ({label_prefix}ffmpeg): has_alpha={has_alpha}",
                indent
            )
        if has_alpha and require_non_opaque:
            return _mask_has_non_opaque_alpha(
                video_path,
                sample_count=sample_count,
                verbose=verbose,
                indent=indent,
                label=label
            )
        if not has_alpha and require_non_opaque:
            return _mask_has_non_opaque_alpha(
                video_path,
                sample_count=sample_count,
                verbose=verbose,
                indent=indent,
                label=label
            )
        return has_alpha
    except Exception:
        if verbose:
            print_clip_status(
                f"Alpha detect ({label_prefix}ffmpeg): failed to inspect",
                indent
            )
        return False


def _is_image_file(path: str) -> bool:
    """Check if path is an image file (PNG/JPG/WebP/etc.)."""
    ext = os.path.splitext(path)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def _image_has_alpha(path: str) -> bool:
    """Detect if an image has any non-opaque alpha channel using PIL."""
    try:
        with Image.open(path) as img:
            if img.mode in {"RGBA", "LA"}:
                img_rgba = img.convert("RGBA")
                alpha = np.array(img_rgba)[:, :, 3]
                return bool((alpha < 255).any())
            if img.mode == "P" and "transparency" in img.info:
                img_rgba = img.convert("RGBA")
                alpha = np.array(img_rgba)[:, :, 3]
                return bool((alpha < 255).any())
    except Exception:
        return False
    return False


def _mask_has_non_opaque_alpha(
    video_path: str,
    sample_count: int = 3,
    verbose: bool = False,
    indent: int = 0,
    label: str | None = None
) -> bool:
    """Inspect a clip mask and return True if any sampled pixel is non-opaque."""
    label_prefix = f"{label} " if label else ""
    clip = None
    try:
        clip = VideoFileClip(video_path, has_mask=True)
        if clip.mask is None:
            if verbose:
                print_clip_status(
                    f"Alpha inspect ({label_prefix}mask): clip.mask is None",
                    indent
                )
            return False
        duration = float(getattr(clip, "duration", 0.0) or 0.0)
        if duration <= 0:
            times = [0.0]
        else:
            end_time = max(duration - 0.001, 0.0)
            times = np.linspace(0.0, end_time, max(sample_count, 1))
        for t in times:
            frame = clip.mask.get_frame(t)
            mask = frame if frame.ndim == 2 else frame[:, :, 0]
            if float(mask.min()) < 0.999:
                if verbose:
                    print_clip_status(
                        f"Alpha inspect ({label_prefix}mask): non-opaque detected",
                        indent
                    )
                return True
        if verbose:
            print_clip_status(
                f"Alpha inspect ({label_prefix}mask): all opaque",
                indent
            )
        return False
    except Exception:
        if verbose:
            print_clip_status(
                f"Alpha inspect ({label_prefix}mask): failed to inspect",
                indent
            )
        return False
    finally:
        try:
            if clip is not None:
                clip.close()
        except Exception:
            pass


def _load_image_clip(
    path: str,
    duration: float = None,
    invert_alpha: bool | None = None,
    auto_invert: bool = True,
    auto_invert_threshold: float = 0.3
) -> ImageClip:
    """Load an image as a MoviePy ImageClip, preserving alpha as a mask."""
    with Image.open(path) as img:
        img_rgba = img.convert("RGBA")
    frame = np.array(img_rgba)
    rgb = frame[:, :, :3]
    alpha = frame[:, :, 3] / 255.0

    if invert_alpha is None and auto_invert:
        # Heuristic: if mostly opaque with few transparent pixels, alpha may be inverted
        transparent_ratio = float((alpha < 0.05).mean())
        opaque_ratio = float((alpha > 0.95).mean())
        if transparent_ratio < auto_invert_threshold and opaque_ratio > (1.0 - auto_invert_threshold):
            invert_alpha = True

    if invert_alpha:
        alpha = 1.0 - alpha

    clip = ImageClip(rgb)
    if alpha is not None:
        mask = ImageClip(alpha, ismask=True)
        clip = clip.set_mask(mask)

    if duration is not None:
        clip = clip.set_duration(duration)

    return clip


def export_broll_with_alpha_debug(
    clip,
    output_folder: str,
    clip_name: str,
    sample_count: int = 5
):
    """Export sample frames from b-roll clip with alpha preserved as RGBA PNGs.
    
    Args:
        clip: MoviePy VideoFileClip with mask
        output_folder: Base folder for debug output (e.g., /app/exports/debug)
        clip_name: Name for this clip's subfolder
        sample_count: Number of sample frames to export (default 5)
    """
    # Create output subfolder
    clip_folder = os.path.join(output_folder, clip_name)
    os.makedirs(clip_folder, exist_ok=True)
    
    duration = clip.duration
    fps = getattr(clip, 'fps', 30) or 30
    
    # Log mask status
    if clip.mask is None:
        print_clip_status(f"⚠️ DEBUG: clip.mask is None - NO ALPHA LOADED!", 4)
        # Still export RGB frames for comparison
        mask_status = "NO_MASK"
    else:
        # Sample mask at frame 0
        try:
            mask_frame = clip.mask.get_frame(0)
            mask_min = float(mask_frame.min())
            mask_max = float(mask_frame.max())
            mask_avg = float(mask_frame.mean())
            print_clip_status(f"✅ DEBUG: Mask loaded - min={mask_min:.3f}, max={mask_max:.3f}, avg={mask_avg:.3f}", 4)
            mask_status = f"min{mask_min:.2f}_max{mask_max:.2f}_avg{mask_avg:.2f}"
        except Exception as e:
            print_clip_status(f"⚠️ DEBUG: Could not read mask: {e}", 4)
            mask_status = "MASK_ERROR"
    
    # Calculate sample times
    if sample_count >= int(duration * fps):
        # Export all frames if sample_count is large
        times = np.linspace(0, duration - 0.001, sample_count)
    else:
        # Evenly spaced samples
        times = np.linspace(0, duration - 0.001, sample_count)
    
    print_clip_status(f"DEBUG: Exporting {len(times)} sample frames to {clip_folder}", 4)
    
    for i, t in enumerate(times):
        try:
            # Get RGB frame
            rgb_frame = clip.get_frame(t)
            
            # Get alpha mask frame
            if clip.mask is not None:
                alpha_frame = clip.mask.get_frame(t)
                # Handle 2D vs 3D mask array
                if alpha_frame.ndim == 2:
                    alpha = (alpha_frame * 255).astype(np.uint8)
                else:
                    alpha = (alpha_frame[:, :, 0] * 255).astype(np.uint8)
            else:
                # No mask - create fully opaque alpha
                alpha = np.full(rgb_frame.shape[:2], 255, dtype=np.uint8)
            
            # Combine RGBA
            rgba = np.dstack([rgb_frame.astype(np.uint8), alpha])
            
            # Save as PNG with alpha
            img = Image.fromarray(rgba, 'RGBA')
            frame_path = os.path.join(clip_folder, f"frame_{i:03d}_t{t:.2f}s.png")
            img.save(frame_path)
            
        except Exception as e:
            print_clip_status(f"DEBUG: Failed to export frame {i} at t={t:.2f}s: {e}", 4)
    
    # Write info file
    info_path = os.path.join(clip_folder, "_debug_info.txt")
    with open(info_path, "w") as f:
        f.write(f"Clip: {clip_name}\n")
        f.write(f"Duration: {duration:.2f}s\n")
        f.write(f"FPS: {fps}\n")
        f.write(f"Size: {clip.w}x{clip.h}\n")
        f.write(f"Mask Status: {mask_status}\n")
        f.write(f"Sample Count: {len(times)}\n")
        f.write(f"Sample Times: {[f'{t:.2f}s' for t in times]}\n")
    
    print_clip_status(f"DEBUG: ✅ Exported to {clip_folder}", 4)


def _create_blurred_slow_background(
    source_path: str,
    duration: float,
    blur_sigma: float,
    slow_factor: float,
    temp_files: List[str],
    loop: bool = True
) -> str:
    """Create a blurred, slowed background clip using FFmpeg."""
    ffmpeg = _get_ffmpeg_path()
    slow_factor = max(slow_factor, 1.0)
    target_duration = max(float(duration or 0.0), 0.01)
    source_duration = 0.0
    try:
        with VideoFileClip(source_path) as src_clip:
            source_duration = float(getattr(src_clip, "duration", 0.0) or 0.0)
    except Exception:
        source_duration = 0.0

    if source_duration > 0:
        slow_factor = max(slow_factor, target_duration / source_duration)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(temp_fd)
    temp_files.append(temp_path)

    filter_str = f"setpts=PTS*{slow_factor},gblur=sigma={blur_sigma}"
    cmd = [ffmpeg, "-y"]
    cmd += [
        "-i", source_path,
        "-vf", filter_str,
        "-t", str(target_duration),
        "-an",
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        temp_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    return temp_path


def _create_chroma_key_alpha(
    source_path: str,
    similarity: float,
    blend: float,
    temp_files: List[str],
    hex_color: str = "0x000000",
    edge_feather: int = 0
) -> str:
    """Create a video with alpha from specific color using FFmpeg colorkey.
    
    Args:
        edge_feather: Blur radius for alpha channel edges (0 = no feathering, 1-5 recommended)
    """
    ffmpeg = _get_ffmpeg_path()
    temp_fd, temp_path = tempfile.mkstemp(suffix=".mov")
    os.close(temp_fd)
    temp_files.append(temp_path)

    # Ensure hex format is correct for ffmpeg (0xRRGGBB)
    if hex_color.startswith("#"):
        hex_color = "0x" + hex_color[1:]
    
    print_clip_status(f"Chroma key color: {hex_color}, similarity: {similarity}, blend: {blend}, edge_feather: {edge_feather}", 4)

    # Build filter: colorkey -> format rgba -> optional alpha edge blur
    filter_str = f"colorkey={hex_color}:{similarity}:{blend},format=rgba"
    
    # Add edge feathering by blurring only the alpha channel
    if edge_feather > 0:
        # Split RGBA, blur alpha, merge back
        # This softens the jagged edges of the mask
        filter_str = (
            f"colorkey={hex_color}:{similarity}:{blend},format=rgba,"
            f"split=2[rgb][a];[a]alphaextract,boxblur={edge_feather}:{edge_feather}[ablur];"
            f"[rgb][ablur]alphamerge"
        )
    
    cmd = [
        ffmpeg, "-y", "-i", source_path,
        "-vf", filter_str,
        "-an",
        "-c:v", "qtrle",
        temp_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    return temp_path


def _get_alpha_stats(video_path: str) -> Dict[str, float]:
    """Get alpha plane signal stats from a video with alpha."""
    ffmpeg = _get_ffmpeg_path()
    cmd = [
        ffmpeg, "-y", "-i", video_path,
        "-vf", "alphaextract,signalstats,metadata=print",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr or ""

    stats = {}
    for line in stderr.splitlines():
        if "lavfi.signalstats." in line:
            try:
                key_val = line.split("lavfi.signalstats.", 1)[1]
                key, val = key_val.split("=", 1)
                stats[key.strip()] = float(val.strip())
            except Exception:
                continue
    return stats


def _auto_tune_chroma_key(
    source_path: str,
    blend: float,
    temp_files: List[str],
    min_sim: float,
    max_sim: float,
    step: float,
    verbose: bool = False,
    indent: int = 0
) -> float:
    """Auto-tune chroma key similarity to get both transparent and opaque alpha."""
    sim = min_sim
    best_sim = min_sim
    best_score = -1.0

    while sim <= max_sim + 1e-6:
        alpha_path = _create_chroma_key_alpha(source_path, sim, blend, temp_files)
        stats = _get_alpha_stats(alpha_path)
        y_min = stats.get("YMIN")
        y_max = stats.get("YMAX")
        y_avg = stats.get("YAVG")

        score = -1.0
        if y_min is not None and y_max is not None and y_avg is not None:
            # Prefer a wide alpha range (some transparent + some opaque)
            score = (y_max - y_min) - abs(127.5 - y_avg)
            if verbose:
                print_clip_status(
                    f"Auto-tune alpha: sim={sim:.3f} y_min={y_min:.1f} y_max={y_max:.1f} y_avg={y_avg:.1f} score={score:.1f}",
                    indent
                )
        if score > best_score:
            best_score = score
            best_sim = sim

        # Good enough if we have both transparent and opaque areas
        if y_min is not None and y_max is not None and y_min <= 5 and y_max >= 200:
            if verbose:
                print_clip_status(
                    f"Auto-tune alpha: early stop at sim={sim:.3f} (y_min={y_min:.1f}, y_max={y_max:.1f})",
                    indent
                )
            return sim

        sim += step

    if verbose:
        print_clip_status(
            f"Auto-tune alpha: best sim={best_sim:.3f} (score={best_score:.1f})",
            indent
        )
    return best_sim


def _resize_to_target(clip: VideoFileClip) -> VideoFileClip:
    """Resize/crop clip to 9:16 (1080x1920)."""
    target_ratio = TARGET_RESOLUTION[0] / TARGET_RESOLUTION[1]
    clip_ratio = clip.w / clip.h

    if clip_ratio > target_ratio:
        clip = clip.resize(height=TARGET_RESOLUTION[1])
        clip = clip.crop(x1=clip.w/2 - TARGET_RESOLUTION[0]/2,
                         x2=clip.w/2 + TARGET_RESOLUTION[0]/2)
    else:
        clip = clip.resize(width=TARGET_RESOLUTION[0])
        clip = clip.crop(y1=clip.h/2 - TARGET_RESOLUTION[1]/2,
                         y2=clip.h/2 + TARGET_RESOLUTION[1]/2)

    return clip.resize(TARGET_RESOLUTION)

def load_clips_config(path: str) -> List[Dict[str, Any]]:
    """Loads the clips configuration from a JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Clips config file not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    return config.get("clips", [])

def get_video_files_from_dir(directory: str) -> List[Dict[str, Any]]:
    """
    Scans directory for video files, sorts them naturally by number in filename.
    Returns a list of clip dicts.
    """
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    files = []
    
    if not os.path.exists(directory):
        return []
    
    print(f"Scanning directory {directory} for videos...")
    
    for f in os.listdir(directory):
        ext = os.path.splitext(f)[1].lower()
        if ext in video_extensions:
            files.append(f)
            
    # Natural sort key function
    def natural_keys(text):
        # Split text into list of strings and numbers
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]
        
    files.sort(key=natural_keys)
    
    print(f"Found {len(files)} videos: {files}")
    
    return [{"path": os.path.join(directory, f), "start": None, "end": None} for f in files]

def process_clips(source: str, style_config: Dict[str, Any] = None) -> VideoFileClip:
    """
    Reads clips from JSON config OR directory.
    Loads videos, trims, resizes/crop to 9:16, applies transitions, and concatenates.
    """
    start_time = time.time()
    if os.path.isdir(source):
        clips_data = get_video_files_from_dir(source)
    else:
        clips_data = load_clips_config(source)
        
    video_clips = []
    temp_files = []

    global_broll_alpha = style_config.get("broll_alpha_fill", {}) if style_config else {}
    alpha_detection = style_config.get("alpha_detection", {}) if style_config else {}
    alpha_verbose = bool(alpha_detection.get("verbose", False))
    alpha_use_ffprobe = alpha_detection.get("use_ffprobe", True)
    alpha_require_non_opaque = alpha_detection.get("require_non_opaque", True)
    transitions_enabled = bool(style_config and style_config.get("transitions", {}).get("enabled", False))
    transitions_enabled = bool(style_config and style_config.get("transitions", {}).get("enabled", False))
    alpha_require_non_opaque = alpha_detection.get("require_non_opaque", True)

    previous_fill_source = None

    target_fps = get_target_fps(style_config)
    print(f"Processing {len(clips_data)} clips... (target_fps={target_fps})")
    try:
        clip_types = [(c.get("type") or "scene") for c in clips_data]
        print(f"Clip types: {clip_types}")
    except Exception:
        pass

    # Separate introcard/endcard from regular clips
    introcard_clip_info = None
    endcard_clip_info = None
    regular_clips = []
    for clip_info in clips_data:
        clip_type = (clip_info.get("type") or "").lower()
        if clip_type == "introcard":
            introcard_clip_info = clip_info
        elif clip_type == "endcard":
            endcard_clip_info = clip_info
        else:
            regular_clips.append(clip_info)
    if endcard_clip_info is None:
        print("⚠️  No endcard clip detected in clips.json")

    try:
        for i, clip_info in enumerate(regular_clips):
            path = clip_info.get("path")
            if not os.path.exists(path):
                print(f"Warning: Clip not found at {path}. Skipping.")
                continue

            print(f"  Loading clip {i+1}: {path}")
            clip_type = (clip_info.get("type") or "").lower()
            is_broll = clip_type == "broll"
            is_image = _is_image_file(path)

            clip_alpha_override = clip_info.get("alpha_fill") or {}
            alpha_fill_config = deep_merge(global_broll_alpha, clip_alpha_override) if is_broll else {}
            alpha_fill_enabled = alpha_fill_config.get("enabled", False)
            alpha_fill_blur = alpha_fill_config.get("blur_sigma", 8)
            alpha_fill_slow = alpha_fill_config.get("slow_factor", 1.5)
            alpha_force_key = alpha_fill_config.get("force_chroma_key", False)
            alpha_key_similarity = alpha_fill_config.get("chroma_key_similarity", 0.08)
            alpha_key_blend = alpha_fill_config.get("chroma_key_blend", 0.0)
            alpha_key_color = alpha_fill_config.get("chroma_key_color", "0x000000")
            alpha_edge_feather = alpha_fill_config.get("edge_feather", 0)
            alpha_auto_tune = alpha_fill_config.get("auto_tune", False)
            alpha_tune_min = alpha_fill_config.get("auto_tune_min", 0.05)
            alpha_tune_max = alpha_fill_config.get("auto_tune_max", 0.30)
            alpha_tune_step = alpha_fill_config.get("auto_tune_step", 0.03)
            image_alpha_invert = alpha_fill_config.get("invert_alpha", None)
            image_alpha_auto_invert = alpha_fill_config.get("auto_invert_alpha", True)
            image_alpha_auto_threshold = alpha_fill_config.get("auto_invert_alpha_threshold", 0.3)

            original_audio = None
            broll_has_alpha = False
            if is_broll and alpha_fill_enabled:
                broll_has_alpha = _has_alpha_channel(
                    path,
                    use_ffprobe=alpha_use_ffprobe,
                    verbose=alpha_verbose,
                    indent=3,
                    label="broll",
                    require_non_opaque=alpha_require_non_opaque
                )
                if alpha_verbose:
                    if broll_has_alpha:
                        print_clip_status("Alpha detected (b-roll) → will fill with blurred background", 3)
                    elif alpha_force_key:
                        print_clip_status("No alpha detected → forcing chroma key", 3)
                    else:
                        print_clip_status("No alpha detected and force_chroma_key=false → alpha fill skipped", 3)

            image_duration = None
            if is_image:
                duration = clip_info.get("duration")
                start = clip_info.get("start")
                end = clip_info.get("end")
                if duration is not None:
                    image_duration = float(duration)
                elif start is not None or end is not None:
                    start_val = float(start or 0.0)
                    end_val = float(end or 0.0)
                    if end is not None and end_val > start_val:
                        image_duration = end_val - start_val
                if image_duration is None:
                    image_duration = 2.0

            if is_image:
                invert_alpha = clip_info.get("invert_alpha", image_alpha_invert)
                clip = _load_image_clip(
                    path,
                    duration=image_duration,
                    invert_alpha=invert_alpha,
                    auto_invert=image_alpha_auto_invert,
                    auto_invert_threshold=image_alpha_auto_threshold
                )
                original_audio = None
                if is_broll and alpha_fill_enabled:
                    broll_has_alpha = _has_alpha_channel(
                        path,
                        use_ffprobe=alpha_use_ffprobe,
                        verbose=alpha_verbose,
                        indent=3,
                        label="broll image",
                        require_non_opaque=alpha_require_non_opaque
                    )
            elif is_broll and alpha_force_key:
                audio_source = VideoFileClip(path)
                original_audio = audio_source.audio
                similarity = alpha_key_similarity
                if alpha_auto_tune:
                    similarity = _auto_tune_chroma_key(
                        path,
                        alpha_key_blend,
                        temp_files,
                        alpha_tune_min,
                        alpha_tune_max,
                        alpha_tune_step,
                        verbose=alpha_verbose,
                        indent=4
                    )
                alpha_path = _create_chroma_key_alpha(
                    path,
                    similarity,
                    alpha_key_blend,
                    temp_files,
                    hex_color=alpha_key_color,
                    edge_feather=alpha_edge_feather
                )
                clip = VideoFileClip(alpha_path, has_mask=True)
            elif is_broll and broll_has_alpha:
                clip = VideoFileClip(path, has_mask=True)
                original_audio = clip.audio
            else:
                clip = VideoFileClip(path)
                original_audio = clip.audio

            # DEBUG: Export b-roll with alpha for inspection
            if alpha_verbose and is_broll and (broll_has_alpha or alpha_force_key):
                debug_folder = "/app/exports/debug"
                os.makedirs(debug_folder, exist_ok=True)
                clip_basename = os.path.splitext(os.path.basename(path))[0]
                print_clip_status(f"DEBUG: Exporting alpha frames for {clip_basename}...", 3)
                export_broll_with_alpha_debug(
                    clip,
                    debug_folder,
                    clip_basename,
                    sample_count=5
                )

            # 1. Trim if requested (skip for static images)
            start = clip_info.get("start")
            end = clip_info.get("end")
            if (start is not None or end is not None) and not is_image:
                clip = clip.subclip(start, end)

            # 2. Resize/Crop to 9:16 (1080x1920)
            if is_broll and (broll_has_alpha or alpha_force_key) and alpha_fill_enabled:
                if previous_fill_source:
                    bg_path = _create_blurred_slow_background(
                        previous_fill_source,
                        clip.duration,
                        alpha_fill_blur,
                        alpha_fill_slow,
                        temp_files
                    )
                    bg_clip = VideoFileClip(bg_path).without_audio()
                    if bg_clip.duration < clip.duration:
                        bg_clip = bg_clip.loop(duration=clip.duration)
                    bg_clip = _resize_to_target(bg_clip)
                    clip = _resize_to_target(clip)
                    clip = CompositeVideoClip(
                        [bg_clip, clip.set_position("center")],
                        size=TARGET_RESOLUTION
                    ).set_duration(clip.duration)
                    clip = clip.set_audio(original_audio)
                else:
                    if alpha_verbose:
                        print_clip_status("Alpha fill enabled but no previous clip available; using normal resize", 3)
                    clip = _resize_to_target(clip)
            else:
                clip = _resize_to_target(clip)

            # Apply tiny audio fades to prevent pops at clip boundaries
            if clip.audio:
                clip = clip.set_audio(_apply_transition_audio_fades(clip.audio, clip.duration))

            video_clips.append(clip)
            previous_fill_source = path

        if not video_clips:
            raise ValueError("No valid clips found to process.")

        # Get introcard if enabled
        introcard_clip = None
        introcard_fill_source = regular_clips[0].get("path") if regular_clips else None

        if introcard_clip_info:
            introcard_path = introcard_clip_info.get("path")
            if introcard_path and os.path.exists(introcard_path):
                print(f"\n  🎬 Loading introcard from clips.json...")
                try:
                    introcard_alpha_config = _resolve_introcard_alpha_config(style_config) if style_config else {}
                    introcard_force_key = introcard_alpha_config.get("force_chroma_key", False)
                    introcard_has_alpha = _has_alpha_channel(
                        introcard_path,
                        use_ffprobe=alpha_use_ffprobe,
                        verbose=alpha_verbose,
                        indent=3,
                        label="introcard",
                        require_non_opaque=alpha_require_non_opaque
                    )
                    print_clip_status(f"Introcard alpha detected: {introcard_has_alpha}", 3)

                    if introcard_force_key:
                        similarity = introcard_alpha_config.get("chroma_key_similarity", 0.08)
                        blend = introcard_alpha_config.get("chroma_key_blend", 0.0)
                        edge_feather = introcard_alpha_config.get("edge_feather", 0)
                        hex_color = introcard_alpha_config.get("chroma_key_color", "0x000000")
                        print_clip_status(
                            f"Introcard alpha-fill config: color={hex_color}, sim={similarity}, blend={blend}, blur={introcard_alpha_config.get('blur_sigma', 8)}, slow={introcard_alpha_config.get('slow_factor', 1.5)}",
                            3
                        )
                        auto_tune = introcard_alpha_config.get("auto_tune", False)
                        if auto_tune:
                            similarity = _auto_tune_chroma_key(
                                introcard_path,
                                blend,
                                temp_files,
                                introcard_alpha_config.get("auto_tune_min", 0.05),
                                introcard_alpha_config.get("auto_tune_max", 0.30),
                                introcard_alpha_config.get("auto_tune_step", 0.03)
                            )
                        alpha_path = _create_chroma_key_alpha(
                            introcard_path,
                            similarity,
                            blend,
                            temp_files,
                            hex_color=hex_color,
                            edge_feather=edge_feather
                        )
                        introcard_raw = VideoFileClip(alpha_path, has_mask=True)
                        introcard_has_alpha = True
                    else:
                        introcard_raw = VideoFileClip(introcard_path, has_mask=True)

                    introcard_auto_invert = introcard_alpha_config.get("auto_invert_alpha", True)
                    introcard_invert_threshold = introcard_alpha_config.get("auto_invert_alpha_threshold", 0.75)
                    if introcard_auto_invert and introcard_raw.mask is not None:
                        if _should_invert_mask(introcard_raw.mask, threshold=introcard_invert_threshold):
                            introcard_raw = introcard_raw.set_mask(_invert_mask(introcard_raw.mask))

                    introcard_clip = introcard_raw.resize(TARGET_RESOLUTION)
                    if introcard_raw.mask is not None and introcard_clip.mask is None:
                        introcard_clip = introcard_clip.set_mask(introcard_raw.mask.resize(introcard_clip.size))

                    if introcard_alpha_config.get("enabled", False) and introcard_alpha_config.get("use_blur_background", False) and introcard_fill_source:
                        blur_sigma = introcard_alpha_config.get("blur_sigma", 8)
                        slow_factor = introcard_alpha_config.get("slow_factor", 1.5)
                        bg_path = _create_blurred_slow_background(
                            introcard_fill_source,
                            introcard_clip.duration,
                            blur_sigma,
                            slow_factor,
                            temp_files
                        )
                        bg_clip = VideoFileClip(bg_path).without_audio()
                        if bg_clip.duration < introcard_clip.duration:
                            bg_clip = bg_clip.loop(duration=introcard_clip.duration)
                        bg_clip = _resize_to_target(bg_clip)
                        introcard_clip = _resize_to_target(introcard_clip)
                        introcard_clip = CompositeVideoClip(
                            [bg_clip, introcard_clip.set_position("center")],
                            size=TARGET_RESOLUTION
                        ).set_duration(introcard_clip.duration).set_audio(introcard_clip.audio)
                        print("     Introcard alpha-fill: enabled (b-roll style)")
                    elif introcard_alpha_config.get("enabled", False) and not introcard_alpha_config.get("use_blur_background", False):
                        print_clip_status("Introcard alpha-fill background disabled; preserving transparency", 3)

                    print(f"     Introcard: {os.path.basename(introcard_path)} ({introcard_clip.duration:.2f}s)")
                except Exception as e:
                    print(f"     ⚠️ Failed to load introcard: {e}")
                    introcard_clip = None

        # Get endcard if enabled
        endcard_clip = None
        endcard_overlap = 0
        
        # First, try to load endcard from clips.json
        if endcard_clip_info:
            endcard_path = endcard_clip_info.get("path")
            if endcard_path and os.path.exists(endcard_path):
                print(f"\n  🎬 Loading endcard from clips.json...")
                if style_config:
                    endcard_config = style_config.get("endcard", {})
                    endcard_overlap = endcard_config.get("overlap_seconds", 0.5)
                clip_overlap = endcard_clip_info.get("overlap_seconds")
                if clip_overlap is not None:
                    endcard_overlap = float(clip_overlap)
                try:
                    base_endcard_alpha = _resolve_endcard_alpha_config(style_config) if style_config else {}
                    endcard_alpha_override = endcard_clip_info.get("alpha_fill") or {}
                    endcard_alpha_config = deep_merge(base_endcard_alpha, endcard_alpha_override)
                    endcard_force_key = endcard_alpha_config.get("force_chroma_key", False)
                    endcard_has_alpha = _has_alpha_channel(
                        endcard_path,
                        use_ffprobe=alpha_use_ffprobe,
                        verbose=alpha_verbose,
                        indent=3,
                        label="endcard",
                        require_non_opaque=alpha_require_non_opaque
                    )
                    print_clip_status(f"Endcard alpha detected: {endcard_has_alpha}", 3)
                    if alpha_verbose:
                        has_non_opaque = _mask_has_non_opaque_alpha(
                            endcard_path,
                            sample_count=3,
                            verbose=alpha_verbose,
                            indent=4,
                            label="endcard"
                        )
                        print_clip_status(f"Endcard non-opaque alpha present: {has_non_opaque}", 3)

                    if endcard_force_key:
                        similarity = endcard_alpha_config.get("chroma_key_similarity", 0.08)
                        blend = endcard_alpha_config.get("chroma_key_blend", 0.0)
                        edge_feather = endcard_alpha_config.get("edge_feather", 0)
                        hex_color = endcard_alpha_config.get("chroma_key_color", "0x000000")
                        print_clip_status(
                            f"Endcard alpha-fill config: color={hex_color}, sim={similarity}, blend={blend}, blur={endcard_alpha_config.get('blur_sigma', 8)}, slow={endcard_alpha_config.get('slow_factor', 1.5)}",
                            3
                        )
                        auto_tune = endcard_alpha_config.get("auto_tune", False)
                        if auto_tune:
                            similarity = _auto_tune_chroma_key(
                                endcard_path,
                                blend,
                                temp_files,
                                endcard_alpha_config.get("auto_tune_min", 0.05),
                                endcard_alpha_config.get("auto_tune_max", 0.30),
                                endcard_alpha_config.get("auto_tune_step", 0.03)
                            )
                        alpha_path = _create_chroma_key_alpha(
                            endcard_path,
                            similarity,
                            blend,
                            temp_files,
                            hex_color=hex_color,
                            edge_feather=edge_feather
                        )
                        endcard_raw = VideoFileClip(alpha_path, has_mask=True)
                        endcard_has_alpha = True
                    else:
                        endcard_raw = VideoFileClip(endcard_path, has_mask=True)

                    if alpha_verbose:
                        _log_mask_stats(endcard_raw.mask, "Endcard mask (pre-invert)", indent=4)

                    # Auto-invert endcard alpha if it appears inverted
                    endcard_auto_invert = endcard_alpha_config.get("auto_invert_alpha", True)
                    endcard_invert_threshold = endcard_alpha_config.get("auto_invert_alpha_threshold", 0.75)
                    if endcard_auto_invert and endcard_raw.mask is not None:
                        if _should_invert_mask(endcard_raw.mask, threshold=endcard_invert_threshold):
                            endcard_raw = endcard_raw.set_mask(_invert_mask(endcard_raw.mask))

                    if alpha_verbose:
                        _log_mask_stats(endcard_raw.mask, "Endcard mask (post-invert)", indent=4)

                    # Auto-invert endcard alpha if it appears inverted
                    endcard_auto_invert = endcard_alpha_config.get("auto_invert_alpha", True)
                    endcard_invert_threshold = endcard_alpha_config.get("auto_invert_alpha_threshold", 0.75)
                    if endcard_auto_invert and endcard_raw.mask is not None:
                        if _should_invert_mask(endcard_raw.mask, threshold=endcard_invert_threshold):
                            endcard_raw = endcard_raw.set_mask(_invert_mask(endcard_raw.mask))

                    # Resize endcard to target resolution
                    endcard_clip = endcard_raw.resize(TARGET_RESOLUTION)
                    if endcard_raw.mask is not None and endcard_clip.mask is None:
                        endcard_clip = endcard_clip.set_mask(endcard_raw.mask.resize(endcard_clip.size))

                    # DEBUG: Export endcard alpha frames for inspection
                    if alpha_verbose and endcard_has_alpha:
                        debug_folder = "/app/exports/debug"
                        os.makedirs(debug_folder, exist_ok=True)
                        endcard_basename = os.path.splitext(os.path.basename(endcard_path))[0]
                        print_clip_status(f"DEBUG: Exporting alpha frames for {endcard_basename}...", 3)
                        export_broll_with_alpha_debug(
                            endcard_clip,
                            debug_folder,
                            endcard_basename,
                            sample_count=5
                        )

                    # Apply alpha-fill background only when explicitly enabled
                    if endcard_alpha_config.get("enabled", False) and endcard_alpha_config.get("use_blur_background", False) and previous_fill_source:
                        blur_sigma = endcard_alpha_config.get("blur_sigma", 8)
                        slow_factor = endcard_alpha_config.get("slow_factor", 1.5)
                        bg_path = _create_blurred_slow_background(
                            previous_fill_source,
                            endcard_clip.duration,
                            blur_sigma,
                            slow_factor,
                            temp_files
                        )
                        bg_clip = VideoFileClip(bg_path).without_audio()
                        if bg_clip.duration < endcard_clip.duration:
                            bg_clip = bg_clip.loop(duration=endcard_clip.duration)
                        bg_clip = _resize_to_target(bg_clip)
                        endcard_clip = _resize_to_target(endcard_clip)
                        endcard_clip = CompositeVideoClip(
                            [bg_clip, endcard_clip.set_position("center")],
                            size=TARGET_RESOLUTION
                        ).set_duration(endcard_clip.duration).set_audio(endcard_clip.audio)
                        print("     Endcard alpha-fill: enabled (b-roll style)")
                    elif endcard_alpha_config.get("enabled", False) and not endcard_alpha_config.get("use_blur_background", False):
                        print_clip_status("Endcard alpha-fill background disabled; preserving transparency", 3)
                    print(f"     Endcard: {os.path.basename(endcard_path)} ({endcard_clip.duration:.2f}s)")
                    print(f"     Overlap: {endcard_overlap}s with last clip")
                except Exception as e:
                    print(f"     ⚠️ Failed to load endcard: {e}")
                    endcard_clip = None
        
        # Fallback: try to load endcard from style config (URL-based)
        if not endcard_clip and style_config:
            endcard_config = style_config.get("endcard", {})
            if endcard_config.get("enabled", False):
                endcard_path = get_endcard_path(style_config, None)  # geo=None uses URL from style
                if endcard_path:
                    print(f"\n  🎬 Loading endcard from style config...")
                    endcard_overlap = endcard_config.get("overlap_seconds", 0.5)
                    try:
                        endcard_alpha_config = _resolve_endcard_alpha_config(style_config)
                        endcard_force_key = endcard_alpha_config.get("force_chroma_key", False)
                        endcard_has_alpha = _has_alpha_channel(
                            endcard_path,
                            use_ffprobe=alpha_use_ffprobe,
                            verbose=alpha_verbose,
                            indent=3,
                            label="endcard",
                            require_non_opaque=alpha_require_non_opaque
                        )
                        print_clip_status(f"Endcard alpha detected: {endcard_has_alpha}", 3)
                        if alpha_verbose:
                            has_non_opaque = _mask_has_non_opaque_alpha(
                                endcard_path,
                                sample_count=3,
                                verbose=alpha_verbose,
                                indent=4,
                                label="endcard"
                            )
                            print_clip_status(f"Endcard non-opaque alpha present: {has_non_opaque}", 3)
                        print_clip_status(f"Endcard alpha detected: {endcard_has_alpha}", 3)
                        if alpha_verbose:
                            has_non_opaque = _mask_has_non_opaque_alpha(
                                endcard_path,
                                sample_count=3,
                                verbose=alpha_verbose,
                                indent=4,
                                label="endcard"
                            )
                            print_clip_status(f"Endcard non-opaque alpha present: {has_non_opaque}", 3)

                        if endcard_force_key:
                            similarity = endcard_alpha_config.get("chroma_key_similarity", 0.08)
                            blend = endcard_alpha_config.get("chroma_key_blend", 0.0)
                            edge_feather = endcard_alpha_config.get("edge_feather", 0)
                            hex_color = endcard_alpha_config.get("chroma_key_color", "0x000000")
                            print_clip_status(
                                f"Endcard alpha-fill config: color={hex_color}, sim={similarity}, blend={blend}, blur={endcard_alpha_config.get('blur_sigma', 8)}, slow={endcard_alpha_config.get('slow_factor', 1.5)}",
                                3
                            )
                            auto_tune = endcard_alpha_config.get("auto_tune", False)
                            if auto_tune:
                                similarity = _auto_tune_chroma_key(
                                    endcard_path,
                                    blend,
                                    temp_files,
                                    endcard_alpha_config.get("auto_tune_min", 0.05),
                                    endcard_alpha_config.get("auto_tune_max", 0.30),
                                    endcard_alpha_config.get("auto_tune_step", 0.03),
                                    verbose=alpha_verbose,
                                    indent=4
                                )
                            alpha_path = _create_chroma_key_alpha(
                                endcard_path,
                                similarity,
                                blend,
                                temp_files,
                                hex_color=hex_color,
                                edge_feather=edge_feather
                            )
                            endcard_raw = VideoFileClip(alpha_path, has_mask=True)
                            endcard_has_alpha = True
                        else:
                            endcard_raw = VideoFileClip(endcard_path, has_mask=True)

                        if alpha_verbose:
                            _log_mask_stats(endcard_raw.mask, "Endcard mask (pre-invert)", indent=4)

                        if alpha_verbose:
                            _log_mask_stats(endcard_raw.mask, "Endcard mask (pre-invert)", indent=4)

                        # Resize endcard to target resolution
                        endcard_clip = endcard_raw.resize(TARGET_RESOLUTION)
                        if endcard_raw.mask is not None and endcard_clip.mask is None:
                            endcard_clip = endcard_clip.set_mask(endcard_raw.mask.resize(endcard_clip.size))

                        if alpha_verbose:
                            _log_mask_stats(endcard_raw.mask, "Endcard mask (post-invert)", indent=4)

                        if alpha_verbose:
                            _log_mask_stats(endcard_raw.mask, "Endcard mask (post-invert)", indent=4)

                        # DEBUG: Export endcard alpha frames for inspection
                        if alpha_verbose and endcard_has_alpha:
                            debug_folder = "/app/exports/debug"
                            os.makedirs(debug_folder, exist_ok=True)
                            endcard_basename = os.path.splitext(os.path.basename(endcard_path))[0]
                            print_clip_status(f"DEBUG: Exporting alpha frames for {endcard_basename}...", 3)
                            export_broll_with_alpha_debug(
                                endcard_clip,
                                debug_folder,
                                endcard_basename,
                                sample_count=5
                            )

                        # DEBUG: Export endcard alpha frames for inspection
                        if alpha_verbose and endcard_has_alpha:
                            debug_folder = "/app/exports/debug"
                            os.makedirs(debug_folder, exist_ok=True)
                            endcard_basename = os.path.splitext(os.path.basename(endcard_path))[0]
                            print_clip_status(f"DEBUG: Exporting alpha frames for {endcard_basename}...", 3)
                            export_broll_with_alpha_debug(
                                endcard_clip,
                                debug_folder,
                                endcard_basename,
                                sample_count=5
                            )
                        if endcard_alpha_config.get("enabled", False) and endcard_alpha_config.get("use_blur_background", False) and previous_fill_source:
                            blur_sigma = endcard_alpha_config.get("blur_sigma", 8)
                            slow_factor = endcard_alpha_config.get("slow_factor", 1.5)
                            bg_path = _create_blurred_slow_background(
                                previous_fill_source,
                                endcard_clip.duration,
                                blur_sigma,
                                slow_factor,
                                temp_files
                            )
                            bg_clip = VideoFileClip(bg_path).without_audio()
                            if bg_clip.duration < endcard_clip.duration:
                                bg_clip = bg_clip.loop(duration=endcard_clip.duration)
                            bg_clip = _resize_to_target(bg_clip)
                            endcard_clip = _resize_to_target(endcard_clip)
                            endcard_clip = CompositeVideoClip(
                                [bg_clip, endcard_clip.set_position("center")],
                                size=TARGET_RESOLUTION
                            ).set_duration(endcard_clip.duration).set_audio(endcard_clip.audio)
                            print("     Endcard alpha-fill: enabled (b-roll style)")
                        elif endcard_alpha_config.get("enabled", False) and not endcard_alpha_config.get("use_blur_background", False):
                            print_clip_status("Endcard alpha-fill background disabled; preserving transparency", 3)
                        elif alpha_verbose and endcard_alpha_config.get("enabled", False):
                            if not endcard_has_alpha:
                                print_clip_status("Endcard alpha-fill enabled but no alpha detected; skipping fill", 3)
                            elif not previous_fill_source:
                                print_clip_status("Endcard alpha-fill enabled but no previous clip available; skipping fill", 3)
                        print(f"     Endcard: {os.path.basename(endcard_path)} ({endcard_clip.duration:.2f}s)")
                        print(f"     Overlap: {endcard_overlap}s with last clip")
                    except Exception as e:
                        print(f"     ⚠️ Failed to load endcard: {e}")
                        endcard_clip = None
        
        # Apply transitions if enabled
        if style_config and style_config.get("transitions", {}).get("enabled", False):
            transition_duration = style_config.get("transitions", {}).get("duration", 0.5)
            print(f"Applying slide transitions (duration: {transition_duration}s)...")
            
            final_clips = []
            current_time = 0
            
            for i, clip in enumerate(video_clips):
                if i == 0:
                    final_clips.append(clip.set_start(current_time))
                    current_time += clip.duration
                else:
                    current_time -= transition_duration

                    if final_clips:
                        last_clip = final_clips[-1]
                        last_clip, clip = _apply_transition_crossfade(last_clip, clip, transition_duration)
                        final_clips[-1] = last_clip
                    
                    def make_slide_out(t):
                        if t < prev_clip.duration - transition_duration:
                            return (0, 0)
                        else:
                            progress = (t - (prev_clip.duration - transition_duration)) / transition_duration
                            x = -TARGET_RESOLUTION[0] * progress
                            return (x, 0)
                    
                    def make_slide_in(t):
                        if t < transition_duration:
                            progress = t / transition_duration
                            x = TARGET_RESOLUTION[0] * (1 - progress)
                            return (x, 0)
                        else:
                            return (0, 0)
                    
                    clip_with_anim = clip.set_position(make_slide_in).set_start(current_time)
                    final_clips.append(clip_with_anim)
                    current_time += clip.duration
            
            # Add introcard overlay if available
            if introcard_clip:
                introcard_positioned = introcard_clip.set_start(0)
                final_clips.append(introcard_positioned)

            # Add endcard overlay if available
            if endcard_clip:
                endcard_start = current_time - endcard_overlap
                print(f"     Adding endcard at t={endcard_start:.2f}s with fade-in transparency")
                
                # Apply audio fadeout to the last clip to prevent audio pop
                if final_clips and endcard_overlap > 0:
                    last_clip = final_clips[-1]
                    if last_clip.audio:
                        audio_fade_duration = min(endcard_overlap, 0.3)
                        last_clip = last_clip.fx(afx.audio_fadeout, audio_fade_duration)
                        final_clips[-1] = last_clip
                        print(f"     Applied {audio_fade_duration:.2f}s audio fadeout to last clip")
                
                # Apply fade-in effect during overlap period (video + audio)
                if endcard_overlap > 0:
                    endcard_with_fade = endcard_clip.fx(vfx.fadein, endcard_overlap)
                    if endcard_with_fade.audio:
                        audio_fade_duration = min(endcard_overlap, 0.3)
                        endcard_with_fade = endcard_with_fade.fx(afx.audio_fadein, audio_fade_duration)
                    endcard_positioned = endcard_with_fade.set_start(endcard_start)
                else:
                    endcard_positioned = endcard_clip.set_start(endcard_start)
                
                final_clips.append(endcard_positioned)
                current_time = endcard_start + endcard_clip.duration
            
            print("Compositing clips with transitions...")
            final_clip = CompositeVideoClip(final_clips, size=TARGET_RESOLUTION)
            final_clip = final_clip.set_duration(current_time)
            final_clip.fps = get_target_fps(style_config)
        else:
            print("Concatenating clips...")
            final_clip = concatenate_videoclips(video_clips, method="compose")
            
            # Add introcard for non-transition mode
            if introcard_clip:
                introcard_positioned = introcard_clip.set_start(0)
                final_clip = CompositeVideoClip([final_clip, introcard_positioned], size=TARGET_RESOLUTION)
                final_clip = final_clip.set_duration(final_clip.duration)

            # Add endcard for non-transition mode
            if endcard_clip:
                total_dur = final_clip.duration
                endcard_start = total_dur - endcard_overlap
                print(f"     Adding endcard at t={endcard_start:.2f}s with fade-in transparency")
                
                # Apply audio fadeout to main clip to prevent audio pop
                if endcard_overlap > 0 and final_clip.audio:
                    audio_fade_duration = min(endcard_overlap, 0.3)
                    final_clip = final_clip.fx(afx.audio_fadeout, audio_fade_duration)
                    print(f"     Applied {audio_fade_duration:.2f}s audio fadeout to main clip")
                
                # Apply fade-in effect during overlap period (video + audio)
                if endcard_overlap > 0:
                    endcard_with_fade = endcard_clip.fx(vfx.fadein, endcard_overlap)
                    if endcard_with_fade.audio:
                        audio_fade_duration = min(endcard_overlap, 0.3)
                        endcard_with_fade = endcard_with_fade.fx(afx.audio_fadein, audio_fade_duration)
                    endcard_positioned = endcard_with_fade.set_start(endcard_start)
                else:
                    endcard_positioned = endcard_clip.set_start(endcard_start)
                
                final_clip = CompositeVideoClip([final_clip, endcard_positioned], size=TARGET_RESOLUTION)
                final_clip = final_clip.set_duration(endcard_start + endcard_clip.duration)
            
            final_clip.fps = get_target_fps(style_config)

        total_time = time.time() - start_time
        print(f"✅ process_clips complete in {total_time:.1f}s")
        return final_clip
    finally:
        time.sleep(0.5)
        cleanup = os.environ.get("UGC_CLEANUP_TEMP_FILES", "0").strip().lower() in {"1", "true", "yes"}
        if cleanup:
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass
        elif temp_files:
            print("⚠️  Temp background files retained to avoid premature deletion. Set UGC_CLEANUP_TEMP_FILES=1 to remove.")


def process_project_clips(project_dir: str, style_config: Dict[str, Any] = None) -> VideoFileClip:
    """
    Process a UGC project folder with the structure:
    - *_scene_1.mp4 + scene_1_hook.mp3
    - *_scene_2.mp4 + scene_2_body.mp3
    - *broll*.mp4 (no audio reference, uses full duration)
    - *_scene_3.mp4 + scene_3_cta.mp3
    
    Each video is trimmed to match the duration of its corresponding MP3.
    
    Post-processing (color grading, grain, etc.) is applied ONLY to AI-generated
    scenes, NOT to brolls (which are already real footage).
    """
    from moviepy.editor import AudioFileClip
    
    start_time = time.time()
    project_name = os.path.basename(project_dir.rstrip('/'))
    print(f"\n  📁 Project: {project_name}")
    
    # Check if post-processing is enabled for scenes
    postprocess_config = {}
    if style_config:
        postprocess_config = style_config.get("postprocess", {})
    
    use_postprocess = postprocess_config.get("enabled", False)

    alpha_fill_config = {}
    if style_config:
        alpha_fill_config = style_config.get("broll_alpha_fill", {})
    alpha_fill_enabled = alpha_fill_config.get("enabled", False)
    alpha_fill_blur = alpha_fill_config.get("blur_sigma", 8)
    alpha_fill_slow = alpha_fill_config.get("slow_factor", 1.5)
    alpha_force_key = alpha_fill_config.get("force_chroma_key", False)
    alpha_key_similarity = alpha_fill_config.get("chroma_key_similarity", 0.08)
    alpha_key_blend = alpha_fill_config.get("chroma_key_blend", 0.0)
    alpha_key_color = alpha_fill_config.get("chroma_key_color", "0x000000")
    alpha_auto_tune = alpha_fill_config.get("auto_tune", False)
    alpha_tune_min = alpha_fill_config.get("auto_tune_min", 0.05)
    alpha_tune_max = alpha_fill_config.get("auto_tune_max", 0.30)
    alpha_tune_step = alpha_fill_config.get("auto_tune_step", 0.03)
    alpha_detection = style_config.get("alpha_detection", {}) if style_config else {}
    alpha_verbose = bool(alpha_detection.get("verbose", False))
    alpha_use_ffprobe = alpha_detection.get("use_ffprobe", True)
    
    if use_postprocess:
        print("  🎨 Post-processing: ENABLED (AI scenes only)")
        pp_effects = []
        if postprocess_config.get("color_grading", {}).get("enabled"):
            pp_effects.append("color")
        if postprocess_config.get("grain", {}).get("enabled"):
            pp_effects.append(f"grain({postprocess_config.get('grain', {}).get('strength', 0)})")
        if postprocess_config.get("vignette", {}).get("enabled"):
            pp_effects.append("vignette")
        if postprocess_config.get("chromatic_aberration", {}).get("enabled"):
            pp_effects.append("aberration")
        print(f"     Effects: {', '.join(pp_effects)}")
    else:
        print("  🎨 Post-processing: DISABLED")
    
    # Find files in the project directory
    files = os.listdir(project_dir)
    
    # Find scene videos and their corresponding MP3s
    scene_1_video = None
    scene_2_video = None
    scene_3_video = None
    broll_video = None
    
    scene_1_audio = None
    scene_2_audio = None
    scene_3_audio = None
    
    for f in files:
        f_lower = f.lower()
        full_path = os.path.join(project_dir, f)
        
        # Support both .mp4 and .mov video files
        if f_lower.endswith('.mp4') or f_lower.endswith('.mov'):
            if 'scene_1' in f_lower:
                scene_1_video = full_path
            elif 'scene_2' in f_lower:
                scene_2_video = full_path
            elif 'scene_3' in f_lower:
                scene_3_video = full_path
            elif 'broll' in f_lower:
                broll_video = full_path
        elif f_lower.endswith('.mp3'):
            if 'scene_1' in f_lower or 'hook' in f_lower:
                scene_1_audio = full_path
            elif 'scene_2' in f_lower or 'body' in f_lower:
                scene_2_audio = full_path
            elif 'scene_3' in f_lower or 'cta' in f_lower:
                scene_3_audio = full_path
    
    # Report found files
    print("\n  📋 Found assets:")
    print(f"     Scene 1: {'✅' if scene_1_video else '❌'} video, {'✅' if scene_1_audio else '❌'} audio")
    print(f"     Scene 2: {'✅' if scene_2_video else '❌'} video, {'✅' if scene_2_audio else '❌'} audio")
    print(f"     B-Roll:  {'✅' if broll_video else '❌'} video")
    print(f"     Scene 3: {'✅' if scene_3_video else '❌'} video, {'✅' if scene_3_audio else '❌'} audio")
    
    # Build the clips list in order: scene_1, scene_2, broll, scene_3
    clips_info = [
        ("Scene 1 (Hook)", scene_1_video, scene_1_audio, False),  # AI scene
        ("Scene 2 (Body)", scene_2_video, scene_2_audio, False),  # AI scene
        ("B-Roll", broll_video, None, True),                       # Real footage
        ("Scene 3 (CTA)", scene_3_video, scene_3_audio, False),   # AI scene
    ]
    
    video_clips = []
    temp_files = []
    previous_fill_source = None
    total_clips = sum(1 for _, v, _, _ in clips_info if v and os.path.exists(v))
    current_clip = 0
    
    print(f"\n  🎬 Processing {total_clips} clips...")
    
    try:
        for name, video_path, audio_path, is_broll in clips_info:
            if not video_path or not os.path.exists(video_path):
                print(f"     ⚠️  {name}: SKIPPED (not found)")
                continue
            
            current_clip += 1
            clip_start_time = time.time()
            print(f"\n     [{current_clip}/{total_clips}] {name}")
            print(f"         File: {os.path.basename(video_path)}")
            
            # Load original clip first to get audio
            print_clip_status("Loading video...", 3)
            original_audio = None
            broll_has_alpha = False
            if is_broll and alpha_fill_enabled:
                broll_has_alpha = _has_alpha_channel(
                    video_path,
                    use_ffprobe=alpha_use_ffprobe,
                    verbose=alpha_verbose,
                    indent=3,
                    label="broll",
                    require_non_opaque=alpha_require_non_opaque
                )
                if alpha_verbose:
                    if broll_has_alpha:
                        print_clip_status("Alpha detected (b-roll) → will fill with blurred background", 3)
                    elif alpha_force_key:
                        print_clip_status("No alpha detected → forcing chroma key", 3)
                    else:
                        print_clip_status("No alpha detected and force_chroma_key=false → alpha fill skipped", 3)

            if is_broll and alpha_force_key:
                audio_source = VideoFileClip(video_path)
                original_audio = audio_source.audio
                similarity = alpha_key_similarity
                if alpha_auto_tune:
                    similarity = _auto_tune_chroma_key(
                        video_path,
                        alpha_key_blend,
                        temp_files,
                        alpha_tune_min,
                        alpha_tune_max,
                        alpha_tune_step,
                        verbose=alpha_verbose,
                        indent=4
                    )
                alpha_path = _create_chroma_key_alpha(
                    video_path,
                    similarity,
                    alpha_key_blend,
                    temp_files,
                    hex_color=alpha_key_color,
                    edge_feather=alpha_edge_feather
                )
                original_clip = VideoFileClip(alpha_path, has_mask=True)
            elif is_broll and broll_has_alpha:
                original_clip = VideoFileClip(video_path, has_mask=True)
                original_audio = original_clip.audio
            else:
                original_clip = VideoFileClip(video_path)
                original_audio = original_clip.audio
            print_clip_status(f"Loaded: {original_clip.duration:.2f}s @ {original_clip.fps}fps", 3)

            # Tiny fades to avoid audio pops at transitions (does not affect music)
            if not transitions_enabled:
                original_audio = _apply_transition_audio_fades(original_audio, original_clip.duration)
            
            # DEBUG: Export b-roll with alpha for inspection
            if alpha_verbose and is_broll and (broll_has_alpha or alpha_force_key):
                debug_folder = "/app/exports/debug"
                os.makedirs(debug_folder, exist_ok=True)
                clip_basename = os.path.splitext(os.path.basename(video_path))[0]
                print_clip_status(f"DEBUG: Exporting alpha frames for {clip_basename}...", 3)
                export_broll_with_alpha_debug(
                    original_clip,
                    debug_folder,
                    clip_basename,
                    sample_count=5
                )
            
            # Apply post-processing to AI scenes BEFORE loading into MoviePy
            source_for_fill = video_path
            if use_postprocess and not is_broll:
                from ugc_pipeline.postprocess import apply_postprocess
                
                # Create temp file for processed video
                temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                os.close(temp_fd)
                temp_files.append(temp_path)
                
                print_clip_status("Applying post-processing (FFmpeg)...", 3)
                pp_start = time.time()
                success = apply_postprocess(
                    input_path=video_path,
                    output_path=temp_path,
                    config=postprocess_config,
                    verbose=True  # Enable verbose for debugging
                )
                
                if success:
                    # Load processed video but keep ORIGINAL audio (to avoid sync issues)
                    processed_clip = VideoFileClip(temp_path)
                    clip = processed_clip.set_audio(original_audio)
                    source_for_fill = temp_path
                    print_clip_status(f"Post-processed OK ({time.time() - pp_start:.1f}s)", 3)
                else:
                    print_clip_status("Post-processing FAILED, using original", 3)
                    clip = original_clip
            else:
                clip = original_clip
                if is_broll and use_postprocess:
                    print_clip_status("Skipping post-process (real footage)", 3)
            
            # Get target duration from MP3 if available
            if audio_path and os.path.exists(audio_path):
                audio_clip = AudioFileClip(audio_path)
                target_duration = audio_clip.duration
                audio_clip.close()
                print_clip_status(f"Trimming to {target_duration:.2f}s (from MP3)", 3)
                
                # Trim video to match audio duration
                if clip.duration > target_duration:
                    clip = clip.subclip(0, target_duration)
            else:
                print_clip_status(f"Using full duration: {clip.duration:.2f}s", 3)
            
            # Resize/Crop to 9:16 (1080x1920)
            print_clip_status(f"Resizing {clip.w}x{clip.h} → {TARGET_RESOLUTION[0]}x{TARGET_RESOLUTION[1]}", 3)

            if is_broll and (broll_has_alpha or alpha_force_key) and alpha_fill_enabled:
                if previous_fill_source:
                    print_clip_status("Building blurred background (FFmpeg)...", 3)
                    bg_path = _create_blurred_slow_background(
                        previous_fill_source,
                        clip.duration,
                        alpha_fill_blur,
                        alpha_fill_slow,
                        temp_files
                    )
                    bg_clip = VideoFileClip(bg_path).without_audio()
                    if bg_clip.duration < clip.duration:
                        bg_clip = bg_clip.loop(duration=clip.duration)
                    bg_clip = _resize_to_target(bg_clip)
                    clip = _resize_to_target(clip)
                    clip = CompositeVideoClip(
                        [bg_clip, clip.set_position("center")],
                        size=TARGET_RESOLUTION
                    ).set_duration(clip.duration)
                    clip = clip.set_audio(original_audio)
                else:
                    if alpha_verbose:
                        print_clip_status("Alpha fill enabled but no previous clip available; using normal resize", 3)
                    clip = _resize_to_target(clip)
            else:
                clip = _resize_to_target(clip)
            
            clip_elapsed = time.time() - clip_start_time
            print_clip_status(f"✅ Done ({clip_elapsed:.1f}s)", 3)
            video_clips.append(clip)
            previous_fill_source = source_for_fill
        
        if not video_clips:
            raise ValueError("No valid clips found in project folder.")
        
        # Get endcard if enabled
        geo = get_geo_from_project_name(project_name)
        endcard_clip = None
        endcard_overlap = 0
        
        if geo and style_config:
            endcard_config = style_config.get("endcard", {})
            if endcard_config.get("enabled", False):
                endcard_path = get_endcard_path(style_config, geo)
                if endcard_path:
                    print(f"\n  🎬 Loading endcard for {geo}...")
                    endcard_overlap = endcard_config.get("overlap_seconds", 1.25)
                    try:
                        endcard_alpha_config = _resolve_endcard_alpha_config(style_config)
                        endcard_force_key = endcard_alpha_config.get("force_chroma_key", False)
                        endcard_has_alpha = _has_alpha_channel(
                            endcard_path,
                            use_ffprobe=alpha_use_ffprobe,
                            verbose=alpha_verbose,
                            indent=3,
                            label="endcard",
                            require_non_opaque=alpha_require_non_opaque
                        )

                        if endcard_force_key:
                            similarity = endcard_alpha_config.get("chroma_key_similarity", 0.08)
                            blend = endcard_alpha_config.get("chroma_key_blend", 0.0)
                            edge_feather = endcard_alpha_config.get("edge_feather", 0)
                            hex_color = endcard_alpha_config.get("chroma_key_color", "0x000000")
                            print_clip_status(
                                f"Endcard alpha-fill config: color={hex_color}, sim={similarity}, blend={blend}, blur={endcard_alpha_config.get('blur_sigma', 8)}, slow={endcard_alpha_config.get('slow_factor', 1.5)}",
                                3
                            )
                            auto_tune = endcard_alpha_config.get("auto_tune", False)
                            if auto_tune:
                                similarity = _auto_tune_chroma_key(
                                    endcard_path,
                                    blend,
                                    temp_files,
                                    endcard_alpha_config.get("auto_tune_min", 0.05),
                                    endcard_alpha_config.get("auto_tune_max", 0.30),
                                    endcard_alpha_config.get("auto_tune_step", 0.03),
                                    verbose=alpha_verbose,
                                    indent=4
                                )
                            alpha_path = _create_chroma_key_alpha(
                                endcard_path,
                                similarity,
                                blend,
                                temp_files,
                                hex_color=hex_color,
                                edge_feather=edge_feather
                            )
                            endcard_raw = VideoFileClip(alpha_path, has_mask=True)
                            endcard_has_alpha = True
                        else:
                            endcard_raw = VideoFileClip(endcard_path, has_mask=True)

                        # Resize endcard to target resolution
                        endcard_clip = endcard_raw.resize(TARGET_RESOLUTION)
                        if endcard_raw.mask is not None and endcard_clip.mask is None:
                            endcard_clip = endcard_clip.set_mask(endcard_raw.mask.resize(endcard_clip.size))
                        if endcard_alpha_config.get("enabled", False) and endcard_alpha_config.get("use_blur_background", False) and previous_fill_source:
                            blur_sigma = endcard_alpha_config.get("blur_sigma", 8)
                            slow_factor = endcard_alpha_config.get("slow_factor", 1.5)
                            bg_path = _create_blurred_slow_background(
                                previous_fill_source,
                                endcard_clip.duration,
                                blur_sigma,
                                slow_factor,
                                temp_files
                            )
                            bg_clip = VideoFileClip(bg_path).without_audio()
                            if bg_clip.duration < endcard_clip.duration:
                                bg_clip = bg_clip.loop(duration=endcard_clip.duration)
                            bg_clip = _resize_to_target(bg_clip)
                            endcard_clip = _resize_to_target(endcard_clip)
                            endcard_clip = CompositeVideoClip(
                                [bg_clip, endcard_clip.set_position("center")],
                                size=TARGET_RESOLUTION
                            ).set_duration(endcard_clip.duration).set_audio(endcard_clip.audio)
                            print("     Endcard alpha-fill: enabled (b-roll style)")
                        elif endcard_alpha_config.get("enabled", False) and not endcard_alpha_config.get("use_blur_background", False):
                            print_clip_status("Endcard alpha-fill background disabled; preserving transparency", 3)
                        elif alpha_verbose and endcard_alpha_config.get("enabled", False):
                            if not endcard_has_alpha:
                                print_clip_status("Endcard alpha-fill enabled but no alpha detected; skipping fill", 3)
                            elif not previous_fill_source:
                                print_clip_status("Endcard alpha-fill enabled but no previous clip available; skipping fill", 3)
                        print(f"     Endcard: {os.path.basename(endcard_path)} ({endcard_clip.duration:.2f}s)")
                        print(f"     Overlap: {endcard_overlap}s before Scene 3 ends")
                    except Exception as e:
                        print(f"     ⚠️ Failed to load endcard: {e}")
                        endcard_clip = None
        
        # Apply transitions if enabled
        if style_config and style_config.get("transitions", {}).get("enabled", False):
            transition_duration = style_config.get("transitions", {}).get("duration", 0.5)
            print(f"\n  🔀 Applying slide transitions ({transition_duration}s duration)...")
            
            final_clips = []
            current_time = 0
            
            for i, clip in enumerate(video_clips):
                if i == 0:
                    final_clips.append(clip.set_start(current_time))
                    current_time += clip.duration
                else:
                    current_time -= transition_duration

                    if final_clips:
                        last_clip = final_clips[-1]
                        last_clip, clip = _apply_transition_crossfade(last_clip, clip, transition_duration)
                        final_clips[-1] = last_clip
                    
                    def make_slide_in(t, trans_dur=transition_duration):
                        if t < trans_dur:
                            progress = t / trans_dur
                            x = TARGET_RESOLUTION[0] * (1 - progress)
                            return (x, 0)
                        else:
                            return (0, 0)
                    
                    clip_with_anim = clip.set_position(make_slide_in).set_start(current_time)
                    final_clips.append(clip_with_anim)
                    current_time += clip.duration
            
            # Add endcard overlay if available
            # Endcard starts (overlap_seconds) before the end of the video
            if endcard_clip:
                endcard_start = current_time - endcard_overlap
                print(f"     Adding endcard at t={endcard_start:.2f}s with fade-in transparency")
                
                # Apply audio fadeout to the last clip (scene 3) to prevent audio pop
                if final_clips and endcard_overlap > 0:
                    last_clip = final_clips[-1]
                    if last_clip.audio:
                        audio_fade_duration = min(endcard_overlap, 0.3)  # Max 0.3s audio fade
                        last_clip = last_clip.fx(afx.audio_fadeout, audio_fade_duration)
                        final_clips[-1] = last_clip
                        print(f"     Applied {audio_fade_duration:.2f}s audio fadeout to last clip")
                
                # Apply fade-in effect during overlap period (video + audio)
                if endcard_overlap > 0:
                    endcard_with_fade = endcard_clip.fx(vfx.fadein, endcard_overlap)
                    # Also fade in endcard audio to prevent pop
                    if endcard_with_fade.audio:
                        audio_fade_duration = min(endcard_overlap, 0.3)
                        endcard_with_fade = endcard_with_fade.fx(afx.audio_fadein, audio_fade_duration)
                    endcard_positioned = endcard_with_fade.set_start(endcard_start)
                else:
                    endcard_positioned = endcard_clip.set_start(endcard_start)
                
                final_clips.append(endcard_positioned)
                # Extend total duration to include full endcard
                current_time = endcard_start + endcard_clip.duration
            
            print("     Compositing clips with transitions...")
            final_clip = CompositeVideoClip(final_clips, size=TARGET_RESOLUTION)
            final_clip = final_clip.set_duration(current_time)
            final_clip.fps = get_target_fps(style_config)
        else:
            print(f"\n  🔗 Concatenating {len(video_clips)} clips...")
            final_clip = concatenate_videoclips(video_clips, method="compose")
            
            # Add endcard for non-transition mode
            if endcard_clip:
                total_dur = final_clip.duration
                endcard_start = total_dur - endcard_overlap
                print(f"     Adding endcard at t={endcard_start:.2f}s with fade-in transparency")
                
                # Apply audio fadeout to main clip (scene 3) to prevent audio pop
                if endcard_overlap > 0 and final_clip.audio:
                    audio_fade_duration = min(endcard_overlap, 0.3)  # Max 0.3s audio fade
                    final_clip = final_clip.fx(afx.audio_fadeout, audio_fade_duration)
                    print(f"     Applied {audio_fade_duration:.2f}s audio fadeout to main clip")
                
                # Apply fade-in effect during overlap period
                if endcard_overlap > 0:
                    def fade_in_concat(get_frame, t):
                        """Apply fade-in transparency effect"""
                        frame = get_frame(t)
                        if t < endcard_overlap:
                            # Fade from transparent to opaque during overlap
                            alpha = t / endcard_overlap
                            return (frame * alpha).astype('uint8')
                        return frame
                    
                    endcard_with_fade = endcard_clip.fl(fade_in_concat)
                    # Also fade in endcard audio to prevent pop
                    if endcard_with_fade.audio:
                        audio_fade_duration = min(endcard_overlap, 0.3)
                        endcard_with_fade = endcard_with_fade.fx(afx.audio_fadein, audio_fade_duration)
                    endcard_positioned = endcard_with_fade.set_start(endcard_start)
                else:
                    endcard_positioned = endcard_clip.set_start(endcard_start)
                
                final_clip = CompositeVideoClip([final_clip, endcard_positioned], size=TARGET_RESOLUTION)
                final_clip = final_clip.set_duration(endcard_start + endcard_clip.duration)
            
            final_clip.fps = get_target_fps(style_config)
        
        total_duration = sum(c.duration for c in video_clips)
        print(f"  ⏱️  Total duration: {total_duration:.2f}s")
        print(f"✅ process_project_clips complete in {time.time() - start_time:.1f}s")
        
        return final_clip
        
    finally:
        # Clean up temp files after a delay (they may still be in use)
        # MoviePy should have loaded them into memory by now
        if temp_files:
            print(f"\n  🧹 Cleaning up {len(temp_files)} temp files...")
        time.sleep(0.5)
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
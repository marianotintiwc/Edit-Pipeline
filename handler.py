"""
RunPod Serverless Handler for UGC Video Pipeline.

This module provides a serverless API endpoint for processing videos with
UGC-style editing (concatenation, music, animated subtitles, optional RIFE
frame interpolation), returning the final video URL from S3.

Usage:
    Deploy as a RunPod serverless endpoint. The handler accepts JSON input
    with video URLs and editing parameters, processes them, and returns
    an S3 URL to the final video.

Input Schema:
    {
        # === VIDEO INPUT (use ONE of these) ===
        "video_urls": [str, ...],              # Legacy: list of video URLs (all treated as scenes)
        "clips": [                              # NEW: Ordered list of clips with metadata
            {
                "type": "scene" | "broll" | "endcard" | "introcard",  # Clip type
                "url": str,                    # Video URL (http/https)
                "start_time": float | None,    # Optional trim start (seconds)
                "end_time": float | None,      # Optional trim end (seconds, use -0.1 for "cut 0.1s before end")
                "alpha_fill": dict | None,     # Optional per-clip override for alpha fill (broll/endcard)
                "overlap_seconds": float | None, # Optional per-clip endcard overlap
                "effects": dict | None         # Optional per-clip effects (future)
            }
        ],
        
        # === GEO & LANGUAGE ===
        "geo": str,                            # NEW: "MLA" | "MLB" | "MLC" | "MLM" (MLB=Portuguese, others=Spanish)
        
        # === MUSIC ===
        "music_url": str | "random" | None,    # NEW: "random" picks from assets/audio
        "music_volume": float,                 # 0.0 - 1.0 (default: 0.3)
        "loop_music": bool,                    # Loop music to video length (default: true)
        
        # === SUBTITLES ===
        "subtitle_mode": str,                  # "auto" | "manual" | "none"
        "manual_srt_url": str | None,          # SRT URL if subtitle_mode="manual"
        
        # === PROCESSING ===
        "edit_preset": str,                    # "standard_vertical", "no_interpolation", "no_subtitles", "simple_concat"
        "enable_interpolation": bool,          # Enable RIFE (default: true)
        "rife_model": str,                     # "rife-v4" | "rife-v4.6" (default: "rife-v4")
        "style_overrides": dict | None         # Partial style.json overrides
    }
    
    Example (new format with scenes + b-roll):
    {
        "geo": "MLA",
        "clips": [
            {"type": "scene", "url": "https://..."},
            {"type": "scene", "url": "https://..."},
            {"type": "broll", "url": "https://..."},
            {"type": "scene", "url": "https://...", "end_time": -0.1},
            {"type": "broll", "url": "https://..."}
        ],
        "music_url": "random",
        "subtitle_mode": "auto",
        "edit_preset": "standard_vertical"
    }

Output Schema:
    {
        "output_url": str,        # S3 URL to final video
        "message": str,           # Success message
        "duration_seconds": float, # Video duration
        "logs": [str]             # Processing logs
    }

Error Schema:
    {
        "error": str,             # Error message
        "error_type": str,        # Exception type
        "logs": [str]             # Logs up to failure point
    }
"""

import os
import sys
import json
import tempfile
import shutil
import time
import logging
import traceback
import random
import glob
import re
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

import runpod
import requests
import boto3
from botocore.exceptions import ClientError

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from startup_check import validate_environment, RIFENotAvailableError, VulkanNotAvailableError


# ─────────────────────────────────────────────────────────────────────────────
# Configuration & Constants
# ─────────────────────────────────────────────────────────────────────────────

class EditPreset(str, Enum):
    """Available editing presets."""
    STANDARD_VERTICAL = "standard_vertical"  # Full UGC: 9:16, subs, music, RIFE
    NO_INTERPOLATION = "no_interpolation"    # Skip RIFE frame interpolation
    NO_SUBTITLES = "no_subtitles"            # Disable subtitle generation
    SIMPLE_CONCAT = "simple_concat"          # Just concatenate, minimal processing
    HORIZONTAL = "horizontal"                # 16:9 output (future)


class SubtitleMode(str, Enum):
    """Subtitle generation modes."""
    AUTO = "auto"      # Whisper transcription
    MANUAL = "manual"  # Download SRT from URL
    NONE = "none"      # No subtitles


@dataclass
class ClipInput:
    """Single clip input with metadata."""
    url: str
    clip_type: str = "scene"  # "scene", "broll", "endcard", or "introcard"
    start_time: Optional[float] = None
    end_time: Optional[float] = None  # Use negative values for "cut X seconds before end" (e.g., -0.1)
    alpha_fill: Optional[Dict[str, Any]] = None
    overlap_seconds: Optional[float] = None
    effects: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not self.url.startswith(('http://', 'https://')):
            raise ValueError(f"Clip URL must be HTTP/HTTPS, got: {self.url}")
        if self.clip_type not in ("scene", "broll", "endcard", "introcard"):
            raise ValueError(f"clip_type must be 'scene', 'broll', 'endcard', or 'introcard', got: {self.clip_type}")
        if self.alpha_fill is not None and not isinstance(self.alpha_fill, dict):
            raise ValueError("alpha_fill must be an object when provided")
        if self.effects is not None and not isinstance(self.effects, dict):
            raise ValueError("effects must be an object when provided")
        if self.overlap_seconds is not None:
            if not isinstance(self.overlap_seconds, (int, float)):
                raise ValueError("overlap_seconds must be a number when provided")
            if self.overlap_seconds < 0:
                raise ValueError("overlap_seconds must be >= 0 when provided")


class Geo(str, Enum):
    """Supported geographic regions."""
    MLA = "MLA"  # Argentina - Spanish
    MLB = "MLB"  # Brazil - Portuguese  
    MLC = "MLC"  # Chile - Spanish
    MLM = "MLM"  # Mexico - Spanish


def get_whisper_language(geo: Optional[str]) -> str:
    """Get Whisper language code based on geo. MLB=Portuguese, others=Spanish."""
    if geo and geo.upper() == "MLB":
        return "pt"
    return "es"


def get_random_music_path() -> Optional[str]:
    """Select a random music file from assets/audio."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    audio_dir = os.path.join(base_dir, "assets", "audio")
    
    audio_extensions = ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.ogg']
    music_files = []
    
    for ext in audio_extensions:
        music_files.extend(glob.glob(os.path.join(audio_dir, ext)))
    
    if not music_files:
        return None
    
    return random.choice(music_files)


@dataclass
class JobInput:
    """Validated job input parameters."""
    # Video input - support both legacy (video_urls) and new (clips) format
    video_urls: Optional[List[str]] = None
    clips: Optional[List[ClipInput]] = None
    
    # Geo for language detection
    geo: Optional[str] = None
    
    # Processing options
    edit_preset: EditPreset = EditPreset.STANDARD_VERTICAL
    music_url: Optional[str] = None  # Can be URL, "random", or None
    music_volume: float = 0.3
    loop_music: bool = True
    subtitle_mode: SubtitleMode = SubtitleMode.AUTO
    manual_srt_url: Optional[str] = None
    enable_interpolation: bool = True
    rife_model: str = "rife-v4"
    style_overrides: Optional[Dict[str, Any]] = None
    output_filename: Optional[str] = None
    output_folder: Optional[str] = None  # Custom S3 folder path (e.g., "TAP_Exports/2026-01")
    
    def __post_init__(self):
        """Validate inputs after initialization."""
        # Must have either video_urls or clips
        if not self.video_urls and not self.clips:
            raise ValueError("Either 'video_urls' or 'clips' must be provided")
        
        # If using legacy video_urls, convert to clips format
        if self.video_urls and not self.clips:
            self.clips = [
                ClipInput(url=url, clip_type="scene")
                for url in self.video_urls
            ]
        
        # Validate clips
        if not self.clips or len(self.clips) == 0:
            raise ValueError("At least one clip is required")
        
        for clip in self.clips:
            if isinstance(clip, dict):
                # Convert dict to ClipInput
                pass  # Will be handled in parse_clips
            elif not isinstance(clip, ClipInput):
                raise ValueError(f"Invalid clip format: {clip}")
        
        # Validate music volume
        if self.music_volume < 0.0 or self.music_volume > 1.0:
            raise ValueError(f"music_volume must be 0.0-1.0, got {self.music_volume}")
        
        # Validate subtitle mode
        if self.subtitle_mode == SubtitleMode.MANUAL and not self.manual_srt_url:
            raise ValueError("manual_srt_url required when subtitle_mode='manual'")
        
        # Validate geo if provided
        if self.geo:
            self.geo = self.geo.upper()
            if self.geo not in ["MLA", "MLB", "MLC", "MLM"]:
                raise ValueError(f"geo must be MLA, MLB, MLC, or MLM, got: {self.geo}")
        
        # Convert string enums if needed
        if isinstance(self.edit_preset, str):
            self.edit_preset = EditPreset(self.edit_preset)
        if isinstance(self.subtitle_mode, str):
            self.subtitle_mode = SubtitleMode(self.subtitle_mode)
    
    def get_whisper_language(self) -> str:
        """Get Whisper language based on geo."""
        return get_whisper_language(self.geo)
    
    def get_resolved_music_path(self) -> Optional[str]:
        """Resolve music_url: if 'random', pick from assets/audio; otherwise return as-is."""
        if self.music_url == "random":
            return get_random_music_path()
        return self.music_url  # URL or None


@dataclass 
class ProcessingContext:
    """Context for a single processing job."""
    job_id: str
    work_dir: str
    logs: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def log(self, message: str, level: str = "INFO"):
        """Add a log entry."""
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(entry)
        print(entry)
        
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    @contextmanager
    def time_block(self, label: str, include_gpu: bool = False):
        """Context manager to time a block and log start/end."""
        start = time.time()
        self.log(f"{label} started")
        if include_gpu:
            self.log(f"GPU snapshot ({label} start): {get_gpu_utilization()}")
        try:
            yield
        finally:
            if include_gpu:
                self.log(f"GPU snapshot ({label} end): {get_gpu_utilization()}")
            self.log(f"{label} finished in {time.time() - start:.1f}s")


# ─────────────────────────────────────────────────────────────────────────────
# S3 Upload
# ─────────────────────────────────────────────────────────────────────────────

def get_s3_client():
    """Create S3 client from environment variables."""
    return boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION', 'us-east-1')
    )


def upload_to_s3(
    local_path: str,
    bucket: str,
    key: str,
    content_type: str = 'video/mp4'
) -> str:
    """
    Upload a file to S3 and return the public URL.
    
    Args:
        local_path: Path to local file
        bucket: S3 bucket name
        key: S3 object key (path within bucket)
        content_type: MIME type for the file
        
    Returns:
        Public URL to the uploaded file
    """
    s3 = get_s3_client()
    
    s3.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={
            'ContentType': content_type
        }
    )
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    if region == 'us-east-1':
        url = f"https://{bucket}.s3.amazonaws.com/{key}"
    else:
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    
    return url


def download_from_s3(
    bucket: str,
    key: str,
    dest_path: str,
    silent: bool = False
) -> str:
    """
    Download a file from S3 to local path.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key (path within bucket)
        dest_path: Local destination path
        silent: If True, suppress print output
        
    Returns:
        Path to downloaded file
    """
    s3 = get_s3_client()
    
    # Ensure destination directory exists
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    if not silent:
        print(f"Downloading s3://{bucket}/{key} -> {dest_path}")
    
    s3.download_file(bucket, key, dest_path)
    
    if not silent:
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"Downloaded: {os.path.basename(dest_path)} ({size_mb:.1f} MB)")
    
    return dest_path


# ─────────────────────────────────────────────────────────────────────────────
# File Downloads
# ─────────────────────────────────────────────────────────────────────────────

def parse_s3_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Parse an S3 URL to extract bucket and key.
    
    Supports formats:
    - https://bucket.s3.amazonaws.com/key
    - https://bucket.s3.region.amazonaws.com/key
    - https://s3.region.amazonaws.com/bucket/key
    - s3://bucket/key
    
    Returns:
        Tuple of (bucket, key) or None if not an S3 URL
    """
    import re
    
    # s3:// format
    if url.startswith('s3://'):
        parts = url[5:].split('/', 1)
        return (parts[0], parts[1]) if len(parts) == 2 else None
    
    # https://bucket.s3.amazonaws.com/key or https://bucket.s3.region.amazonaws.com/key
    match = re.match(r'https?://([^.]+)\.s3(?:\.([a-z0-9-]+))?\.amazonaws\.com/(.+)', url)
    if match:
        bucket = match.group(1)
        key = match.group(3)
        return (bucket, key)
    
    # https://s3.region.amazonaws.com/bucket/key
    match = re.match(r'https?://s3\.([a-z0-9-]+)\.amazonaws\.com/([^/]+)/(.+)', url)
    if match:
        bucket = match.group(2)
        key = match.group(3)
        return (bucket, key)
    
    return None


def download_file(url: str, dest_path: str, ctx: ProcessingContext) -> str:
    """
    Download a file from URL to local path.
    Automatically detects S3 URLs and uses authenticated boto3 download.
    
    Args:
        url: Source URL
        dest_path: Destination file path
        ctx: Processing context for logging
        
    Returns:
        Path to downloaded file
    """
    ctx.log(f"Downloading: {url[:80]}...")
    
    # Check if this is an S3 URL that needs authenticated download
    s3_info = parse_s3_url(url)
    if s3_info:
        bucket, key = s3_info
        ctx.log(f"  [S3] Authenticated download from {bucket}/{key[:50]}...")
        try:
            s3 = get_s3_client()
            s3.download_file(bucket, key, dest_path)
            size_mb = os.path.getsize(dest_path) / (1024 * 1024)
            ctx.log(f"Downloaded: {os.path.basename(dest_path)} ({size_mb:.1f} MB)")
            return dest_path
        except Exception as e:
            ctx.log(f"  [S3] Auth download failed: {e}, trying public URL...")
            # Fall through to try as public URL
    
    # Try as public URL
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
    
    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    ctx.log(f"Downloaded: {os.path.basename(dest_path)} ({size_mb:.1f} MB)")
    
    return dest_path


def download_videos(
    clips: List[ClipInput],
    work_dir: str,
    ctx: ProcessingContext
) -> List[Dict[str, Any]]:
    """
    Download all input videos to work directory.
    
    Returns list of clip dicts with local paths and trim info.
    """
    video_dir = os.path.join(work_dir, "videos")
    os.makedirs(video_dir, exist_ok=True)
    
    downloaded_clips = []
    for i, clip in enumerate(clips):
        # Extract extension from URL or default to .mp4
        ext = os.path.splitext(clip.url.split('?')[0])[1] or '.mp4'
        # Handle different clip types for file naming
        if clip.clip_type == "broll":
            clip_type_prefix = "broll"
        elif clip.clip_type == "endcard":
            clip_type_prefix = "endcard"
        elif clip.clip_type == "introcard":
            clip_type_prefix = "introcard"
        else:
            clip_type_prefix = "scene"
        dest = os.path.join(video_dir, f"{clip_type_prefix}_{i+1}{ext}")
        download_file(clip.url, dest, ctx)
        
        downloaded_clips.append({
            "path": dest,
            "type": clip.clip_type,
            "start": clip.start_time,
            "end": clip.end_time,
            "alpha_fill": clip.alpha_fill,
            "overlap_seconds": clip.overlap_seconds,
            "effects": clip.effects
        })
        ctx.log(f"  [{clip.clip_type.upper()}] {os.path.basename(dest)}")
    
    return downloaded_clips


# ─────────────────────────────────────────────────────────────────────────────
# Configuration Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_clips_config(downloaded_clips: List[Dict[str, Any]], work_dir: str, ctx: ProcessingContext) -> str:
    """
    Generate clips.json configuration for the pipeline.
    
    Args:
        downloaded_clips: List of clip dicts with path, type, start, end
        work_dir: Working directory
        ctx: Processing context for logging
        
    Returns:
        Path to generated clips.json
    """
    from moviepy.editor import VideoFileClip
    
    clips = []
    for clip_data in downloaded_clips:
        path = clip_data["path"]
        start = clip_data.get("start")
        end = clip_data.get("end")
        
        # Handle negative end_time (e.g., -0.1 means "cut 0.1s before actual end")
        if end is not None and end < 0:
            original_end = end
            try:
                with VideoFileClip(path) as temp_clip:
                    actual_duration = temp_clip.duration
                    end = actual_duration + end  # e.g., 10.0 + (-0.1) = 9.9
                    ctx.log(f"  Trim: {os.path.basename(path)} cut to {end:.2f}s (removed {-original_end:.2f}s from end)")
            except Exception as e:
                ctx.log(f"  Warning: Could not get duration for {path}: {e}", "WARN")
                end = None
        
        clips.append({
            "path": path,
            "type": clip_data.get("type", "scene"),
            "start": start,
            "end": end,
            "alpha_fill": clip_data.get("alpha_fill"),
            "overlap_seconds": clip_data.get("overlap_seconds"),
            "effects": clip_data.get("effects")
        })
    
    config = {"clips": clips}
    
    config_path = os.path.join(work_dir, "clips.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    ctx.log(f"Generated clips.json with {len(clips)} clips")
    return config_path
    
    config_path = os.path.join(work_dir, "clips.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    return config_path


def generate_style_config(
    job_input: JobInput,
    work_dir: str,
    ctx: ProcessingContext
) -> str:
    """
    Generate style.json configuration based on preset and overrides.
    
    Args:
        job_input: Validated job input
        work_dir: Working directory
        ctx: Processing context
        
    Returns:
        Path to generated style.json
    """
    # Base style configuration
    style = {
        "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
        "fontsize": 80,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "position": "center_bottom",
        "margin_bottom": 550,
        "highlight": {
            "enabled": True,
            "color": "white",
            "bg_color": "#FFE600",
            "fontsize_multiplier": 1.0
        },
        "animation": {
            "enabled": True,
            "type": "pop_in",
            "duration": 0.2,
            "scale_start": 0.5,
            "scale_end": 1.0
        },
        "transcription": {
            "model": "small",
            "keywords": "UGC, TikTok, Marketing",
            "word_level": True,
            "max_words_per_segment": 4,
            "max_delay_seconds": 0.5
        },
        "shadow": {
            "enabled": True,
            "color": "black",
            "offset": 4,
            "opacity": 0.5,
            "blur": 3
        },
        "transitions": {
            "enabled": True,
            "type": "slide",
            "direction": "left",
            "duration": 0.3
        },
        "endcard": {
            "enabled": False,
            "overlap_seconds": 0.5
        },
        "postprocess": {
            "enabled": True,
            "frame_interpolation": {
                "enabled": job_input.enable_interpolation,
                "input_fps": 24,
                "target_fps": 60,
                "model": job_input.rife_model,
                "gpu_id": 0
            },
            "color_grading": {
                "enabled": True,
                "brightness": -0.08,
                "contrast": 0.7,
                "saturation": 1.0,
                "gamma": 1.0
            },
            "grain": {
                "enabled": True,
                "strength": 10,
                "temporal": True
            },
            "vignette": {
                "enabled": True,
                "intensity": 0.785
            },
            "output": {
                "crf": 23,
                "preset": "slow"
            }
        },
        "audio": {
            "music_volume": job_input.music_volume,
            "loop_music": job_input.loop_music
        },
        "broll_alpha_fill": {
            "enabled": True,
            "blur_sigma": 60,
            "slow_factor": 1.5,
            "force_chroma_key": True,
            "chroma_key_color": "0x1F1F1F",
            "chroma_key_similarity": 0.01,
            "chroma_key_blend": 0.0,
            "edge_feather": 5,
            "auto_tune": False,
            "auto_tune_min": 0.05,
            "auto_tune_max": 0.30,
            "auto_tune_step": 0.03
        },
        "endcard_alpha_fill": {
            "enabled": False,
            "force_chroma_key": False,
            "use_blur_background": False
        },
        "introcard_alpha_fill": {
            "enabled": True,
            "force_chroma_key": False,
            "use_blur_background": False
        }
    }
    
    # Apply preset modifications
    preset = job_input.edit_preset
    
    if preset == EditPreset.NO_INTERPOLATION:
        style["postprocess"]["frame_interpolation"]["enabled"] = False
        ctx.log("Preset: NO_INTERPOLATION - RIFE disabled")
        
    elif preset == EditPreset.NO_SUBTITLES:
        # Subtitles handled separately, but mark in style for reference
        style["subtitles_enabled"] = False
        ctx.log("Preset: NO_SUBTITLES - Subtitles disabled")
        
    elif preset == EditPreset.SIMPLE_CONCAT:
        style["postprocess"]["enabled"] = False
        style["transitions"]["enabled"] = False
        style["subtitles_enabled"] = False
        ctx.log("Preset: SIMPLE_CONCAT - Minimal processing")
        
    elif preset == EditPreset.HORIZONTAL:
        # Future: 16:9 output
        style["resolution"] = [1920, 1080]
        ctx.log("Preset: HORIZONTAL - 16:9 output")
    
    # Apply user overrides (deep merge)
    if job_input.style_overrides:
        style = deep_merge(style, job_input.style_overrides)
        ctx.log(f"Applied {len(job_input.style_overrides)} style overrides")
    
    # Validate RIFE if enabled
    if style["postprocess"]["frame_interpolation"]["enabled"]:
        try:
            from startup_check import check_rife_binary
            check_rife_binary()
            ctx.log("RIFE validation: OK")
        except RIFENotAvailableError as e:
            raise RuntimeError(
                f"RIFE frame interpolation is enabled but not available: {e}. "
                "Set enable_interpolation=false or fix RIFE installation."
            )
    
    config_path = os.path.join(work_dir, "style.json")
    with open(config_path, 'w') as f:
        json.dump(style, f, indent=2)
    
    return config_path


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


VALID_INPUT_KEYS = {
    "video_urls",
    "clips",
    "geo",
    "music_url",
    "music_volume",
    "loop_music",
    "subtitle_mode",
    "manual_srt_url",
    "edit_preset",
    "enable_interpolation",
    "rife_model",
    "style_overrides",
    "output_filename",
    "output_folder",
    "project_name",
    "job_id"
}

VALID_CLIP_KEYS = {
    "type",
    "url",
    "start_time",
    "end_time",
    "alpha_fill",
    "overlap_seconds",
    "effects",
    "duration",
    "invert_alpha"
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_alpha_fill_config(alpha_cfg: Dict[str, Any], prefix: str) -> None:
    """Validate alpha_fill config for expected types and ranges."""
    if not isinstance(alpha_cfg, dict):
        raise ValueError(f"{prefix} must be an object")

    def _check_bool(key: str):
        if key in alpha_cfg and alpha_cfg[key] is not None and not isinstance(alpha_cfg[key], bool):
            raise ValueError(f"{prefix}.{key} must be a boolean")

    def _check_number(key: str, min_val: float | None = None, max_val: float | None = None):
        if key in alpha_cfg and alpha_cfg[key] is not None:
            if not _is_number(alpha_cfg[key]):
                raise ValueError(f"{prefix}.{key} must be a number")
            if min_val is not None and alpha_cfg[key] < min_val:
                raise ValueError(f"{prefix}.{key} must be >= {min_val}")
            if max_val is not None and alpha_cfg[key] > max_val:
                raise ValueError(f"{prefix}.{key} must be <= {max_val}")

    _check_bool("enabled")
    _check_number("blur_sigma", min_val=0)
    _check_number("slow_factor", min_val=0)
    _check_bool("force_chroma_key")
    _check_number("chroma_key_similarity", min_val=0, max_val=1)
    _check_number("chroma_key_blend", min_val=0, max_val=1)
    _check_number("edge_feather", min_val=0)
    _check_bool("auto_tune")
    _check_number("auto_tune_min", min_val=0, max_val=1)
    _check_number("auto_tune_max", min_val=0, max_val=1)
    _check_number("auto_tune_step", min_val=0, max_val=1)
    _check_bool("invert_alpha")
    _check_bool("auto_invert_alpha")
    _check_number("auto_invert_alpha_threshold", min_val=0, max_val=1)

    if "auto_tune_min" in alpha_cfg and "auto_tune_max" in alpha_cfg:
        min_val = alpha_cfg.get("auto_tune_min")
        max_val = alpha_cfg.get("auto_tune_max")
        if _is_number(min_val) and _is_number(max_val) and min_val > max_val:
            raise ValueError(f"{prefix}.auto_tune_min must be <= auto_tune_max")

    if "auto_tune_step" in alpha_cfg:
        step = alpha_cfg.get("auto_tune_step")
        if _is_number(step) and step <= 0:
            raise ValueError(f"{prefix}.auto_tune_step must be > 0")

    if "chroma_key_color" in alpha_cfg and alpha_cfg["chroma_key_color"] is not None:
        color = str(alpha_cfg["chroma_key_color"])
        if not re.match(r"^(#|0x)[0-9a-fA-F]{6}$", color):
            raise ValueError(f"{prefix}.chroma_key_color must be #RRGGBB or 0xRRGGBB")


def validate_payload(job_input_raw: Dict[str, Any], ctx: ProcessingContext) -> None:
    """Validate payload types and log warnings for unknown fields."""
    if not isinstance(job_input_raw, dict):
        raise ValueError("input must be a JSON object")

    unknown_top = [k for k in job_input_raw.keys() if k not in VALID_INPUT_KEYS]
    for key in unknown_top:
        ctx.log(f"Warning: Unknown input field '{key}' will be ignored", "WARN")

    if "video_urls" in job_input_raw and job_input_raw["video_urls"] is not None:
        if not isinstance(job_input_raw["video_urls"], list):
            raise ValueError("video_urls must be an array of strings")
        for url in job_input_raw["video_urls"]:
            if not isinstance(url, str):
                raise ValueError("video_urls must be an array of strings")

    if "clips" in job_input_raw and job_input_raw["clips"] is not None:
        if not isinstance(job_input_raw["clips"], list):
            raise ValueError("clips must be an array of clip objects")
        for idx, clip in enumerate(job_input_raw["clips"]):
            if not isinstance(clip, dict):
                raise ValueError(f"clips[{idx}] must be an object")
            unknown_clip = [k for k in clip.keys() if k not in VALID_CLIP_KEYS]
            for key in unknown_clip:
                ctx.log(f"Warning: Unknown clip field '{key}' in clips[{idx}] will be ignored", "WARN")
            if not clip.get("url") or not isinstance(clip.get("url"), str):
                raise ValueError(f"clips[{idx}].url is required and must be a string")
            clip_type = clip.get("type", "scene")
            if clip_type not in ("scene", "broll", "endcard", "introcard"):
                raise ValueError(
                    f"clips[{idx}].type must be 'scene', 'broll', 'endcard', or 'introcard', got: {clip_type}"
                )
            for key in ("start_time", "end_time"):
                if key in clip and clip[key] is not None and not _is_number(clip[key]):
                    raise ValueError(f"clips[{idx}].{key} must be a number or null")
            if "overlap_seconds" in clip and clip["overlap_seconds"] is not None:
                if not _is_number(clip["overlap_seconds"]):
                    raise ValueError(f"clips[{idx}].overlap_seconds must be a number or null")
                if clip["overlap_seconds"] < 0:
                    raise ValueError(f"clips[{idx}].overlap_seconds must be >= 0")
            if "alpha_fill" in clip and clip["alpha_fill"] is not None and not isinstance(clip["alpha_fill"], dict):
                raise ValueError(f"clips[{idx}].alpha_fill must be an object or null")
            if "alpha_fill" in clip and clip["alpha_fill"] is not None:
                _validate_alpha_fill_config(clip["alpha_fill"], f"clips[{idx}].alpha_fill")
            if "effects" in clip and clip["effects"] is not None and not isinstance(clip["effects"], dict):
                raise ValueError(f"clips[{idx}].effects must be an object or null")

    if "music_volume" in job_input_raw and job_input_raw["music_volume"] is not None:
        if not _is_number(job_input_raw["music_volume"]):
            raise ValueError("music_volume must be a number")

    if "loop_music" in job_input_raw and job_input_raw["loop_music"] is not None:
        if not isinstance(job_input_raw["loop_music"], bool):
            raise ValueError("loop_music must be a boolean")

    if "enable_interpolation" in job_input_raw and job_input_raw["enable_interpolation"] is not None:
        if not isinstance(job_input_raw["enable_interpolation"], bool):
            raise ValueError("enable_interpolation must be a boolean")

    if "subtitle_mode" in job_input_raw and job_input_raw["subtitle_mode"] is not None:
        if job_input_raw["subtitle_mode"] not in {"auto", "manual", "none"}:
            raise ValueError("subtitle_mode must be 'auto', 'manual', or 'none'")

    if "edit_preset" in job_input_raw and job_input_raw["edit_preset"] is not None:
        if job_input_raw["edit_preset"] not in {p.value for p in EditPreset}:
            raise ValueError("edit_preset is not a supported preset")

    if "style_overrides" in job_input_raw and job_input_raw["style_overrides"] is not None:
        if not isinstance(job_input_raw["style_overrides"], dict):
            raise ValueError("style_overrides must be an object")
        for key in ("broll_alpha_fill", "endcard_alpha_fill", "introcard_alpha_fill"):
            if key in job_input_raw["style_overrides"] and job_input_raw["style_overrides"][key] is not None:
                _validate_alpha_fill_config(job_input_raw["style_overrides"][key], f"style_overrides.{key}")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Execution
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    job_input: JobInput,
    ctx: ProcessingContext
) -> Tuple[str, float]:
    """
    Execute the full video processing pipeline.
    
    Args:
        job_input: Validated job input parameters
        ctx: Processing context
        
    Returns:
        Tuple of (output_path, video_duration)
    """
    work_dir = ctx.work_dir
    
    # Step 1: Download input videos (using new clips format)
    with ctx.time_block("Step 1/6: Downloading input videos"):
        if not job_input.clips:
            raise ValueError("No clips to process")
        downloaded_clips = download_videos(job_input.clips, work_dir, ctx)
        scene_count = sum(1 for c in downloaded_clips if c.get("type") == "scene")
        broll_count = sum(1 for c in downloaded_clips if c.get("type") == "broll")
        endcard_count = sum(1 for c in downloaded_clips if c.get("type") == "endcard")
        ctx.log(
            f"Downloaded {len(downloaded_clips)} clips "
            f"({scene_count} scenes, {broll_count} b-roll, {endcard_count} endcards)"
        )
    
    # Step 2: Handle music (download URL, use random, or skip)
    music_path = None
    resolved_music = job_input.get_resolved_music_path()

    with ctx.time_block("Step 2/6: Preparing background music"):
        if resolved_music == "random" or job_input.music_url == "random":
            # Already resolved by get_resolved_music_path()
            music_path = get_random_music_path()
            if music_path:
                ctx.log(f"Using random music: {os.path.basename(music_path)}")
            else:
                ctx.log("No music files found in assets/audio", "WARN")
        elif resolved_music and resolved_music.startswith(('http://', 'https://')):
            ctx.log("Downloading background music...")
            music_dir = os.path.join(work_dir, "audio")
            os.makedirs(music_dir, exist_ok=True)
            ext = os.path.splitext(resolved_music.split('?')[0])[1] or '.mp3'
            music_path = os.path.join(music_dir, f"music{ext}")
            download_file(resolved_music, music_path, ctx)
        elif resolved_music and os.path.exists(resolved_music):
            # Local file path (e.g., from random selection)
            music_path = resolved_music
            ctx.log(f"Using local music: {os.path.basename(music_path)}")
        else:
            ctx.log("No music provided, skipping")
    
    # Step 3: Download or prepare subtitles
    srt_path = None
    with ctx.time_block("Step 3/6: Preparing subtitles"):
        if job_input.subtitle_mode == SubtitleMode.MANUAL:
            ctx.log("Downloading manual subtitles...")
            subs_dir = os.path.join(work_dir, "subs")
            os.makedirs(subs_dir, exist_ok=True)
            srt_path = os.path.join(subs_dir, "subtitles.srt")
            if job_input.manual_srt_url:
                download_file(job_input.manual_srt_url, srt_path, ctx)
        elif job_input.subtitle_mode == SubtitleMode.NONE:
            ctx.log("Subtitles disabled")
        else:
            ctx.log("Auto-transcription will run during processing")
    
    # Step 4: Generate configuration files
    with ctx.time_block("Step 4/6: Generating pipeline configuration"):
        clips_config = generate_clips_config(downloaded_clips, work_dir, ctx)
        style_config = generate_style_config(job_input, work_dir, ctx)
    
    # Step 5: Run the main pipeline
    ctx.log("Step 5/6: Running video processing pipeline...")
    
    output_dir = os.path.join(work_dir, "exports")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = job_input.output_filename or f"output_{ctx.job_id}.mp4"
    output_path = os.path.join(output_dir, output_filename)
    
    # Import and run pipeline
    from ugc_pipeline.clips import process_clips
    from ugc_pipeline.audio import process_audio
    from ugc_pipeline.subtitles import generate_subtitles
    from ugc_pipeline.style import load_style
    from ugc_pipeline.export import export_video
    
    # Load style
    style = load_style(style_config)
    interp_cfg = style.get("postprocess", {}).get("frame_interpolation", {})
    ctx.log(
        "Frame interpolation config: "
        f"enabled={interp_cfg.get('enabled', False)}, "
        f"model={interp_cfg.get('model', 'rife-v4')}, "
        f"target_fps={interp_cfg.get('target_fps', 'n/a')}, "
        f"gpu_id={interp_cfg.get('gpu_id', 'n/a')}"
    )
    
    # Process clips
    with ctx.time_block("Clips processing", include_gpu=True):
        video_clip = process_clips(clips_config, style)
        ctx.log(f"Video duration: {video_clip.duration:.2f}s")
    
    # Add audio
    if music_path:
        with ctx.time_block("Audio mix"):
            ctx.log("Adding background audio...")
            video_clip = process_audio(video_clip, music_path, style)
    
    # Generate/apply subtitles
    if job_input.subtitle_mode != SubtitleMode.NONE:
        if job_input.subtitle_mode == SubtitleMode.AUTO:
            with ctx.time_block("Transcription (Whisper)", include_gpu=True):
                ctx.log("Generating subtitles with Whisper...")
                ctx.log(f"GPU snapshot (pre-whisper): {get_gpu_utilization()}")
                ctx.log(f"GPU processes (pre-whisper): {get_gpu_processes()}")
                # Auto-generate subtitles
                subs_dir = os.path.join(work_dir, "subs")
                os.makedirs(subs_dir, exist_ok=True)
                srt_path = os.path.join(subs_dir, "auto_generated.srt")
                
                try:
                    from ugc_pipeline.transcription import transcribe_audio_array
                    import numpy as np
                    
                    # Extract audio
                    audio_chunks = []
                    for chunk in video_clip.audio.iter_chunks(fps=16000, chunksize=3000):
                        audio_chunks.append(chunk)
                    
                    if audio_chunks:
                        audio_array = np.vstack(audio_chunks)
                        if len(audio_array.shape) > 1 and audio_array.shape[1] > 1:
                            audio_array = audio_array.mean(axis=1)
                        
                        transcription_config = style.get("transcription", {})
                        whisper_language = job_input.get_whisper_language()
                        ctx.log(f"Whisper language: {whisper_language} (geo: {job_input.geo or 'not specified'})")
                        ctx.log(f"Audio samples for Whisper: {audio_array.shape[0]}")
                        
                        transcribe_audio_array(
                            audio_array,
                            srt_path,
                            model_name=transcription_config.get("model", "small"),
                            language=whisper_language,
                            initial_prompt=transcription_config.get("keywords"),
                            word_level=transcription_config.get("word_level", True),
                            max_words=transcription_config.get("max_words_per_segment", 4),
                            silence_threshold=transcription_config.get("max_delay_seconds", 0.5),
                            log_func=ctx.log
                        )
                        ctx.log("Subtitles generated successfully")
                        ctx.log(f"GPU snapshot (post-whisper): {get_gpu_utilization()}")
                except Exception as e:
                    ctx.log(f"Subtitle generation failed: {e}", "WARN")
                    srt_path = None
        
        if srt_path and os.path.exists(srt_path):
            with ctx.time_block("Subtitle rendering"):
                ctx.log("Applying subtitles...")
                video_clip = generate_subtitles(video_clip, srt_path, style)
    
    # Export final video
    with ctx.time_block("Export", include_gpu=True):
        ctx.log("Exporting final video...")
        ctx.log(f"GPU snapshot (pre-export): {get_gpu_utilization()}")
        ctx.log(f"GPU processes (pre-export): {get_gpu_processes()}")
        export_video(video_clip, output_path, style, log_func=ctx.log)
    
    # Clean up MoviePy resources
    video_clip.close()
    
    # Get final video info
    duration = video_clip.duration
    file_size = os.path.getsize(output_path) / (1024 * 1024)
    ctx.log(f"Export complete: {file_size:.1f} MB, {duration:.1f}s")
    
    return output_path, duration


# ─────────────────────────────────────────────────────────────────────────────
# RunPod Handler
# ─────────────────────────────────────────────────────────────────────────────

def get_gpu_info() -> str:
    """Get GPU information for diagnostics."""
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            memory_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            return f"CUDA: {device_name} ({memory_total:.1f}GB)"
        else:
            return "CUDA: Not available"
    except Exception as e:
        return f"CUDA check failed: {e}"


def get_gpu_utilization() -> str:
    """Get GPU utilization snapshot via nvidia-smi (best-effort)."""
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout.strip().splitlines()
        if output:
            return f"GPU util={output[0]}"
        return "GPU util=unavailable"
    except Exception as e:
        return f"GPU util check failed: {e}"


def get_gpu_memory_info() -> Optional[Tuple[int, int]]:
    """Return (used_mb, total_mb) from nvidia-smi, best-effort."""
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout.strip().splitlines()
        if output:
            used_str, total_str = [v.strip() for v in output[0].split(",")]
            return int(used_str), int(total_str)
        return None
    except Exception:
        return None


def get_gpu_processes() -> str:
    """List GPU compute processes via nvidia-smi (best-effort)."""
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout.strip().splitlines()
        if not output or (len(output) == 1 and not output[0].strip()):
            return "none"
        return "; ".join(line.strip() for line in output)
    except Exception as e:
        return f"GPU process check failed: {e}"


def get_ffmpeg_encoder_info() -> str:
    """Check FFmpeg encoder availability (best-effort)."""
    try:
        import subprocess
        ffmpeg_cmd = "ffmpeg"
        try:
            import imageio_ffmpeg
            ffmpeg_cmd = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        result = subprocess.run(
            [ffmpeg_cmd, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        encoders = result.stdout or ""
        has_nvenc = "h264_nvenc" in encoders
        return f"FFmpeg: {ffmpeg_cmd} | h264_nvenc={'YES' if has_nvenc else 'NO'}"
    except Exception as e:
        return f"FFmpeg encoder check failed: {e}"


def configure_cache_environment(ctx: ProcessingContext) -> None:
    """Configure cache directories, preferring the RunPod network volume when available."""
    try:
        runpod_volume = "/runpod-volume"
        fallback_volume = "/tmp/runpod-volume"
        base_cache = runpod_volume if os.path.isdir(runpod_volume) else fallback_volume

        if base_cache == fallback_volume and not os.path.isdir(runpod_volume):
            os.makedirs(base_cache, exist_ok=True)
            ctx.log(f"/runpod-volume not found; using {base_cache} for caches", "WARN")

        whisper_cache = os.environ.get("WHISPER_CACHE_DIR") or os.path.join(base_cache, "whisper_models")
        xdg_cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(base_cache, "cache")

        os.environ["WHISPER_CACHE_DIR"] = whisper_cache
        os.environ["XDG_CACHE_HOME"] = xdg_cache

        os.makedirs(whisper_cache, exist_ok=True)
        os.makedirs(xdg_cache, exist_ok=True)

        ctx.log(f"Cache dirs: WHISPER_CACHE_DIR={whisper_cache} | XDG_CACHE_HOME={xdg_cache}")
    except Exception as e:
        ctx.log(f"Cache env setup failed: {e}", "WARN")


def configure_gpu_environment(ctx: ProcessingContext) -> None:
    """Configure GPU-related environment variables (best-effort)."""
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except Exception as e:
        ctx.log(f"GPU env setup: Torch check failed ({e})", "WARN")
        return

    if cuda_available:
        requested_whisper = os.environ.get("WHISPER_DEVICE")
        if not requested_whisper:
            os.environ["WHISPER_DEVICE"] = "auto"
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
        os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

        mem_info = get_gpu_memory_info()
        if mem_info:
            used_mb, total_mb = mem_info
            free_mb = total_mb - used_mb
            ctx.log(f"GPU memory: used={used_mb}MB free={free_mb}MB total={total_mb}MB")
            if (not requested_whisper or requested_whisper.lower() in {"auto", "cpu"}) and free_mb < 3000:
                os.environ["WHISPER_DEVICE"] = "cpu"
                ctx.log("Low free GPU memory. Forcing WHISPER_DEVICE=cpu", "WARN")
            elif requested_whisper and requested_whisper.lower() == "cuda" and free_mb < 3000:
                ctx.log("Low free GPU memory with WHISPER_DEVICE=cuda. OOM risk is high.", "WARN")
        ctx.log(
            "GPU env configured: "
            f"WHISPER_DEVICE={os.environ.get('WHISPER_DEVICE')} | "
            f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')} | "
            f"TF_FORCE_GPU_ALLOW_GROWTH={os.environ.get('TF_FORCE_GPU_ALLOW_GROWTH')}"
        )
    else:
        ctx.log("CUDA not available. GPU-only steps may fall back to CPU.", "WARN")


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod serverless handler function.
    
    Args:
        job: RunPod job dictionary with 'id' and 'input' keys
        
    Returns:
        Result dictionary with output URL or error
    """
    job_id = job.get('id', 'unknown')
    job_input_raw = job.get('input', {})
    
    # Create temp working directory
    work_dir = tempfile.mkdtemp(prefix=f"ugc_job_{job_id}_")
    ctx = ProcessingContext(job_id=job_id, work_dir=work_dir)
    
    try:
        ctx.log(f"Starting job {job_id}")
        ctx.log(f"Work directory: {work_dir}")
        configure_cache_environment(ctx)
        ctx.log("Configuring GPU environment...")
        configure_gpu_environment(ctx)
        ctx.log(f"GPU: {get_gpu_info()}")
        ctx.log(f"GPU snapshot (startup): {get_gpu_utilization()}")
        ctx.log(f"GPU processes (startup): {get_gpu_processes()}")
        ctx.log(get_ffmpeg_encoder_info())
        
        # Validate and parse input
        ctx.log("Validating input parameters...")
        
        # Validate payload and warn on unknown fields
        validate_payload(job_input_raw, ctx)

        # Parse clips from new format or legacy video_urls
        parsed_clips = None
        if 'clips' in job_input_raw and job_input_raw['clips']:
            parsed_clips = []
            for clip_data in job_input_raw['clips']:
                if isinstance(clip_data, dict):
                    parsed_clips.append(ClipInput(
                        url=clip_data.get('url', ''),
                        clip_type=clip_data.get('type', 'scene'),
                        start_time=clip_data.get('start_time'),
                        end_time=clip_data.get('end_time'),
                        alpha_fill=clip_data.get('alpha_fill'),
                        overlap_seconds=clip_data.get('overlap_seconds'),
                        effects=clip_data.get('effects')
                    ))
                else:
                    raise ValueError(f"Invalid clip format: {clip_data}")
            ctx.log(f"Parsed {len(parsed_clips)} clips from new format")
        
        job_input = JobInput(
            video_urls=job_input_raw.get('video_urls'),
            clips=parsed_clips,
            geo=job_input_raw.get('geo'),
            edit_preset=job_input_raw.get('edit_preset', 'standard_vertical'),
            music_url=job_input_raw.get('music_url'),
            music_volume=job_input_raw.get('music_volume', 0.3),
            loop_music=job_input_raw.get('loop_music', True),
            subtitle_mode=job_input_raw.get('subtitle_mode', 'auto'),
            manual_srt_url=job_input_raw.get('manual_srt_url'),
            enable_interpolation=job_input_raw.get('enable_interpolation', True),
            rife_model=job_input_raw.get('rife_model', 'rife-v4'),
            style_overrides=job_input_raw.get('style_overrides'),
            output_filename=job_input_raw.get('output_filename'),
            output_folder=job_input_raw.get('output_folder')
        )
        ctx.log(f"Input validation passed (geo: {job_input.geo or 'not specified'})")
        
        # Run pipeline
        output_path, duration = run_pipeline(job_input, ctx)
        
        # Upload to S3
        ctx.log("Step 6/6: Uploading to S3...")
        bucket = os.environ.get('S3_BUCKET', 'ugc-pipeline-outputs')
        
        # Use custom output_folder if provided, otherwise default to outputs/{job_id}/
        if job_input.output_folder:
            s3_key = f"{job_input.output_folder.strip('/')}/{os.path.basename(output_path)}"
        else:
            s3_key = f"outputs/{job_id}/{os.path.basename(output_path)}"
        
        output_url = upload_to_s3(output_path, bucket, s3_key)
        ctx.log(f"Upload complete: {output_url}")
        
        # Success response
        total_time = ctx.elapsed()
        ctx.log(f"Job completed successfully in {total_time:.1f}s")
        
        return {
            "output_url": output_url,
            "message": f"Video processed successfully in {total_time:.1f}s",
            "duration_seconds": duration,
            "file_size_mb": os.path.getsize(output_path) / (1024 * 1024),
            "logs": ctx.logs
        }
        
    except ValueError as e:
        # Input validation error
        ctx.log(f"Validation error: {e}", "ERROR")
        return {
            "error": str(e),
            "error_type": "ValidationError",
            "logs": ctx.logs
        }
        
    except (RIFENotAvailableError, VulkanNotAvailableError) as e:
        # Infrastructure error
        ctx.log(f"Infrastructure error: {e}", "ERROR")
        return {
            "error": str(e),
            "error_type": "InfrastructureError", 
            "logs": ctx.logs
        }
        
    except requests.RequestException as e:
        # Download error
        ctx.log(f"Download error: {e}", "ERROR")
        return {
            "error": f"Failed to download resource: {e}",
            "error_type": "DownloadError",
            "logs": ctx.logs
        }
        
    except ClientError as e:
        # S3 upload error
        ctx.log(f"S3 error: {e}", "ERROR")
        return {
            "error": f"Failed to upload to S3: {e}",
            "error_type": "S3Error",
            "logs": ctx.logs
        }
        
    except Exception as e:
        # Unexpected error
        ctx.log(f"Unexpected error: {e}", "ERROR")
        ctx.log(traceback.format_exc(), "ERROR")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "logs": ctx.logs
        }
        
    finally:
        # Cleanup work directory
        try:
            shutil.rmtree(work_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup {work_dir}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Validate environment on startup
    print("=" * 60)
    print("  UGC Pipeline - RunPod Serverless Handler")
    print("=" * 60)
    
    try:
        validate_environment()
        print("\n✅ Environment validation passed\n")
    except Exception as e:
        print(f"\n❌ Environment validation failed: {e}\n")
        # Don't exit - allow handler to start but jobs will fail with clear error
    
    # Start RunPod serverless handler
    runpod.serverless.start({"handler": handler})

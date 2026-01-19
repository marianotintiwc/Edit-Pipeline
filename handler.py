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
        "video_urls": [str, str, str, str],    # Exactly 4 video URLs
        "edit_preset": str,                     # "standard_vertical", "no_interpolation", "no_subtitles"
        "music_url": str | None,               # Optional background music URL
        "music_volume": float,                 # 0.0 - 1.0 (default: 0.3)
        "loop_music": bool,                    # Loop music to video length (default: true)
        "subtitle_mode": str,                  # "auto" | "manual" | "none"
        "manual_srt_url": str | None,          # SRT URL if subtitle_mode="manual"
        "enable_interpolation": bool,          # Enable RIFE (default: true)
        "rife_model": str,                     # "rife-v4" | "rife-v4.6" (default: "rife-v4")
        "style_overrides": dict | None         # Partial style.json overrides
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
from typing import Dict, Any, List, Optional, Tuple
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
class JobInput:
    """Validated job input parameters."""
    video_urls: List[str]
    edit_preset: EditPreset = EditPreset.STANDARD_VERTICAL
    music_url: Optional[str] = None
    music_volume: float = 0.3
    loop_music: bool = True
    subtitle_mode: SubtitleMode = SubtitleMode.AUTO
    manual_srt_url: Optional[str] = None
    enable_interpolation: bool = True
    rife_model: str = "rife-v4"
    style_overrides: Optional[Dict[str, Any]] = None
    output_filename: Optional[str] = None
    
    def __post_init__(self):
        """Validate inputs after initialization."""
        if len(self.video_urls) != 4:
            raise ValueError(f"Exactly 4 video URLs required, got {len(self.video_urls)}")
        
        if not all(url.startswith(('http://', 'https://')) for url in self.video_urls):
            raise ValueError("All video URLs must be valid HTTP/HTTPS URLs")
        
        if self.music_volume < 0.0 or self.music_volume > 1.0:
            raise ValueError(f"music_volume must be 0.0-1.0, got {self.music_volume}")
        
        if self.subtitle_mode == SubtitleMode.MANUAL and not self.manual_srt_url:
            raise ValueError("manual_srt_url required when subtitle_mode='manual'")
        
        # Convert string enums if needed
        if isinstance(self.edit_preset, str):
            self.edit_preset = EditPreset(self.edit_preset)
        if isinstance(self.subtitle_mode, str):
            self.subtitle_mode = SubtitleMode(self.subtitle_mode)


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
            'ContentType': content_type,
            'ACL': 'public-read'
        }
    )
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    if region == 'us-east-1':
        url = f"https://{bucket}.s3.amazonaws.com/{key}"
    else:
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    
    return url


# ─────────────────────────────────────────────────────────────────────────────
# File Downloads
# ─────────────────────────────────────────────────────────────────────────────

def download_file(url: str, dest_path: str, ctx: ProcessingContext) -> str:
    """
    Download a file from URL to local path.
    
    Args:
        url: Source URL
        dest_path: Destination file path
        ctx: Processing context for logging
        
    Returns:
        Path to downloaded file
    """
    ctx.log(f"Downloading: {url[:80]}...")
    
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
    urls: List[str],
    work_dir: str,
    ctx: ProcessingContext
) -> List[str]:
    """Download all input videos to work directory."""
    video_dir = os.path.join(work_dir, "videos")
    os.makedirs(video_dir, exist_ok=True)
    
    paths = []
    for i, url in enumerate(urls):
        # Extract extension from URL or default to .mp4
        ext = os.path.splitext(url.split('?')[0])[1] or '.mp4'
        dest = os.path.join(video_dir, f"input_{i+1}{ext}")
        download_file(url, dest, ctx)
        paths.append(dest)
    
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Configuration Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_clips_config(video_paths: List[str], work_dir: str) -> str:
    """
    Generate clips.json configuration for the pipeline.
    
    Args:
        video_paths: List of local video file paths
        work_dir: Working directory
        
    Returns:
        Path to generated clips.json
    """
    clips = [{"path": path, "start": None, "end": None} for path in video_paths]
    
    config = {"clips": clips}
    
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
        "font": "Arial-Bold",
        "fontsize": 70,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 0,
        "position": "center_middle",
        "margin_bottom": 200,
        "highlight": {
            "enabled": True,
            "color": "yellow",
            "fontsize_multiplier": 1.1,
            "roundness": 1.5
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
    
    # Step 1: Download input videos
    ctx.log("Step 1/6: Downloading input videos...")
    video_paths = download_videos(job_input.video_urls, work_dir, ctx)
    ctx.log(f"Downloaded {len(video_paths)} videos in {ctx.elapsed():.1f}s")
    
    # Step 2: Download music (if provided)
    music_path = None
    if job_input.music_url:
        ctx.log("Step 2/6: Downloading background music...")
        music_dir = os.path.join(work_dir, "audio")
        os.makedirs(music_dir, exist_ok=True)
        ext = os.path.splitext(job_input.music_url.split('?')[0])[1] or '.mp3'
        music_path = os.path.join(music_dir, f"music{ext}")
        download_file(job_input.music_url, music_path, ctx)
    else:
        ctx.log("Step 2/6: No music URL provided, skipping")
    
    # Step 3: Download or prepare subtitles
    srt_path = None
    if job_input.subtitle_mode == SubtitleMode.MANUAL:
        ctx.log("Step 3/6: Downloading manual subtitles...")
        subs_dir = os.path.join(work_dir, "subs")
        os.makedirs(subs_dir, exist_ok=True)
        srt_path = os.path.join(subs_dir, "subtitles.srt")
        download_file(job_input.manual_srt_url, srt_path, ctx)
    elif job_input.subtitle_mode == SubtitleMode.NONE:
        ctx.log("Step 3/6: Subtitles disabled")
    else:
        ctx.log("Step 3/6: Auto-transcription will run during processing")
    
    # Step 4: Generate configuration files
    ctx.log("Step 4/6: Generating pipeline configuration...")
    clips_config = generate_clips_config(video_paths, work_dir)
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
    
    # Process clips
    ctx.log("Processing video clips...")
    video_clip = process_clips(clips_config, style)
    ctx.log(f"Video duration: {video_clip.duration:.2f}s")
    
    # Add audio
    if music_path:
        ctx.log("Adding background audio...")
        video_clip = process_audio(video_clip, music_path, style)
    
    # Generate/apply subtitles
    if job_input.subtitle_mode != SubtitleMode.NONE:
        if job_input.subtitle_mode == SubtitleMode.AUTO:
            ctx.log("Generating subtitles with Whisper...")
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
                    transcribe_audio_array(
                        audio_array,
                        srt_path,
                        model_name=transcription_config.get("model", "small"),
                        language="es",
                        initial_prompt=transcription_config.get("keywords"),
                        word_level=transcription_config.get("word_level", True),
                        max_words=transcription_config.get("max_words_per_segment", 4),
                        silence_threshold=transcription_config.get("max_delay_seconds", 0.5)
                    )
                    ctx.log("Subtitles generated successfully")
            except Exception as e:
                ctx.log(f"Subtitle generation failed: {e}", "WARN")
                srt_path = None
        
        if srt_path and os.path.exists(srt_path):
            ctx.log("Applying subtitles...")
            video_clip = generate_subtitles(video_clip, srt_path, style)
    
    # Export final video
    ctx.log("Exporting final video...")
    export_video(video_clip, output_path, style)
    
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
        
        # Validate and parse input
        ctx.log("Validating input parameters...")
        job_input = JobInput(
            video_urls=job_input_raw.get('video_urls', []),
            edit_preset=job_input_raw.get('edit_preset', 'standard_vertical'),
            music_url=job_input_raw.get('music_url'),
            music_volume=job_input_raw.get('music_volume', 0.3),
            loop_music=job_input_raw.get('loop_music', True),
            subtitle_mode=job_input_raw.get('subtitle_mode', 'auto'),
            manual_srt_url=job_input_raw.get('manual_srt_url'),
            enable_interpolation=job_input_raw.get('enable_interpolation', True),
            rife_model=job_input_raw.get('rife_model', 'rife-v4'),
            style_overrides=job_input_raw.get('style_overrides'),
            output_filename=job_input_raw.get('output_filename')
        )
        ctx.log("Input validation passed")
        
        # Run pipeline
        output_path, duration = run_pipeline(job_input, ctx)
        
        # Upload to S3
        ctx.log("Step 6/6: Uploading to S3...")
        bucket = os.environ.get('S3_BUCKET', 'ugc-pipeline-outputs')
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

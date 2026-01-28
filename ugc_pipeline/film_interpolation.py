"""
FILM Frame Interpolation Module
Google's Frame Interpolation for Large Motion (FILM) implementation.

Integrates TensorFlow Hub's FILM model for smooth frame interpolation (e.g., 30fps → 60fps)
while strictly preserving original audio lip-sync.

Reference: https://github.com/google-research/frame-interpolation
TF Hub: https://www.tensorflow.org/hub/tutorials/tf_hub_film_example

Usage:
    # As module
    from ugc_pipeline.film_interpolation import interpolate_video
    interpolate_video("input.mp4", "output.mp4", target_fps=60)
    
    # As CLI
    python film_interpolation.py --input video.mp4 --target_fps 60 --output interpolated.mp4
"""

import os
import sys
import time
import logging
import tempfile
import subprocess
import shutil
from typing import Optional, Tuple, List, Callable
from pathlib import Path

import numpy as np

# Lazy imports for heavy dependencies
_tf = None
_hub = None
_cv2 = None

def _lazy_import_tensorflow():
    """Lazy import TensorFlow to avoid startup overhead."""
    global _tf, _hub
    if _tf is None:
        import tensorflow as tf
        import tensorflow_hub as hub
        _tf = tf
        _hub = hub
        # Suppress TF warnings
        tf.get_logger().setLevel('ERROR')
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    return _tf, _hub

def _lazy_import_cv2():
    """Lazy import OpenCV."""
    global _cv2
    if _cv2 is None:
        import cv2
        _cv2 = cv2
    return _cv2

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# FILM model from TensorFlow Hub (Style variant for better quality)
FILM_MODEL_URL = "https://tfhub.dev/google/film/1"

# Default configuration
DEFAULT_CONFIG = {
    "enabled": False,
    "target_fps": 60,               # Target output FPS
    "times_to_interpolate": 1,      # Recursive interpolation depth (1=2x, 2=4x, 3=8x)
    "batch_size": 1,                # Frames to process at once (GPU memory dependent)
    "chunk_size": 30,               # Process in chunks to reduce memory usage
    "overlap_frames": 2,            # Overlap between chunks to avoid seam artifacts
    "preserve_audio": True,         # CRITICAL: Always preserve original audio
    "output_quality": {
        "crf": 18,                  # High quality (0-51, lower=better)
        "preset": "medium",         # Encoding preset (medium for balance)
        "pix_fmt": "yuv420p"
    },
    "gpu_memory_limit": None,       # Limit GPU memory (GB), None = auto
    "create_comparison": False      # Create side-by-side comparison video
}


# ─────────────────────────────────────────────────────────────────────────────
# FILM Model Wrapper
# ─────────────────────────────────────────────────────────────────────────────

class FILMInterpolator:
    """
    Wrapper for Google's FILM model from TensorFlow Hub.
    Handles model loading, frame interpolation, and memory management.
    """
    
    def __init__(self, gpu_memory_limit: Optional[float] = None):
        """
        Initialize FILM interpolator.
        
        Args:
            gpu_memory_limit: Max GPU memory in GB (None = auto)
        """
        self.tf, self.hub = _lazy_import_tensorflow()
        self.model = None
        self._setup_gpu(gpu_memory_limit)
    
    def _setup_gpu(self, memory_limit: Optional[float]):
        """Configure GPU memory growth to avoid OOM errors."""
        gpus = self.tf.config.list_physical_devices('GPU')
        if gpus:
            try:
                for gpu in gpus:
                    if memory_limit:
                        # Limit memory to specified amount
                        self.tf.config.set_logical_device_configuration(
                            gpu,
                            [self.tf.config.LogicalDeviceConfiguration(
                                memory_limit=int(memory_limit * 1024)
                            )]
                        )
                    else:
                        # Allow memory growth
                        self.tf.config.experimental.set_memory_growth(gpu, True)
                logical = self.tf.config.list_logical_devices('GPU')
                names = ", ".join([d.name for d in logical]) if logical else "unknown"
                logging.info(f"FILM GPU configured: {len(gpus)} device(s) | logical: {names}")
            except RuntimeError as e:
                logging.warning(f"GPU config error: {e}")
    
    def load_model(self):
        """Load FILM model from TensorFlow Hub (downloads on first use)."""
        if self.model is None:
            logging.info("Loading FILM model from TensorFlow Hub...")
            start = time.time()
            self.model = self.hub.load(FILM_MODEL_URL)
            logging.info(f"Model loaded in {time.time() - start:.1f}s")
        return self.model
    
    def interpolate_pair(self, frame1: np.ndarray, frame2: np.ndarray, 
                         t: float = 0.5) -> np.ndarray:
        """
        Interpolate a single frame between two input frames.
        
        Args:
            frame1: First frame (H, W, 3), float32 [0, 1]
            frame2: Second frame (H, W, 3), float32 [0, 1]
            t: Interpolation time (0.0 = frame1, 1.0 = frame2, 0.5 = middle)
            
        Returns:
            Interpolated frame (H, W, 3), float32 [0, 1]
        """
        model = self.load_model()
        
        # Prepare inputs (FILM expects batch dimension)
        # Shape: (batch, H, W, 3) for images
        # Shape: (batch, 1) for time - CRITICAL: must be 2D!
        img1 = self.tf.constant(frame1[np.newaxis, ...], dtype=self.tf.float32)
        img2 = self.tf.constant(frame2[np.newaxis, ...], dtype=self.tf.float32)
        time_val = self.tf.constant([[t]], dtype=self.tf.float32)  # Shape (1, 1) not (1,)
        
        # Run interpolation
        result = model({
            'time': time_val,
            'x0': img1,
            'x1': img2
        })
        
        return result['image'][0].numpy()
    
    def interpolate_recursive(self, frame1: np.ndarray, frame2: np.ndarray,
                              times_to_interpolate: int = 1) -> List[np.ndarray]:
        """
        Recursively interpolate between two frames.
        
        Args:
            frame1: First frame
            frame2: Second frame
            times_to_interpolate: Recursion depth (1=1 mid frame, 2=3 frames, 3=7 frames)
            
        Returns:
            List of interpolated frames (excluding input frames)
        """
        if times_to_interpolate <= 0:
            return []
        
        # Get middle frame
        mid_frame = self.interpolate_pair(frame1, frame2, 0.5)
        
        if times_to_interpolate == 1:
            return [mid_frame]
        
        # Recursively interpolate left and right halves
        left_frames = self.interpolate_recursive(frame1, mid_frame, times_to_interpolate - 1)
        right_frames = self.interpolate_recursive(mid_frame, frame2, times_to_interpolate - 1)
        
        return left_frames + [mid_frame] + right_frames
    
    def cleanup(self):
        """Release GPU memory."""
        if self.model is not None:
            del self.model
            self.model = None
            self.tf.keras.backend.clear_session()


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg Utilities
# ─────────────────────────────────────────────────────────────────────────────

def get_ffmpeg_path() -> str:
    """Get FFmpeg executable path."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    
    raise RuntimeError("FFmpeg not found. Install imageio-ffmpeg or add ffmpeg to PATH.")


def get_video_info(video_path: str) -> dict:
    """
    Get video metadata using FFmpeg (no ffprobe needed).
    
    Returns:
        dict with keys: width, height, fps, duration, frame_count, has_audio
    """
    ffmpeg = get_ffmpeg_path()
    
    info = {
        "width": 0,
        "height": 0,
        "fps": 30.0,
        "duration": 0.0,
        "frame_count": 0,
        "has_audio": False
    }
    
    # Use ffmpeg to get video info (works without ffprobe)
    cmd = [
        ffmpeg, "-i", video_path,
        "-hide_banner"
    ]
    
    # FFmpeg outputs info to stderr
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr
    
    import re
    
    # Parse duration: "Duration: 00:00:17.48"
    duration_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', stderr)
    if duration_match:
        h, m, s = duration_match.groups()
        info["duration"] = int(h) * 3600 + int(m) * 60 + float(s)
    
    # Parse video stream resolution: look for "1074x1928" pattern after "Video:"
    # Format: "Stream #0:0: Video: h264 ..., 1074x1928, ..."
    res_match = re.search(r'Video:.*?,\s*(\d+)x(\d+)', stderr)
    if res_match:
        info["width"] = int(res_match.group(1))
        info["height"] = int(res_match.group(2))
    
    # Parse fps: "30 fps" or "29.97 fps" or "30 tbr"
    fps_match = re.search(r',\s*(\d+(?:\.\d+)?)\s*fps', stderr)
    if fps_match:
        info["fps"] = float(fps_match.group(1))
    else:
        # Try tbr as fallback
        tbr_match = re.search(r',\s*(\d+(?:\.\d+)?)\s*tbr', stderr)
        if tbr_match:
            info["fps"] = float(tbr_match.group(1))
    
    # Check for audio stream
    if re.search(r'Stream.*Audio:', stderr):
        info["has_audio"] = True
    
    # Calculate frame count
    if info["duration"] > 0 and info["fps"] > 0:
        info["frame_count"] = int(info["duration"] * info["fps"])
    
    return info


def get_video_info_detailed(video_path: str) -> dict:
    """
    Get video metadata using FFprobe if available, fallback to FFmpeg.
    
    Returns:
        dict with keys: width, height, fps, duration, frame_count, has_audio
    """
    # Try ffprobe first for more accurate info
    try:
        ffprobe = None
        
        # Check common locations
        try:
            import imageio_ffmpeg
            ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
            candidates = [
                os.path.join(ffmpeg_dir, "ffprobe.exe"),
                os.path.join(ffmpeg_dir, "ffprobe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    ffprobe = c
                    break
        except ImportError:
            pass
        
        if not ffprobe:
            ffprobe = shutil.which("ffprobe")
        
        if ffprobe:
            cmd = [
                ffprobe, "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                info = {
                    "width": 0,
                    "height": 0,
                    "fps": 30.0,
                    "duration": 0.0,
                    "frame_count": 0,
                    "has_audio": False
                }
                
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        info["width"] = int(stream.get("width", 0))
                        info["height"] = int(stream.get("height", 0))
                        
                        fps_str = stream.get("r_frame_rate", "30/1")
                        if "/" in fps_str:
                            num, den = map(float, fps_str.split("/"))
                            info["fps"] = num / den if den else 30.0
                        else:
                            info["fps"] = float(fps_str)
                        
                        info["frame_count"] = int(stream.get("nb_frames", 0))
                            
                    elif stream.get("codec_type") == "audio":
                        info["has_audio"] = True
                
                info["duration"] = float(data.get("format", {}).get("duration", 0))
                if not info["frame_count"]:
                    info["frame_count"] = int(info["duration"] * info["fps"])
                
                return info
    except Exception:
        pass
    
    # Fallback to ffmpeg-only method
    return get_video_info(video_path)
    info["duration"] = float(data.get("format", {}).get("duration", 0))
    if not info["frame_count"]:
        info["frame_count"] = int(info["duration"] * info["fps"])
    
    return info


def extract_frames(video_path: str, output_dir: str, 
                   progress_callback: Optional[Callable] = None) -> int:
    """
    Extract all frames from video as PNG files.
    
    Args:
        video_path: Input video path
        output_dir: Directory to save frames
        progress_callback: Optional callback(current, total)
        
    Returns:
        Number of frames extracted
    """
    ffmpeg = get_ffmpeg_path()
    info = get_video_info(video_path)
    
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        ffmpeg, "-y", "-i", video_path,
        "-vsync", "0",  # Preserve all frames
        "-q:v", "2",    # High quality PNG
        os.path.join(output_dir, "%08d.png")
    ]
    
    process = subprocess.Popen(
        cmd, stderr=subprocess.PIPE, universal_newlines=True
    )
    
    frame_count = 0
    for line in process.stderr:
        if "frame=" in line:
            try:
                frame_count = int(line.split("frame=")[1].split()[0])
                if progress_callback:
                    progress_callback(frame_count, info["frame_count"])
            except (IndexError, ValueError):
                pass
    
    process.wait()
    
    # Count actual extracted frames
    frames = [f for f in os.listdir(output_dir) if f.endswith(".png")]
    return len(frames)


def extract_audio(video_path: str, audio_path: str) -> bool:
    """
    Extract audio track from video without any processing.
    
    CRITICAL: This preserves the exact original audio for lip-sync.
    """
    ffmpeg = get_ffmpeg_path()
    
    cmd = [
        ffmpeg, "-y", "-i", video_path,
        "-vn",           # No video
        "-acodec", "copy",  # Copy audio stream exactly
        audio_path
    ]
    
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and os.path.exists(audio_path)


def assemble_video(frames_dir: str, output_path: str, fps: float,
                   audio_path: Optional[str] = None,
                   config: Optional[dict] = None,
                   progress_callback: Optional[Callable] = None) -> bool:
    """
    Assemble frames into video and mux with original audio.
    
    Args:
        frames_dir: Directory containing frame PNGs
        output_path: Output video path
        fps: Target frame rate
        audio_path: Original audio file to mux (preserves lip-sync)
        config: Output quality settings
        progress_callback: Optional callback(current, total)
        
    Returns:
        True if successful
    """
    ffmpeg = get_ffmpeg_path()
    config = config or DEFAULT_CONFIG.get("output_quality", {})
    
    # Count frames
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    total_frames = len(frames)
    
    # Check if NVENC is available for GPU encoding (A100/RTX)
    use_nvenc = False
    try:
        result = subprocess.run(
            [ffmpeg, '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=10
        )
        if 'h264_nvenc' in result.stdout:
            use_nvenc = True
    except Exception:
        pass
    
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "%08d.png"),
    ]
    
    # Add original audio (CRITICAL for lip-sync)
    if audio_path and os.path.exists(audio_path):
        cmd.extend(["-i", audio_path])
    
    if use_nvenc:
        # GPU encoding with NVENC (A100/RTX) - much faster
        encoder_name = "h264_nvenc"
        preset_name = "p4"
        quality_mode = "cq"
        quality_value = str(config.get("crf", 18))
        logging.info(f"FILM encode: encoder={encoder_name} preset={preset_name} {quality_mode}={quality_value}")
        cmd.extend([
            "-c:v", encoder_name,
            "-preset", preset_name,  # NVENC preset (p1=fastest, p7=slowest, p4=balanced)
            "-cq", quality_value,  # Constant quality mode
            "-pix_fmt", config.get("pix_fmt", "yuv420p"),
            "-movflags", "+faststart",
        ])
    else:
        # CPU encoding fallback
        encoder_name = "libx264"
        preset_name = config.get("preset", "medium")
        quality_mode = "crf"
        quality_value = str(config.get("crf", 18))
        logging.info(f"FILM encode: encoder={encoder_name} preset={preset_name} {quality_mode}={quality_value}")
        cmd.extend([
            "-c:v", encoder_name,
            "-crf", quality_value,
            "-preset", preset_name,
            "-pix_fmt", config.get("pix_fmt", "yuv420p"),
            "-movflags", "+faststart",
        ])
    
    # Audio mapping
    if audio_path and os.path.exists(audio_path):
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-map", "0:v", "-map", "1:a"])
    
    cmd.append(output_path)
    
    process = subprocess.Popen(
        cmd, stderr=subprocess.PIPE, universal_newlines=True
    )
    
    for line in process.stderr:
        if "frame=" in line:
            try:
                current = int(line.split("frame=")[1].split()[0])
                if progress_callback:
                    progress_callback(current, total_frames)
            except (IndexError, ValueError):
                pass
    
    process.wait()
    return process.returncode == 0


# ─────────────────────────────────────────────────────────────────────────────
# Main Interpolation Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def interpolate_video(
    input_path: str,
    output_path: str,
    target_fps: Optional[float] = None,
    times_to_interpolate: Optional[int] = None,
    config: Optional[dict] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    verbose: bool = True
) -> bool:
    """
    Main entry point: Interpolate video to higher FPS while preserving audio.
    
    Args:
        input_path: Input video file (MP4/MOV)
        output_path: Output video path
        target_fps: Target FPS (e.g., 60). If None, uses 2x source FPS.
        times_to_interpolate: Recursion depth (auto-calculated from target_fps if None)
        config: Full configuration dict (overrides defaults)
        progress_callback: Callback(stage, current, total) for progress updates
        verbose: Print progress to console
        
    Returns:
        True if successful
    """
    cv2 = _lazy_import_cv2()
    
    # Merge config with defaults
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    
    def log(msg):
        if verbose:
            print(f"  [FILM] {msg}")
        logging.info(f"[FILM] {msg}")
    
    def progress(stage: str, current: int, total: int):
        if progress_callback:
            progress_callback(stage, current, total)
        if verbose and total > 0:
            pct = (current / total) * 100
            print(f"\r  [FILM] {stage}: {current}/{total} ({pct:.1f}%)", end="", flush=True)
    
    start_time = time.time()

    # ─────────────────────────────────────────────────────────────
    # Step 0: Get video info and calculate interpolation params
    # ─────────────────────────────────────────────────────────────
    log("Analyzing input video...")
    info = get_video_info(input_path)
    source_fps = info["fps"]
    duration = info["duration"]
    has_audio = info["has_audio"]
    
    log(f"  Source: {info['width']}x{info['height']} @ {source_fps:.2f}fps, {duration:.2f}s")
    
    # Calculate target FPS and interpolation depth
    if target_fps is None:
        target_fps = cfg.get("target_fps", source_fps * 2)
    
    fps_multiplier = target_fps / source_fps
    
    if times_to_interpolate is None:
        # Calculate: 2^n = multiplier → n = log2(multiplier)
        import math
        times_to_interpolate = max(1, int(math.ceil(math.log2(fps_multiplier))))
    
    actual_multiplier = 2 ** times_to_interpolate
    actual_target_fps = source_fps * actual_multiplier
    
    log(f"  Target: {actual_target_fps:.2f}fps (2^{times_to_interpolate} = {actual_multiplier}x)")
    
    # ─────────────────────────────────────────────────────────────
    # Step 1: Extract frames and audio
    # ─────────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory(prefix="film_") as temp_dir:
        frames_in_dir = os.path.join(temp_dir, "frames_in")
        frames_out_dir = os.path.join(temp_dir, "frames_out")
        audio_path = os.path.join(temp_dir, "audio.aac")
        
        os.makedirs(frames_in_dir)
        os.makedirs(frames_out_dir)
        
        log("Extracting frames...")
        frame_count = extract_frames(
            input_path, frames_in_dir,
            lambda c, t: progress("Extracting", c, t)
        )
        if verbose:
            print()  # Newline after progress
        log(f"  Extracted {frame_count} frames")
        
        # Extract audio (CRITICAL for lip-sync)
        if has_audio and cfg.get("preserve_audio", True):
            log("Extracting original audio (preserving lip-sync)...")
            if not extract_audio(input_path, audio_path):
                log("  Warning: Audio extraction failed")
                audio_path = None
        else:
            audio_path = None
        
        # ─────────────────────────────────────────────────────────
        # Step 2: Load FILM model
        # ─────────────────────────────────────────────────────────
        log("Loading FILM model...")
        interpolator = FILMInterpolator(cfg.get("gpu_memory_limit"))
        interpolator.load_model()
        try:
            gpu_list = interpolator.tf.config.list_physical_devices('GPU')
            log(f"  FILM GPU devices: {len(gpu_list)}")
        except Exception:
            pass
        
        # ─────────────────────────────────────────────────────────
        # Step 3: Interpolate frames
        # ─────────────────────────────────────────────────────────
        log(f"Interpolating frames (depth={times_to_interpolate})...")
        
        frame_files = sorted([
            f for f in os.listdir(frames_in_dir) if f.endswith(".png")
        ])
        
        output_frame_idx = 1
        total_pairs = len(frame_files) - 1
        
        try:
            from tqdm import tqdm
            frame_iter = tqdm(range(len(frame_files) - 1), desc="Interpolating", unit="pair")
        except ImportError:
            frame_iter = range(len(frame_files) - 1)
        
        for i in frame_iter:
            # Load frame pair
            frame1_path = os.path.join(frames_in_dir, frame_files[i])
            frame2_path = os.path.join(frames_in_dir, frame_files[i + 1])
            
            frame1 = cv2.imread(frame1_path)
            frame2 = cv2.imread(frame2_path)
            
            # Convert BGR → RGB and normalize to [0, 1]
            frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            
            # Write first frame of pair
            out_path = os.path.join(frames_out_dir, f"{output_frame_idx:08d}.png")
            frame1_bgr = (frame1 * 255).astype(np.uint8)
            frame1_bgr = cv2.cvtColor(frame1_bgr, cv2.COLOR_RGB2BGR)
            cv2.imwrite(out_path, frame1_bgr)
            output_frame_idx += 1
            
            # Generate interpolated frames
            interp_frames = interpolator.interpolate_recursive(
                frame1, frame2, times_to_interpolate
            )
            
            # Write interpolated frames
            for interp_frame in interp_frames:
                out_path = os.path.join(frames_out_dir, f"{output_frame_idx:08d}.png")
                interp_bgr = (np.clip(interp_frame, 0, 1) * 255).astype(np.uint8)
                interp_bgr = cv2.cvtColor(interp_bgr, cv2.COLOR_RGB2BGR)
                cv2.imwrite(out_path, interp_bgr)
                output_frame_idx += 1
            
            # Update progress
            if not isinstance(frame_iter, range):
                pass  # tqdm handles it
            else:
                progress("Interpolating", i + 1, total_pairs)
        
        # Write last frame
        last_frame_path = os.path.join(frames_in_dir, frame_files[-1])
        last_frame = cv2.imread(last_frame_path)
        out_path = os.path.join(frames_out_dir, f"{output_frame_idx:08d}.png")
        cv2.imwrite(out_path, last_frame)
        
        if verbose:
            print()  # Newline after progress
        
        total_output_frames = output_frame_idx
        log(f"  Generated {total_output_frames} frames ({frame_count} → {total_output_frames})")
        
        # Cleanup model to free GPU memory
        interpolator.cleanup()
        
        # ─────────────────────────────────────────────────────────
        # Step 4: Assemble output video with original audio
        # ─────────────────────────────────────────────────────────
        log("Assembling final video...")
        
        success = assemble_video(
            frames_out_dir, output_path, actual_target_fps,
            audio_path=audio_path,
            config=cfg.get("output_quality", {}),
            progress_callback=lambda c, t: progress("Encoding", c, t)
        )
        
        if verbose:
            print()  # Newline after progress
        
        if success:
            output_info = get_video_info(output_path)
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            log(f"  Output: {output_info['width']}x{output_info['height']} @ {output_info['fps']:.2f}fps")
            log(f"  File size: {file_size:.2f} MB")
            log(f"✓ Interpolation complete in {time.time() - start_time:.1f}s")
            return True
        else:
            log("✗ Failed to assemble video")
            return False


def interpolate_video_simple(
    input_path: str,
    output_path: str,
    fps_multiplier: int = 2,
    verbose: bool = True
) -> bool:
    """
    Simple interface for video interpolation.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        fps_multiplier: 2 = double FPS, 4 = quadruple FPS
        
    Returns:
        True if successful
    """
    import math
    times = int(math.log2(fps_multiplier))
    return interpolate_video(
        input_path, output_path,
        times_to_interpolate=times,
        verbose=verbose
    )


# ─────────────────────────────────────────────────────────────────────────────
# Integration with UGC Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def apply_film_interpolation(
    input_path: str,
    output_path: str,
    config: dict,
    verbose: bool = True
) -> bool:
    """
    Apply FILM interpolation as part of the UGC pipeline.
    
    Called from postprocess.py or clips.py when frame_interpolation.model == "film".
    
    Args:
        input_path: Input video (after other post-processing)
        output_path: Output video path
        config: frame_interpolation config from style.json
        verbose: Print progress
        
    Returns:
        True if successful, False if skipped or failed
    """
    if not config.get("enabled", False):
        return False
    
    model = config.get("model", "rife-v4").lower()
    if model != "film":
        return False  # Use RIFE instead
    
    target_fps = config.get("target_fps", 60)
    
    # Check if TensorFlow is available
    try:
        _lazy_import_tensorflow()
    except ImportError as e:
        logging.warning(f"FILM interpolation unavailable: {e}")
        logging.warning("Install tensorflow and tensorflow-hub: pip install tensorflow tensorflow-hub")
        return False
    
    film_config = {
        "target_fps": target_fps,
        "preserve_audio": True,
        "output_quality": {
            "crf": 18,
            "preset": "medium"
        },
        "gpu_memory_limit": config.get("gpu_memory_limit")
    }
    
    return interpolate_video(input_path, output_path, target_fps=target_fps, 
                            config=film_config, verbose=verbose)


# ─────────────────────────────────────────────────────────────────────────────
# CLI Interface
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Command-line interface for FILM interpolation."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="FILM Frame Interpolation - Smooth video frame rate upscaling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Double FPS (30 → 60)
  python film_interpolation.py --input video.mp4 --target_fps 60 --output smooth.mp4
  
  # Quadruple FPS with high quality
  python film_interpolation.py --input video.mp4 --times 2 --crf 15 --output smooth.mp4
  
  # Simple 2x multiplier
  python film_interpolation.py --input video.mp4 --multiplier 2 --output smooth.mp4
"""
    )
    
    parser.add_argument("--input", "-i", required=True, help="Input video file (MP4/MOV)")
    parser.add_argument("--output", "-o", required=True, help="Output video file")
    parser.add_argument("--target_fps", "-fps", type=float, help="Target FPS (e.g., 60)")
    parser.add_argument("--multiplier", "-m", type=int, choices=[2, 4, 8], 
                        help="FPS multiplier (2/4/8)")
    parser.add_argument("--times", "-t", type=int, default=1,
                        help="Times to interpolate (1=2x, 2=4x, 3=8x)")
    parser.add_argument("--crf", type=int, default=18, help="Output quality (0-51, lower=better)")
    parser.add_argument("--preset", default="medium", 
                        choices=["ultrafast", "fast", "medium", "slow", "veryslow"],
                        help="Encoding preset (medium recommended for balance)")
    parser.add_argument("--gpu-memory", type=float, help="GPU memory limit in GB")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")
    
    args = parser.parse_args()
    
    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Build config
    config = {
        "output_quality": {
            "crf": args.crf,
            "preset": args.preset
        },
        "gpu_memory_limit": args.gpu_memory
    }
    
    # Calculate times_to_interpolate
    times = args.times
    if args.multiplier:
        import math
        times = int(math.log2(args.multiplier))
    
    target_fps = args.target_fps
    
    print("\n" + "="*50)
    print("  FILM Frame Interpolation")
    print("  Google Research - Frame Interpolation for Large Motion")
    print("="*50 + "\n")
    
    start_time = time.time()
    
    success = interpolate_video(
        args.input,
        args.output,
        target_fps=target_fps,
        times_to_interpolate=times,
        config=config,
        verbose=not args.quiet
    )
    
    elapsed = time.time() - start_time
    
    if success:
        print(f"\n✓ Completed in {elapsed:.1f}s")
        print(f"  Output: {args.output}")
    else:
        print(f"\n✗ Interpolation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

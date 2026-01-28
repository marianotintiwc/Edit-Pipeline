from moviepy.editor import CompositeVideoClip
import os
import sys
import time
import shutil
import subprocess
from typing import Dict, Any, Optional, Callable


def _get_ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    ffmpeg = shutil.which("ffmpeg")
    return ffmpeg or "ffmpeg"


def _has_nvenc(ffmpeg_path: str) -> bool:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        encoders = result.stdout or ""
        return "h264_nvenc" in encoders
    except Exception:
        return False

def print_export_status(message: str, indent: int = 0):
    """Print a formatted status message for export processing."""
    prefix = "  " * indent
    print(f"{prefix}→ {message}")
    sys.stdout.flush()

def export_video(
    final_clip: CompositeVideoClip,
    output_path: str,
    style_config: Optional[Dict[str, Any]] = None,
    log_func: Optional[Callable[[str], None]] = None
):
    export_start = time.time()

    # 1. Directory Setup
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 2. Determine FPS
    target_fps = 30
    if style_config:
        pp_config = style_config.get("postprocess", {})
        interp_config = pp_config.get("frame_interpolation", {})
        if interp_config.get("enabled", False):
            target_fps = interp_config.get("target_fps", 30)

    # 3. Setup Logging
    def log_message(message: str):
        if log_func:
            log_func(message)
        print(f"     {message}")

    log_message(f"Exporting: {os.path.basename(output_path)} @ {target_fps} FPS")
    
    # Debug audio status
    has_audio = final_clip.audio is not None
    log_message(f"Audio status: {'HAS AUDIO' if has_audio else 'NO AUDIO!'}") 
    if has_audio:
        try:
            audio_dur = final_clip.audio.duration
            log_message(f"Audio duration: {audio_dur:.2f}s")
        except:
            log_message("Audio duration: unknown")

    ffmpeg_path = _get_ffmpeg_path()
    nvenc_available = _has_nvenc(ffmpeg_path)
    log_message(f"FFmpeg: {ffmpeg_path} | h264_nvenc={'YES' if nvenc_available else 'NO'}")

    # ─────────────────────────────────────────────────────────────
    # MAX QUALITY GPU CONFIGURATION (L40S / Ada Lovelace)
    # Uses CRF-like quality mode for broad FFmpeg compatibility
    # ─────────────────────────────────────────────────────────────
    nvenc_params = [
        '-preset', 'p7',
        '-tune', 'hq',
        '-cq', '19',
        '-b:v', '0',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart'
    ]

    if not nvenc_available:
        log_message("NVENC not available. Falling back to libx264.")
        final_clip.write_videofile(
            output_path,
            fps=target_fps,
            codec='libx264',
            audio_codec='aac',
            audio_bitrate='320k',
            threads=4,
            logger='bar'
        )

        export_elapsed = time.time() - export_start
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        log_message(f"✅ Export complete! Size: {file_size_mb:.2f} MB | Time: {export_elapsed:.1f}s")
        return True

    print("     Starting NVENC (Max Quality) Encoding...")
    log_message(f"NVENC params: {' '.join(nvenc_params)}")

    try:
        final_clip.write_videofile(
            output_path,
            fps=target_fps,
            codec='h264_nvenc',
            audio_codec='aac',
            audio_bitrate='320k',
            threads=4,
            ffmpeg_params=nvenc_params,
            logger='bar'
        )

        export_elapsed = time.time() - export_start
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

        log_message(f"✅ Export complete! Size: {file_size_mb:.2f} MB | Time: {export_elapsed:.1f}s")
        return True

    except Exception as e:
        log_message(f"❌ GPU Export Failed: {str(e)}")
        print("     Falling back to CPU...")
        final_clip.write_videofile(output_path, fps=target_fps, codec='libx264', logger='bar')

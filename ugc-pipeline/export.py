from moviepy.editor import CompositeVideoClip
import os
import sys
import time
from typing import Dict, Any, Optional

def print_export_status(message: str, indent: int = 0):
    """Print a formatted status message for export processing."""
    prefix = "  " * indent
    print(f"{prefix}→ {message}")
    sys.stdout.flush()

def export_video(final_clip: CompositeVideoClip, output_path: str, style_config: Optional[Dict[str, Any]] = None):
    """
    Exports the final video to MP4 with optimized compression.
    
    Note: Post-processing (color grading, grain, etc.) is now applied per-scene
    in clips.py, BEFORE concatenation. This ensures only AI-generated scenes
    are processed, while brolls (real footage) remain untouched.
    
    Args:
        final_clip: The MoviePy video clip to export
        output_path: Path for the final output file
        style_config: Style configuration dict (for future use)
    """
    export_start = time.time()
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print_export_status(f"Created output directory: {output_dir}")
    
    # Determine target FPS from frame interpolation config
    target_fps = 30  # Default
    if style_config:
        pp_config = style_config.get("postprocess", {})
        interp_config = pp_config.get("frame_interpolation", {})
        if interp_config.get("enabled", False):
            target_fps = interp_config.get("target_fps", 30)
    
    print(f"\n  📤 Exporting video...")
    print(f"     Output: {os.path.basename(output_path)}")
    print(f"     Duration: {final_clip.duration:.2f}s")
    print(f"     Resolution: {final_clip.size[0]}x{final_clip.size[1]}")
    print(f"     Target FPS: {target_fps}")
    
    # Use H.264 iPhone standard encoding
    # CRF 23 is iPhone default balance (same as post-processing output)
    video_bitrate = "8000k" 
    audio_bitrate = "192k"
    
    print(f"     Codec: H.264 (libx264)")
    print(f"     Video: {video_bitrate} @ CRF 23")
    print(f"     Audio: AAC {audio_bitrate}")
    print(f"     Preset: slow (quality priority)\n")
    
    print_export_status("Starting MoviePy encoding (this may take a while)...", 1)
    
    try:
        final_clip.write_videofile(
            output_path,
            fps=target_fps,
            codec='libx264',
            audio_codec='aac',
            bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
            preset='slow',
            threads=4,
            ffmpeg_params=[
                '-crf', '23',  # iPhone standard quality
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart'
            ],
            logger='bar'  # Show progress bar
        )
        
        export_elapsed = time.time() - export_start
        
        # Report final file size
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        
        print(f"\n  ✅ Export complete!")
        print(f"     File: {output_path}")
        print(f"     Size: {file_size_mb:.2f} MB")
        print(f"     Time: {export_elapsed:.1f}s")
        
        return True
        
    except Exception as e:
        export_elapsed = time.time() - export_start
        print(f"\n  ❌ Export FAILED after {export_elapsed:.1f}s")
        print(f"     Error: {str(e)}")
        raise

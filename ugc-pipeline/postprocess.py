"""
UGC Post-Processing Module
Applies FFmpeg-based effects to make AI-generated videos look like casual iPhone UGC footage.

Effects (applied in correct order for realism):
1. Frame interpolation (RIFE or Google FILM) - 24fps → 30/60fps
2. Color grading (brightness, contrast, curves for shadows/highlights)
3. Chromatic aberration (RGB channel offset)
4. Lens distortion (barrel distortion for iPhone wide-angle)
5. Vignette (edge darkening)
6. Halation (warm bloom from highlights - film/analog look)
7. Film grain (temporal noise) - LAST to hide seams

Order matters: Color grade first → aberration/distortion → vignette → halation → grain last

Frame Interpolation Models:
- "rife-v4": Fast, requires rife-ncnn-vulkan binary
- "film": Google's FILM model (highest quality for talking heads, requires TensorFlow)
"""

import os
import subprocess
import shutil
import tempfile
import logging
from typing import Dict, Any, Optional

# Default post-processing configuration
DEFAULT_CONFIG = {
    "enabled": False,
    
    # Frame interpolation - 24fps AI output to 30fps iPhone standard
    # Supports: "rife-v4" (fast, requires rife-ncnn-vulkan), "film" (Google FILM, high quality)
    "frame_interpolation": {
        "enabled": True,
        "input_fps": 24,          # Source framerate (AI typically outputs 24fps)
        "target_fps": 30,         # Target framerate (iPhone standard)
        "model": "rife-v4",       # "rife-v4" or "film" (Google FILM for highest quality)
        "gpu_id": 0,              # GPU to use (-1 for CPU, RIFE only)
        "gpu_memory_limit": None  # GPU memory limit in GB (FILM only, None = auto)
    },
    
    # Color grading - makes footage look more natural/casual (FIRST)
    "color_grading": {
        "enabled": True,
        "brightness": -0.08,      # Exposure -17 equivalent (range: -1.0 to 1.0)
        "contrast": 0.7,          # Contrast -38 equivalent (range: 0 to 2.0, 1.0 = neutral)
        "saturation": 1.0,        # Saturation (range: 0 to 3.0, 1.0 = neutral)
        "gamma": 1.0,             # Gamma correction (range: 0.1 to 10.0, 1.0 = neutral)
        # Curves for shadows/highlights control
        "curves": {
            "enabled": True,
            "shadows_lift": 0.3,      # Lift shadows (0.0-0.5, higher = lifted blacks)
            "highlights_compress": 0.7, # Compress highlights (0.5-1.0, lower = compressed)
            "black_point": 0.0,       # Black point (0.0-0.2)
            "white_point": 1.0        # White point (0.8-1.0)
        }
    },
    
    # Chromatic aberration - RGB channel offset for lens imperfection (SECOND)
    "chromatic_aberration": {
        "enabled": True,
        "offset_pixels": 2        # Pixel offset for R/B channels (0-10, 2 = subtle)
    },
    
    # Lens distortion - barrel/pincushion for wide-angle iPhone feel (THIRD)
    "lens_distortion": {
        "enabled": True,
        "k1": -0.05               # Distortion coefficient (-0.5 to 0.5, -0.05 = subtle barrel)
    },
    
    # Vignette - darkens edges like iPhone lens (FOURTH)
    "vignette": {
        "enabled": True,
        "intensity": 0.785        # pi/4 ≈ 0.785 (range: 0 to 1.57, higher = stronger)
    },
    
    # Halation - warm bloom from highlights (FIFTH, film/analog look)
    "halation": {
        "enabled": False,         # Off by default, enable for vintage film look
        "intensity": 0.15,        # Bloom opacity (0.0-1.0, 0.15 = subtle)
        "radius": 5,              # Blur radius for glow (1-20, 5 = soft)
        "color": "warm"           # "warm" (orange/red), "cool" (blue), or "neutral"
    },
    
    # Film grain - adds organic texture (LAST - hides seams)
    "grain": {
        "enabled": True,
        "strength": 10,           # Grain intensity (0-100, 10 = subtle, 25 = heavy)
        "temporal": True          # Temporal variation (moving grain vs static)
    },
    
    # Output quality - H.264 iPhone standard
    "output": {
        "crf": 23,                # Quality (0-51, 23 = iPhone default balance)
        "preset": "slow"          # Encoding preset (ultrafast to veryslow)
    }
}


def get_ffmpeg_path() -> str:
    """Get FFmpeg executable path."""
    # Try imageio_ffmpeg first
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    
    # Fall back to system ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    
    raise RuntimeError("FFmpeg not found. Install imageio-ffmpeg or add ffmpeg to PATH.")


def get_rife_path() -> Optional[str]:
    """Get RIFE executable path (optional)."""
    # First check PATH
    rife = shutil.which("rife-ncnn-vulkan")
    if rife:
        return rife
    
    # Check common installation locations
    import glob
    common_paths = [
        r"C:\Users\*\Desktop\ugc editor\tools\*\rife-ncnn-vulkan.exe",
        r"C:\tools\rife*\rife-ncnn-vulkan.exe",
        r"C:\Program Files\rife*\rife-ncnn-vulkan.exe",
    ]
    
    for pattern in common_paths:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    
    return None


def build_filter_graph(config: Dict[str, Any]) -> str:
    """
    Constructs a robust filter_complex graph with explicit labels.
    This prevents 'semicolon vs comma' errors and handles sizing correctly.
    """
    filters = []
    current_label = "[0:v]" # Start with input video
    step_count = 0

    def add_step(filter_str):
        nonlocal current_label, step_count
        next_label = f"[v{step_count+1}]"
        # Append [in]FILTER[out]
        filters.append(f"{current_label}{filter_str}{next_label}")
        current_label = next_label
        step_count += 1

    # 1. Color Grading (Eq)
    cg = config.get("color_grading", {})
    if cg.get("enabled", True):
        brightness = cg.get("brightness", 0.0)
        contrast = cg.get("contrast", 1.0)
        saturation = cg.get("saturation", 1.0)
        gamma = cg.get("gamma", 1.0)
        
        eq = f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}:gamma={gamma}"
        add_step(eq)

        # 1b. Curves
        curves = cg.get("curves", {})
        if curves.get("enabled", False):
            black = curves.get("black_point", 0.0)
            shadow_lift = curves.get("shadows_lift", 0.0)
            highlight_compress = curves.get("highlights_compress", 1.0)
            white = curves.get("white_point", 1.0)
            curve_str = f"0/{black} 0.2/{shadow_lift} 0.8/{highlight_compress} 1/{white}"
            add_step(f"curves=all='{curve_str}'")

    # 2. Chromatic Aberration (THE FIX: Resize & Crop)
    ca = config.get("chromatic_aberration", {})
    if ca.get("enabled", False):
        offset = ca.get("offset_pixels", 2)
        if offset > 0:
            # We must crop exactly what we added. 
            # If offset=2, we add 4px total (2 left, 2 right).
            # We scale to iw+4:ih+4, then crop back to iw:ih
            scale_w = f"iw+{offset*2}"
            scale_h = f"ih+{offset*2}"
            # Crop syntax: w=iw-OFFSET:h=ih-OFFSET:x=HALF:y=HALF
            # But inside the filter chain, 'iw' refers to the current (scaled) input.
            # So if we scaled up by 4, we crop by 'iw-4'.
            crop_args = f"w=iw-{offset*2}:h=ih-{offset*2}:x={offset}:y={offset}"
            
            # Complex graph for CA
            # Split into 3 -> Process R/B -> Merge
            next_label = f"[v{step_count+1}]"
            
            graph = (
                f"{current_label}split=3[r_in][g_in][b_in];"
                # Red: Scale Up -> Crop Center
                f"[r_in]scale={scale_w}:{scale_h}:flags=bicubic,crop={crop_args}[r_out];"
                # Green: Keep (Anchor)
                f"[g_in]null[g_out];"
                # Blue: Scale Up -> Crop Center
                f"[b_in]scale={scale_w}:{scale_h}:flags=bicubic,crop={crop_args}[b_out];"
                # Merge
                f"[r_out][g_out][b_out]mergeplanes=0x000102:format=gbrp{next_label}"
            )
            filters.append(graph)
            current_label = next_label
            step_count += 1

    # 3. Lens Distortion
    lens = config.get("lens_distortion", {})
    if lens.get("enabled", False):
        k1 = lens.get("k1", -0.05)
        add_step(f"lenscorrection=cx=0.5:cy=0.5:k1={k1}:k2=0")

    # 4. Vignette
    vignette = config.get("vignette", {})
    if vignette.get("enabled", True):
        intensity = vignette.get("intensity", 0.2)
        add_step(f"vignette={intensity}")

    # 5. Halation (warm bloom from highlights - film look)
    halation = config.get("halation", {})
    if halation.get("enabled", False):
        hal_intensity = halation.get("intensity", 0.15)
        hal_radius = halation.get("radius", 5)
        hal_color = halation.get("color", "warm")
        
        # Color temperature shift for warm vs cool halation (subtle!)
        # rs/gs/bs = shadows, rm/gm/bm = midtones, rh/gh/bh = highlights
        if hal_color == "warm":
            # Subtle warm: slight red/yellow boost in the bloom
            color_filter = "colorbalance=rh=0.1:gh=0.03:bh=-0.05"
        elif hal_color == "cool":
            # Subtle cool: slight blue tint in highlights
            color_filter = "colorbalance=rh=-0.05:gh=0.03:bh=0.1"
        else:
            # Neutral - no color shift
            color_filter = "null"
        
        # Proper halation: threshold highlights, blur, blend
        # Using curves to create a proper highlight-only mask (black out darks/mids)
        next_label = f"[v{step_count+1}]"
        
        # Threshold: Use curves to crush shadows/mids and keep only highlights
        # This creates a proper "highlight mask" before blurring
        threshold_curve = "0/0 0.6/0 0.85/0.5 1/1"
        
        halation_graph = (
            f"{current_label}split=2[hal_main][hal_glow];"
            # Extract ONLY highlights: crush shadows/mids with curves, then blur and tint
            f"[hal_glow]curves=all='{threshold_curve}',"
            f"gblur=sigma={hal_radius},"
            f"{color_filter}[hal_bloom];"
            # Blend bloom back using screen mode (additive-like)
            f"[hal_main][hal_bloom]blend=all_mode=screen:all_opacity={hal_intensity}{next_label}"
        )
        filters.append(halation_graph)
        current_label = next_label
        step_count += 1

    # 6. Grain (LAST - hides seams)
    grain = config.get("grain", {})
    if grain.get("enabled", True):
        strength = grain.get("strength", 15)
        temporal = "t" if grain.get("temporal", True) else ""
        add_step(f"noise=alls={strength}:allf={temporal}+u")

    # Join with semicolons (Standard filter_complex syntax)
    return ";".join(filters), current_label


def apply_postprocess(input_path: str, output_path: str, config: Dict[str, Any], verbose: bool = True) -> bool:
    if not config.get("enabled", False):
        shutil.copy2(input_path, output_path)
        return True
    
    ffmpeg = get_ffmpeg_path()
    interp_config = config.get("frame_interpolation", {})
    use_interpolation = interp_config.get("enabled", False)
    interp_model = interp_config.get("model", "rife-v4").lower()
    
    # 1. Build the graph
    filter_graph, final_label = build_filter_graph(config)
    
    # Frame interpolation workflow
    if use_interpolation:
        rife_path = get_rife_path()
        if verbose:
            print(f"      [DEBUG] Frame interpolation: enabled={use_interpolation}, model={interp_model}")
            print(f"      [DEBUG] RIFE path: {rife_path}")
        
        # Check if FILM model is requested
        if interp_model == "film":
            try:
                return _apply_with_film(input_path, output_path, config, filter_graph, final_label, verbose)
            except Exception as e:
                if verbose:
                    print(f"      [ERROR] FILM failed: {e}, falling back to direct FFmpeg")
        # Fall back to RIFE if available
        elif rife_path:
            try:
                result = _apply_with_rife(input_path, output_path, config, filter_graph, final_label, verbose)
                if result:
                    return result
                else:
                    if verbose:
                        print(f"      [WARN] RIFE returned False, falling back to direct FFmpeg")
            except Exception as e:
                if verbose:
                    print(f"      [ERROR] RIFE failed: {e}, falling back to direct FFmpeg")
        else:
            if verbose:
                print(f"      [WARN] Interpolation model '{interp_model}' not available, skipping")
    
    # No interpolation - direct FFmpeg processing
    return _apply_direct(input_path, output_path, filter_graph, final_label, config, verbose)

def _apply_direct(input_path, output_path, filter_graph, final_label, config, verbose):
    ffmpeg = get_ffmpeg_path()
    out_cfg = config.get("output", {})
    
    cmd = [ffmpeg, "-y", "-i", input_path]
    
    if filter_graph:
        # Map the final label to the output
        cmd.extend(["-filter_complex", filter_graph, "-map", final_label, "-map", "0:a?"])
    else:
        cmd.extend(["-c:v", "copy", "-c:a", "copy"])
        
    cmd.extend([
        "-c:v", "libx264", "-crf", str(out_cfg.get("crf", 23)),
        "-preset", out_cfg.get("preset", "slow"),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path
    ])
    
    try:
        subprocess.run(cmd, check=True, capture_output=not verbose)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error: {e.stderr.decode() if e.stderr else 'Unknown'}")
        return False

def _apply_with_rife(input_path, output_path, config, filter_graph, final_label, verbose):
    """
    Apply RIFE frame interpolation with correct FPS/duration math.
    
    RIFE doubles the frame count. To maintain original duration:
    - Original: N frames @ source_fps → duration = N/source_fps
    - After RIFE: 2N frames → to keep same duration, fps = 2N/duration = 2*source_fps
    
    If target_fps < 2*source_fps, we need to limit RIFE or drop frames.
    If target_fps > 2*source_fps, we use what RIFE gives (2*source_fps).
    """
    ffmpeg = get_ffmpeg_path()
    rife = get_rife_path()
    rife_cfg = config.get("frame_interpolation", {})
    out_cfg = config.get("output", {})
    # Keep 60fps from RIFE (no downsampling) - was 45fps
    target_fps = rife_cfg.get("target_fps", 60)
    
    with tempfile.TemporaryDirectory() as tmp:
        # Step 1: Get source video info (FPS and duration)
        probe_cmd = [
            ffmpeg, "-i", input_path, "-f", "null", "-"
        ]
        # Use ffprobe-style detection
        info_cmd = [
            ffmpeg, "-i", input_path
        ]
        try:
            result = subprocess.run(info_cmd, capture_output=True, text=True)
            # Parse FPS from stderr (ffmpeg outputs info to stderr)
            import re
            fps_match = re.search(r'(\d+(?:\.\d+)?)\s*fps', result.stderr)
            duration_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
            
            source_fps = float(fps_match.group(1)) if fps_match else 30.0
            if duration_match:
                h, m, s = duration_match.groups()
                source_duration = float(h) * 3600 + float(m) * 60 + float(s)
            else:
                source_duration = None
                
            if verbose:
                print(f"      [RIFE] Source: {source_fps}fps, duration: {source_duration:.2f}s" if source_duration else f"      [RIFE] Source: {source_fps}fps")
        except Exception as e:
            if verbose:
                print(f"      [WARN] Could not detect source FPS: {e}, assuming 30fps")
            source_fps = 30.0
            source_duration = None
        
        # RIFE doubles frame count, so interpolated fps = 2 * source_fps
        rife_output_fps = source_fps * 2
        
        # Step 2: Extract frames at source FPS
        in_frames = os.path.join(tmp, "in")
        out_frames = os.path.join(tmp, "out")
        os.makedirs(in_frames)
        os.makedirs(out_frames)
        
        # Extract at source FPS to maintain correct frame count
        subprocess.run([
            ffmpeg, "-y", "-i", input_path, 
            "-vf", f"fps={source_fps}",  # Ensure consistent frame extraction
            f"{in_frames}/%08d.png"
        ], check=True, capture_output=True)
        
        # Count input frames
        input_frame_count = len([f for f in os.listdir(in_frames) if f.endswith('.png')])
        if verbose:
            print(f"      [RIFE] Extracted {input_frame_count} frames")
        
        # Step 3: Run RIFE interpolation (doubles frames)
        subprocess.run([
            rife, "-i", in_frames, "-o", out_frames, 
            "-m", rife_cfg.get("model", "rife-v4"),
            "-g", str(rife_cfg.get("gpu_id", 0))
        ], check=True, capture_output=True)
        
        # Count output frames
        output_frame_count = len([f for f in os.listdir(out_frames) if f.endswith('.png')])
        actual_multiplier = output_frame_count / input_frame_count if input_frame_count > 0 else 2
        
        if verbose:
            print(f"      [RIFE] Output: {output_frame_count} frames ({actual_multiplier:.1f}x)")
        
        # Step 4: Calculate correct output FPS to maintain duration
        # Duration must stay the same: output_frames / output_fps = source_duration
        # Therefore: output_fps = output_frames / source_duration
        if source_duration and source_duration > 0:
            correct_output_fps = output_frame_count / source_duration
        else:
            # Fallback: assume RIFE doubled, so fps doubles
            correct_output_fps = source_fps * actual_multiplier
        
        # Clamp to target_fps if user specified a lower value
        # (we'll drop frames via fps filter if needed)
        final_fps = min(correct_output_fps, target_fps) if target_fps else correct_output_fps
        
        if verbose:
            print(f"      [RIFE] Assembling at {correct_output_fps:.1f}fps (target: {target_fps}fps)")
        
        # Step 5: Re-encode with correct FPS and filters
        cmd = [
            ffmpeg, "-y", 
            "-framerate", str(correct_output_fps),  # Input at RIFE's actual output rate
            "-i", f"{out_frames}/%08d.png",
            "-i", input_path,  # Load original for audio mapping
        ]
        
        # If target_fps is lower than RIFE output, add fps filter to downsample
        if target_fps and target_fps < correct_output_fps:
            if filter_graph:
                # Prepend fps filter to the existing filter graph
                fps_filter = f"[0:v]fps={target_fps}[fps_out];[fps_out]"
                # Replace [0:v] references in filter_graph
                modified_graph = filter_graph.replace("[0:v]", "[fps_out]", 1)
                full_graph = f"[0:v]fps={target_fps}[fps_out];{modified_graph}"
                cmd.extend(["-filter_complex", full_graph, "-map", final_label])
            else:
                cmd.extend(["-vf", f"fps={target_fps}"])
        elif filter_graph:
            cmd.extend(["-filter_complex", filter_graph, "-map", final_label])
        
        # Map audio from original input (Stream 1) - CRITICAL for sync
        cmd.extend(["-map", "1:a?", "-c:a", "copy"])
        
        cmd.extend([
            "-c:v", "libx264", "-crf", str(out_cfg.get("crf", 23)),
            "-preset", out_cfg.get("preset", "slow"),
            "-pix_fmt", "yuv420p", output_path
        ])
        
        try:
            subprocess.run(cmd, check=True, capture_output=not verbose)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Error: {e.stderr.decode() if e.stderr else 'Unknown'}")
            return False


def _apply_with_film(input_path, output_path, config, filter_graph, final_label, verbose):
    """
    Apply post-processing using Google's FILM model for frame interpolation.
    
    FILM (Frame Interpolation for Large Motion) excels at:
    - Talking head videos (lip-sync preservation)
    - Large motion scenes
    - High-quality temporal consistency
    
    Pipeline:
    1. Apply FFmpeg filters first (color grading, grain, etc.)
    2. Run FILM interpolation on filtered video
    3. Preserve original audio exactly for lip-sync
    """
    from ugc_pipeline.film_interpolation import interpolate_video, get_video_info
    
    ffmpeg = get_ffmpeg_path()
    film_cfg = config.get("frame_interpolation", {})
    out_cfg = config.get("output", {})
    
    with tempfile.TemporaryDirectory() as tmp:
        # Step 1: Apply FFmpeg filters first (if any)
        filtered_path = os.path.join(tmp, "filtered.mp4")
        
        if filter_graph:
            cmd = [
                ffmpeg, "-y", "-i", input_path,
                "-filter_complex", filter_graph,
                "-map", final_label, "-map", "0:a?",
                "-c:v", "libx264", "-crf", "18",  # High quality intermediate
                "-preset", "fast",
                "-c:a", "copy",
                "-pix_fmt", "yuv420p",
                filtered_path
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=not verbose)
            except subprocess.CalledProcessError as e:
                print(f"FFmpeg filter error: {e.stderr.decode() if e.stderr else 'Unknown'}")
                return False
        else:
            # No filters, use input directly
            filtered_path = input_path
        
        # Step 2: Apply FILM interpolation
        if verbose:
            print(f"  → Applying FILM frame interpolation...")
        
        film_config = {
            "target_fps": film_cfg.get("target_fps", 60),
            "preserve_audio": True,
            "output_quality": {
                "crf": out_cfg.get("crf", 18),
                "preset": out_cfg.get("preset", "slow")
            },
            "gpu_memory_limit": film_cfg.get("gpu_memory_limit")
        }
        
        try:
            success = interpolate_video(
                filtered_path,
                output_path,
                target_fps=film_cfg.get("target_fps", 60),
                config=film_config,
                verbose=verbose
            )
            return success
        except Exception as e:
            print(f"FILM interpolation error: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to direct processing without interpolation
            if verbose:
                print("  → Falling back to direct processing (no interpolation)")
            return _apply_direct(input_path, output_path, filter_graph, final_label, config, verbose)

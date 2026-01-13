import json
import os
import re
import time
import sys
from moviepy.editor import VideoFileClip, concatenate_videoclips, vfx, CompositeVideoClip
from typing import List, Dict, Any

TARGET_RESOLUTION = (1080, 1920)
TARGET_FPS = 30  # Default, can be overridden by frame_interpolation config


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
    """Get the endcard video path for the given GEO."""
    if not style_config:
        return None
    
    endcard_config = style_config.get("endcard", {})
    if not endcard_config.get("enabled", False):
        return None
    
    folder = endcard_config.get("folder", "")
    files = endcard_config.get("files", {})
    
    filename = files.get(geo)
    if not filename:
        return None
    
    path = os.path.join(folder, filename)
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
    if os.path.isdir(source):
        clips_data = get_video_files_from_dir(source)
    else:
        clips_data = load_clips_config(source)
        
    video_clips = []

    print(f"Processing {len(clips_data)} clips...")

    for i, clip_info in enumerate(clips_data):
        path = clip_info.get("path")
        if not os.path.exists(path):
            print(f"Warning: Clip not found at {path}. Skipping.")
            continue

        print(f"  Loading clip {i+1}: {path}")
        clip = VideoFileClip(path)

        # 1. Trim if requested
        start = clip_info.get("start")
        end = clip_info.get("end")
        if start is not None or end is not None:
            clip = clip.subclip(start, end)

        # 2. Resize/Crop to 9:16 (1080x1920)
        # Strategy: Resize to fill height, then center crop width, OR resize to fill width, then center crop height.
        # We want to fill the screen.
        
        # Calculate aspect ratios
        target_ratio = TARGET_RESOLUTION[0] / TARGET_RESOLUTION[1]
        clip_ratio = clip.w / clip.h

        if clip_ratio > target_ratio:
            # Clip is wider than target (e.g. 16:9 vs 9:16) -> Resize by height, crop width
            clip = clip.resize(height=TARGET_RESOLUTION[1])
            clip = clip.crop(x1=clip.w/2 - TARGET_RESOLUTION[0]/2, 
                             x2=clip.w/2 + TARGET_RESOLUTION[0]/2)
        else:
            # Clip is taller/narrower -> Resize by width, crop height
            clip = clip.resize(width=TARGET_RESOLUTION[0])
            clip = clip.crop(y1=clip.h/2 - TARGET_RESOLUTION[1]/2, 
                             y2=clip.h/2 + TARGET_RESOLUTION[1]/2)

        # Force resolution just in case of rounding errors
        clip = clip.resize(TARGET_RESOLUTION)
        
        video_clips.append(clip)

    if not video_clips:
        raise ValueError("No valid clips found to process.")

    # Apply transitions if enabled
    if style_config and style_config.get("transitions", {}).get("enabled", False):
        transition_duration = style_config.get("transitions", {}).get("duration", 0.5)
        print(f"Applying slide transitions (duration: {transition_duration}s)...")
        
        final_clips = []
        current_time = 0
        
        for i, clip in enumerate(video_clips):
            if i == 0:
                # First clip: no transition in, just add it
                final_clips.append(clip.set_start(current_time))
                current_time += clip.duration
            else:
                # Apply slide transition
                # Previous clip slides out to the left
                # Current clip slides in from the right
                
                prev_clip = video_clips[i-1]
                
                # Adjust timing: overlap by transition_duration
                current_time -= transition_duration
                
                # Outgoing clip: slides left
                def make_slide_out(t):
                    # t goes from 0 to transition_duration
                    # x goes from 0 to -TARGET_RESOLUTION[0]
                    if t < prev_clip.duration - transition_duration:
                        return (0, 0)  # Static position
                    else:
                        progress = (t - (prev_clip.duration - transition_duration)) / transition_duration
                        x = -TARGET_RESOLUTION[0] * progress
                        return (x, 0)
                
                # Incoming clip: slides in from right
                def make_slide_in(t):
                    # t goes from 0 to transition_duration
                    # x goes from +TARGET_RESOLUTION[0] to 0
                    if t < transition_duration:
                        progress = t / transition_duration
                        x = TARGET_RESOLUTION[0] * (1 - progress)
                        return (x, 0)
                    else:
                        return (0, 0)  # Static position
                
                # Note: We already added prev_clip in the previous iteration
                # So we just add the current clip with slide-in animation
                clip_with_anim = clip.set_position(make_slide_in).set_start(current_time)
                final_clips.append(clip_with_anim)
                
                current_time += clip.duration
        
        # Composite all clips
        print("Compositing clips with transitions...")
        final_clip = CompositeVideoClip(final_clips, size=TARGET_RESOLUTION)
        final_clip.fps = get_target_fps(style_config)
    else:
        print("Concatenating clips...")
        final_clip = concatenate_videoclips(video_clips, method="compose")
        final_clip.fps = get_target_fps(style_config)
    
    return final_clip


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
    import tempfile
    import shutil
    
    project_name = os.path.basename(project_dir.rstrip('/'))
    print(f"\n  📁 Project: {project_name}")
    
    # Check if post-processing is enabled for scenes
    postprocess_config = {}
    if style_config:
        postprocess_config = style_config.get("postprocess", {})
    
    use_postprocess = postprocess_config.get("enabled", False)
    
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
            original_clip = VideoFileClip(video_path)
            original_audio = original_clip.audio
            print_clip_status(f"Loaded: {original_clip.duration:.2f}s @ {original_clip.fps}fps", 3)
            
            # Apply post-processing to AI scenes BEFORE loading into MoviePy
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
            target_ratio = TARGET_RESOLUTION[0] / TARGET_RESOLUTION[1]
            clip_ratio = clip.w / clip.h

            if clip_ratio > target_ratio:
                # Clip is wider than target -> Resize by height, crop width
                clip = clip.resize(height=TARGET_RESOLUTION[1])
                clip = clip.crop(x1=clip.w/2 - TARGET_RESOLUTION[0]/2, 
                                 x2=clip.w/2 + TARGET_RESOLUTION[0]/2)
            else:
                # Clip is taller/narrower -> Resize by width, crop height
                clip = clip.resize(width=TARGET_RESOLUTION[0])
                clip = clip.crop(y1=clip.h/2 - TARGET_RESOLUTION[1]/2, 
                                 y2=clip.h/2 + TARGET_RESOLUTION[1]/2)

            # Force resolution just in case of rounding errors
            clip = clip.resize(TARGET_RESOLUTION)
            
            clip_elapsed = time.time() - clip_start_time
            print_clip_status(f"✅ Done ({clip_elapsed:.1f}s)", 3)
            video_clips.append(clip)
        
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
                        endcard_raw = VideoFileClip(endcard_path, has_mask=True)
                        # Resize endcard to target resolution
                        endcard_clip = endcard_raw.resize(TARGET_RESOLUTION)
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
                print(f"     Adding endcard at t={endcard_start:.2f}s")
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
                print(f"     Adding endcard at t={endcard_start:.2f}s")
                endcard_positioned = endcard_clip.set_start(endcard_start)
                final_clip = CompositeVideoClip([final_clip, endcard_positioned], size=TARGET_RESOLUTION)
                final_clip = final_clip.set_duration(endcard_start + endcard_clip.duration)
            
            final_clip.fps = get_target_fps(style_config)
        
        total_duration = sum(c.duration for c in video_clips)
        print(f"  ⏱️  Total duration: {total_duration:.2f}s")
        
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
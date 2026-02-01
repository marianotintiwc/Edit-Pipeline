import argparse
import os
import sys
import time
import logging
import json
from datetime import datetime

# Add current directory to path so we can import ugc_pipeline
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ugc_pipeline.clips import process_clips, process_project_clips
from ugc_pipeline.audio import process_audio
from ugc_pipeline.subtitles import generate_subtitles
from ugc_pipeline.style import load_style
from ugc_pipeline.export import export_video

# Setup logging
def setup_logging():
    """Configure logging to both file and console."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file

def print_banner():
    """Print a startup banner."""
    print("\n" + "="*60)
    print("  UGC VIDEO PIPELINE")
    print("  Version 2.0 - Post-processing enabled")
    print("="*60 + "\n")

def print_step(step_num: int, total_steps: int, title: str):
    """Print a formatted step header with progress."""
    progress = f"[{step_num}/{total_steps}]"
    print(f"\n{'─'*60}")
    print(f"  {progress} {title}")
    print(f"{'─'*60}")

def print_status(message: str, status: str = "INFO"):
    """Print a status message with icon."""
    icons = {
        "INFO": "ℹ️ ",
        "OK": "✅",
        "WARN": "⚠️ ",
        "ERROR": "❌",
        "PROGRESS": "⏳",
        "DONE": "🎬"
    }
    icon = icons.get(status, "  ")
    print(f"  {icon} {message}")
    logging.info(f"[{status}] {message}")

def main():
    start_time = time.time()
    log_file = setup_logging()
    print_banner()
    print_status(f"Log file: {log_file}", "INFO")
    
    # Ensure ffmpeg is in PATH for Whisper
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        
        # Add to PATH if not present
        if ffmpeg_dir not in os.environ["PATH"]:
            print_status(f"Adding ffmpeg to PATH: {ffmpeg_dir}", "INFO")
            os.environ["PATH"] += os.pathsep + ffmpeg_dir
    except ImportError:
        print_status("imageio_ffmpeg not found. Whisper might fail if ffmpeg is not in PATH.", "WARN")

    # Configure ImageMagick for MoviePy
    try:
        from moviepy.config import change_settings
        import shutil
        import glob
        
        magick_path = shutil.which("magick")
        
        # If not in PATH, check common installation locations
        if not magick_path:
            common_paths = [
                r"C:\Program Files\ImageMagick-*\magick.exe",
                r"C:\Program Files (x86)\ImageMagick-*\magick.exe",
            ]
            for pattern in common_paths:
                matches = glob.glob(pattern)
                if matches:
                    magick_path = matches[0]
                    # Add ImageMagick directory to PATH
                    magick_dir = os.path.dirname(magick_path)
                    os.environ["PATH"] = magick_dir + os.pathsep + os.environ["PATH"]
                    print_status(f"Found ImageMagick at: {magick_dir}", "INFO")
                    break
        
        if magick_path:
            print_status(f"ImageMagick configured: {os.path.basename(magick_path)}", "OK")
            change_settings({"IMAGEMAGICK_BINARY": magick_path})
        else:
            print_status("'magick' binary not found. TextClip might fail.", "WARN")
    except Exception as e:
        print_status(f"Error configuring ImageMagick: {e}", "ERROR")

    parser = argparse.ArgumentParser(description="UGC Video Pipeline CLI")
    
    parser.add_argument("--clips_config", help="Path to clips JSON config", default=None)
    parser.add_argument("--music", help="Path to background music file", default=None)
    parser.add_argument("--subtitles", help="Path to subtitles SRT file", default=None)
    parser.add_argument("--output", help="Path to output MP4 file", default=None)
    parser.add_argument("--style", help="Path to style JSON config", default=None)
    parser.add_argument("--project", help="Path to UGC project folder (contains scene_1.mp4, scene_2.mp4, broll, scene_3.mp4 and MP3s)", default=None)
    
    args = parser.parse_args()
    
    # Define defaults
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # For batch processing: use clips_config directory as base_dir for subtitles
    # This ensures each project gets its own subtitle file
    if args.clips_config and os.path.exists(args.clips_config):
        project_dir = os.path.dirname(os.path.abspath(args.clips_config))
        # Create subs directory in project folder
        project_subs_dir = os.path.join(project_dir, "subs")
        if not os.path.exists(project_subs_dir):
            os.makedirs(project_subs_dir)
        # Use project_dir for subtitle paths (will be set later)
        batch_mode_dir = project_dir
    else:
        batch_mode_dir = None
    
    print_status("Resolving input paths...", "PROGRESS")
    
    # Clips Config
    if args.clips_config:
        clips_config_path = args.clips_config
    else:
        video_dir = os.path.join(base_dir, "assets", "video")
        p1 = os.path.join(base_dir, "config", "clips.json")
        p2 = os.path.join(base_dir, "config", "clips.sample.json")
        
        has_videos = False
        if os.path.exists(video_dir):
            video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
            for f in os.listdir(video_dir):
                if os.path.splitext(f)[1].lower() in video_extensions:
                    has_videos = True
                    break
        
        if has_videos:
            clips_config_path = video_dir
        else:
            clips_config_path = p1 if os.path.exists(p1) else p2
            
        print_status(f"Clips source: {clips_config_path}", "INFO")

    # Music
    if args.music:
        music_path = args.music
    else:
        music_path = os.path.join(base_dir, "assets", "audio", "music.mp3")
        print_status(f"Music: {os.path.basename(music_path)}", "INFO")

    # Subtitles
    if args.subtitles:
        subtitles_path = args.subtitles
    else:
        subtitles_path = os.path.join(base_dir, "assets", "subs", "subtitles.srt")

    # Output
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(base_dir, "exports", "video_final.mp4")
    print_status(f"Output: {output_path}", "INFO")

    # Style
    if args.style:
        style_path = args.style
    else:
        p1 = os.path.join(base_dir, "config", "style.json")
        p2 = os.path.join(base_dir, "config", "style.sample.json")
        style_path = p1 if os.path.exists(p1) else p2
    print_status(f"Style config: {os.path.basename(style_path)}", "INFO")
    
    TOTAL_STEPS = 5
    
    # ─────────────────────────────────────────────────────────────
    # STEP 1: Load Style
    # ─────────────────────────────────────────────────────────────
    print_step(1, TOTAL_STEPS, "LOADING STYLE CONFIGURATION")
    step_start = time.time()
    style_config = load_style(style_path)
    
    # Report postprocess status
    pp_config = style_config.get("postprocess", {})
    if pp_config.get("enabled", False):
        print_status("Post-processing: ENABLED", "OK")
        print_status(f"  Color grading: {'ON' if pp_config.get('color_grading', {}).get('enabled') else 'OFF'}", "INFO")
        print_status(f"  Grain: {'ON' if pp_config.get('grain', {}).get('enabled') else 'OFF'} (strength: {pp_config.get('grain', {}).get('strength', 0)})", "INFO")
        print_status(f"  Vignette: {'ON' if pp_config.get('vignette', {}).get('enabled') else 'OFF'}", "INFO")
    else:
        print_status("Post-processing: DISABLED", "WARN")
    print_status(f"Step 1 completed in {time.time() - step_start:.1f}s", "OK")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 2: Process Clips
    # ─────────────────────────────────────────────────────────────
    print_step(2, TOTAL_STEPS, "PROCESSING VIDEO CLIPS")
    step_start = time.time()
    try:
        if args.project:
            print_status(f"Project: {os.path.basename(args.project)}", "INFO")
            video_clip = process_project_clips(args.project, style_config)
        else:
            video_clip = process_clips(clips_config_path, style_config)
        print_status(f"Video duration: {video_clip.duration:.2f}s", "OK")
        print_status(f"Step 2 completed in {time.time() - step_start:.1f}s", "OK")
    except Exception as e:
        print_status(f"Error processing clips: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        logging.error(traceback.format_exc())
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────
    # STEP 3: Add Audio
    # ─────────────────────────────────────────────────────────────
    print_step(3, TOTAL_STEPS, "ADDING BACKGROUND AUDIO")
    step_start = time.time()
    video_clip = process_audio(video_clip, music_path)
    print_status(f"Step 3 completed in {time.time() - step_start:.1f}s", "OK")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 4: Generate Subtitles
    # ─────────────────────────────────────────────────────────────
    print_step(4, TOTAL_STEPS, "GENERATING SUBTITLES")
    step_start = time.time()
    
    # Transcription Settings from Style Config
    transcription_config = style_config.get("transcription", {})
    model_name = transcription_config.get("model", "small")
    keywords = transcription_config.get("keywords", None)
    word_level = transcription_config.get("word_level", False)
    max_words = transcription_config.get("max_words_per_segment", 1)
    max_delay = transcription_config.get("max_delay_seconds", 0.5)

    def infer_tap_from_clips_config(path: str) -> bool:
        if not path or not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for clip in data.get("clips", []):
                text = (clip.get("path") or clip.get("url") or "").lower()
                if "tap" in text:
                    return True
        except Exception:
            return False
        return False
    
    # Detect language from project folder GEO code
    transcription_language = "es"  # Default to Spanish

    def infer_geo_from_text(text: str) -> str:
        if not text:
            return None
        t = text.upper()
        if "-MLB" in t:
            return "MLB"
        if "-MLA" in t:
            return "MLA"
        if "-MLM" in t:
            return "MLM"
        return None

    def infer_geo_from_clips_config(path: str) -> str:
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for clip in data.get("clips", []):
                geo = infer_geo_from_text(clip.get("path", ""))
                if geo:
                    return geo
        except Exception:
            return None
        return None

    geo_hint = None
    if args.project:
        project_name = os.path.basename(args.project.rstrip('/'))
        if project_name.endswith("-MLB"):
            transcription_language = "pt"
            print_status("GEO: MLB (Brazil) → Portuguese", "INFO")
        elif project_name.endswith("-MLA"):
            transcription_language = "es"
            print_status("GEO: MLA (Argentina) → Spanish", "INFO")
        elif project_name.endswith("-MLM"):
            transcription_language = "es"
            print_status("GEO: MLM (Mexico) → Spanish", "INFO")
    else:
        geo_hint = (
            infer_geo_from_text(output_path)
            or infer_geo_from_text(clips_config_path)
            or (infer_geo_from_text(os.path.basename(clips_config_path)) if clips_config_path else None)
        )
        if not geo_hint and clips_config_path:
            if os.path.isdir(clips_config_path):
                geo_hint = infer_geo_from_text(os.path.basename(clips_config_path))
            else:
                geo_hint = infer_geo_from_clips_config(clips_config_path)

        if geo_hint == "MLB":
            transcription_language = "pt"
            print_status("GEO: MLB (Brazil) → Portuguese", "INFO")
        elif geo_hint == "MLA":
            transcription_language = "es"
            print_status("GEO: MLA (Argentina) → Spanish", "INFO")
        elif geo_hint == "MLM":
            transcription_language = "es"
            print_status("GEO: MLM (Mexico) → Spanish", "INFO")

    is_tap_job = False
    tap_markers = [
        output_path,
        clips_config_path or "",
        os.path.basename(clips_config_path) if clips_config_path else "",
        keywords or ""
    ]
    if any("tap" in (m or "").lower() for m in tap_markers):
        is_tap_job = True
    elif infer_tap_from_clips_config(clips_config_path or ""):
        is_tap_job = True

    tap_prompt = "Mercado Pago, Tap, contactless, payment, Tap to Pay, pagar con Tap."
    initial_prompt = tap_prompt if is_tap_job else keywords
    
    # Workflow:
    # 1. Check for manual override: assets/subs/subtitles.srt
    # 2. Check for existing auto-generated: assets/subs/auto_generated.srt
    # 3. Generate new: assets/subs/auto_generated.srt
    
    # Use batch_mode_dir (project folder) for batch processing, otherwise base_dir
    subs_base_dir = batch_mode_dir if batch_mode_dir else base_dir
    
    manual_subs_path = os.path.join(subs_base_dir, "subs", "subtitles.srt") if batch_mode_dir else os.path.join(base_dir, "assets", "subs", "subtitles.srt")
    auto_subs_path = os.path.join(subs_base_dir, "subs", "auto_generated.srt") if batch_mode_dir else os.path.join(base_dir, "assets", "subs", "auto_generated.srt")
    
    final_subtitles_path = None
    
    # Always regenerate subtitles for batch processing (when clips_config is provided)
    # This ensures each project gets fresh subtitles from its own audio
    regenerate_subs = True  # Force regeneration for batch processing

    if os.path.exists(manual_subs_path):
        print_status(f"Using manual subtitles: {os.path.basename(manual_subs_path)}", "OK")
        final_subtitles_path = manual_subs_path
    else:
        print_status("Generating subtitles with Whisper...", "PROGRESS")
        try:
            from ugc_pipeline.transcription import transcribe_audio_array
            import numpy as np
            
            print_status("Extracting audio to memory (16kHz mono)...", "PROGRESS")
            
            audio_chunks = []
            for chunk in video_clip.audio.iter_chunks(fps=16000, chunksize=3000):
                audio_chunks.append(chunk)
            
            if not audio_chunks:
                raise ValueError("Could not extract audio chunks from video.")
                
            audio_array = np.vstack(audio_chunks)
            
            if len(audio_array.shape) > 1 and audio_array.shape[1] > 1:
                audio_array = audio_array.mean(axis=1)
            
            print_status(f"Transcribing (model={model_name}, lang={transcription_language})...", "PROGRESS")
            transcribe_audio_array(
                audio_array, 
                auto_subs_path, 
                model_name=model_name, 
                language=transcription_language, 
                initial_prompt=initial_prompt,
                is_tap_job=is_tap_job,
                word_level=word_level,
                max_words=max_words,
                silence_threshold=max_delay
            )
            
            final_subtitles_path = auto_subs_path
            print_status(f"Subtitles saved: {os.path.basename(auto_subs_path)}", "OK")
            
        except ImportError:
            print_status("openai-whisper not installed. Cannot generate subtitles.", "ERROR")
            final_subtitles_path = None
        except Exception as e:
            import traceback
            traceback.print_exc()
            logging.error(traceback.format_exc())
            print_status(f"Subtitle generation failed: {e}", "ERROR")
            print_status("Proceeding without subtitles.", "WARN")
            final_subtitles_path = None
            
    final_clip = generate_subtitles(video_clip, final_subtitles_path, style_config)
    print_status(f"Step 4 completed in {time.time() - step_start:.1f}s", "OK")
    
    # ─────────────────────────────────────────────────────────────
    # STEP 5: Export Final Video
    # ─────────────────────────────────────────────────────────────
    print_step(5, TOTAL_STEPS, "EXPORTING FINAL VIDEO")
    step_start = time.time()
    
    try:
        export_video(final_clip, output_path, style_config)
        print_status(f"Step 5 completed in {time.time() - step_start:.1f}s", "OK")
    except Exception as e:
        print_status(f"Export failed: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        logging.error(traceback.format_exc())
        sys.exit(1)
    
    # ─────────────────────────────────────────────────────────────
    # DONE
    # ─────────────────────────────────────────────────────────────
    total_time = time.time() - start_time
    print("\n" + "="*60)
    print_status(f"PIPELINE COMPLETE!", "DONE")
    print_status(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)", "INFO")
    print_status(f"Output: {output_path}", "INFO")
    
    # File size
    if os.path.exists(output_path):
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print_status(f"File size: {file_size_mb:.2f} MB", "INFO")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()

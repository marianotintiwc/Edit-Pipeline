# Patch for Pillow 10+ compatibility with moviepy 1.x
# ANTIALIAS was removed in Pillow 10, replaced with LANCZOS
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

# UGC Pipeline modules
from ugc_pipeline.clips import process_clips, process_project_clips
from ugc_pipeline.audio import process_audio
from ugc_pipeline.subtitles import generate_subtitles
from ugc_pipeline.style import load_style
from ugc_pipeline.export import export_video
from ugc_pipeline.postprocess import apply_postprocess

# FILM interpolation (optional - requires tensorflow)
try:
    from ugc_pipeline.film_interpolation import (
        interpolate_video,
        interpolate_video_simple,
        apply_film_interpolation,
        FILMInterpolator
    )
    FILM_AVAILABLE = True
except ImportError:
    FILM_AVAILABLE = False

__all__ = [
    # Core pipeline functions
    'process_clips',
    'process_project_clips', 
    'process_audio',
    'generate_subtitles',
    'load_style',
    'export_video',
    'apply_postprocess',
    # FILM interpolation
    'interpolate_video',
    'interpolate_video_simple',
    'apply_film_interpolation',
    'FILMInterpolator',
    'FILM_AVAILABLE'
]

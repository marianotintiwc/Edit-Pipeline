import os
from typing import Dict, Any, Optional
from moviepy.editor import AudioFileClip, VideoFileClip, afx

def process_audio(
    video_clip: VideoFileClip, 
    music_path: str, 
    style_config: Optional[Dict[str, Any]] = None,
    volume: Optional[float] = None
) -> VideoFileClip:
    """
    Adds background music to the video clip.
    Loops the music if necessary, trims to video duration, and adjusts volume.
    
    Args:
        video_clip: Input video clip
        music_path: Path to music file
        style_config: Optional style configuration with audio settings
        volume: Override volume (0.0-1.0). If None, uses style_config or default 0.06
        
    Returns:
        Video clip with music added
    """
    if not os.path.exists(music_path):
        print(f"Warning: Music file not found at {music_path}. Proceeding without music.")
        return video_clip

    print(f"Adding background music: {music_path}")
    
    # Get audio settings from style config or use defaults
    audio_config = {}
    if style_config:
        audio_config = style_config.get("audio", {})
    
    # Determine volume (priority: explicit param > config > default)
    if volume is None:
        volume = audio_config.get("music_volume", 0.06)
    
    # Determine if we should loop
    loop_music = audio_config.get("loop_music", True)
    
    # Load music
    music = AudioFileClip(music_path)
    
    # Loop or trim based on video duration
    if music.duration < video_clip.duration:
        if loop_music:
            music = afx.audio_loop(music, duration=video_clip.duration)
        # If not looping and music is shorter, it will just end early
    else:
        music = music.subclip(0, video_clip.duration)
        
    # Adjust volume
    music = music.volumex(volume)
    
    # Mix with existing audio or set as only audio
    from moviepy.editor import CompositeAudioClip
    
    if video_clip.audio is not None:
        final_audio = CompositeAudioClip([video_clip.audio, music])
    else:
        final_audio = music
        
    video_clip.audio = final_audio
    return video_clip

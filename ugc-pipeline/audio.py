import os
from moviepy.editor import AudioFileClip, VideoFileClip, afx

def process_audio(video_clip: VideoFileClip, music_path: str, volume: float = 0.06) -> VideoFileClip:
    """
    Adds background music to the video clip.
    Loops the music if necessary, trims to video duration, and adjusts volume.
    Default volume 0.06 corresponds to approx -25dB relative to full scale.
    """
    if not os.path.exists(music_path):
        print(f"Warning: Music file not found at {music_path}. Proceeding without music.")
        return video_clip

    print(f"Adding background music: {music_path}")
    
    # Load music
    music = AudioFileClip(music_path)
    
    # Loop if music is shorter than video
    if music.duration < video_clip.duration:
        music = afx.audio_loop(music, duration=video_clip.duration)
    else:
        music = music.subclip(0, video_clip.duration)
        
    # Adjust volume
    music = music.volumex(volume)
    
    # If video has audio, we might want to mix them. 
    # For now, we'll just set the music as the audio if video has none, 
    # or mix them if video has audio (CompositeAudioClip could be used, but set_audio replaces).
    # Let's assume we want to MIX if video has audio, or just SET if not.
    # Actually, standard moviepy set_audio REPLACES. 
    # To mix, we need CompositeAudioClip.
    
    from moviepy.editor import CompositeAudioClip
    
    if video_clip.audio is not None:
        final_audio = CompositeAudioClip([video_clip.audio, music])
    else:
        final_audio = music
        
    video_clip.audio = final_audio
    return video_clip

import whisper
import os
import datetime

def format_timestamp(seconds: float) -> str:
    """Formats seconds into SRT timestamp format (HH:MM:SS,mmm)."""
    td = datetime.timedelta(seconds=seconds)
    # timedelta string is usually H:MM:SS.mmmmmm or [D day[s], ]H:MM:SS.mmmmmm
    # We need to handle it carefully.
    
    total_seconds = int(seconds)
    milliseconds = int((seconds - total_seconds) * 1000)
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

import numpy as np

def transcribe_audio_array(
    audio_array: np.ndarray, 
    output_srt_path: str, 
    model_name: str = "small", 
    language: str = None, 
    initial_prompt: str = None,
    word_level: bool = False,
    max_words: int = 1,
    silence_threshold: float = 0.5
):
    """
    Transcribes audio from a numpy array using Whisper and saves it as an SRT file.
    Expects audio_array to be mono (1D) and 16kHz.
    Uses GPU (CUDA) if available for faster transcription.
    """
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading Whisper model '{model_name}' on {device.upper()}...")
    if device == "cuda":
        print(f"  🚀 GPU: {torch.cuda.get_device_name(0)}")
    model = whisper.load_model(model_name, device=device)
    
    print(f"Transcribing audio data (shape: {audio_array.shape})...")
    # Whisper accepts numpy array directly
    # Ensure it's float32
    audio_data = audio_array.astype(np.float32)
    
    # Transcribe with language option
    options = {}
    if language:
        options["language"] = language
    if initial_prompt:
        options["initial_prompt"] = initial_prompt
    if word_level:
        options["word_timestamps"] = True
        
    result = model.transcribe(audio_data, **options)
    
    final_segments = []
    
    if word_level:
        print(f"Processing word-level timestamps (max_words={max_words}, silence_threshold={silence_threshold})...")
        for seg in result.get("segments", []):
            if "words" in seg:
                words = seg["words"]
                
                # Smart Segmentation Logic
                current_chunk = []
                
                for i, word_obj in enumerate(words):
                    # Check for silence before adding the word (unless it's the first word of chunk)
                    if current_chunk:
                        prev_end = current_chunk[-1]["end"]
                        curr_start = word_obj["start"]
                        
                        # Break if silence > threshold OR max words reached
                        if (curr_start - prev_end > silence_threshold):
                            # print(f"DEBUG: Splitting segment due to silence ({curr_start - prev_end:.2f}s > {silence_threshold}s) at word '{word_obj['word']}'")
                            process_chunk(current_chunk, final_segments)
                            current_chunk = []
                        elif (len(current_chunk) >= max_words):
                             process_chunk(current_chunk, final_segments)
                             current_chunk = []
                            
                    current_chunk.append(word_obj)
                
                # Process remaining chunk
                if current_chunk:
                    process_chunk(current_chunk, final_segments)

            else:
                # Fallback if no words found
                final_segments.append(seg)
    else:
        final_segments = result.get("segments", [])
    
    print(f"Writing {len(final_segments)} subtitles to {output_srt_path}...")
    with open(output_srt_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(final_segments):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = segment["text"].strip()
            
            f.write(f"{i+1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")
            
    print("Transcription complete!")

def process_chunk(chunk, final_segments):
    """Helper to process a chunk of words into karaoke segments"""
    if not chunk: return

    chunk_text_words = [w["word"].strip() for w in chunk]
    
    # For Karaoke effect: one segment per word
    for j, word_obj in enumerate(chunk):
        start = word_obj["start"]
        end = word_obj["end"]
        
        # Construct text with active word marked
        current_words = chunk_text_words.copy()
        current_words[j] = f"[{current_words[j]}]"
        text = " ".join(current_words)
        
        final_segments.append({"start": start, "end": end, "text": text})


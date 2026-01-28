import json
import os
from typing import Optional, Dict, Any

DEFAULT_STYLE = {
    "font": "Arial-Bold",
    "fontsize": 70,
    "color": "white",
    "stroke_color": "black",
    "stroke_width": 0,
    "position": "center_middle",
    "margin_bottom": 200,
    "highlight": {
        "enabled": False,
        "color": "yellow",
        "fontsize_multiplier": 1.1,
        "roundness": 1.5

    },
    "animation": {
        "enabled": False,
        "type": "pop_in",
        "duration": 0.2,
        "scale_start": 0.5,
        "scale_end": 1.0
    },
    "transcription": {
        "model": "small",
        "keywords": "UGC, TikTok, Marketing",
        "word_level": True,
        "max_words_per_segment": 4,
        "max_delay_seconds": 0.5
    },
    "shadow": {
        "enabled": True,
        "color": "black",
        "offset": 4,
        "opacity": 0.5,
        "blur": 3
    },
    "transitions": {
        "enabled": True,
        "type": "slide",
        "direction": "left",
        "duration": 0.02
    }
}

def load_style(path: str) -> Dict[str, Any]:
    """
    Loads style configuration from a JSON file.
    Merges with default style for missing keys.
    """
    if not os.path.exists(path):
        print(f"Warning: Style file {path} not found. Using defaults.")
        return DEFAULT_STYLE.copy()

    try:
        with open(path, 'r', encoding='utf-8') as f:
            user_style = json.load(f)
        
        # Deep merge with defaults (simplified)
        style = DEFAULT_STYLE.copy()
        style.update(user_style)
        
        # Ensure nested dicts are also merged if present in user_style
        if "highlight" in user_style:
            style["highlight"] = DEFAULT_STYLE["highlight"].copy()
            style["highlight"].update(user_style["highlight"])
            
        if "animation" in user_style:
            style["animation"] = DEFAULT_STYLE["animation"].copy()
            style["animation"].update(user_style["animation"])
            
        return style
    except json.JSONDecodeError as e:
        print(f"Error parsing style JSON: {e}. Using defaults.")
        return DEFAULT_STYLE.copy()

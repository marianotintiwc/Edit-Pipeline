#!/usr/bin/env python
"""
FILM Frame Interpolation CLI
Standalone script for Google's FILM model frame interpolation.

Usage:
    python interpolate_video.py --input video.mp4 --target_fps 60 --output interpolated.mp4
    
For integration with UGC pipeline, FILM is automatically available when you set:
    "frame_interpolation": {
        "enabled": true,
        "model": "film",
        "target_fps": 60
    }
in your style.json config.
"""

import sys
import os

# Add the UGC 2.5 directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
ugc_dir = os.path.join(script_dir, "UGC", "UGC 2.5")
if os.path.exists(ugc_dir):
    sys.path.insert(0, ugc_dir)

from ugc_pipeline.film_interpolation import main

if __name__ == "__main__":
    main()

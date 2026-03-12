import pysrt
from moviepy.editor import TextClip, CompositeVideoClip, VideoFileClip, ImageClip, ColorClip
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageFilter, ImageDraw
import numpy as np


def create_rounded_box_clip(
    width: int,
    height: int,
    color_rgb: Tuple[int, int, int],
    radius: int,
    duration: float,
):
    """Create a rounded-rectangle background clip using PIL."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=radius, fill=color_rgb + (255,)
    )
    arr = np.array(img)
    clip = ImageClip(arr).set_duration(duration)
    clip = clip.set_opacity(1.0)
    return clip


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def wrap_text_to_lines(text: str, max_chars_per_line: int) -> str:
    """Wrap text into lines of at most max_chars_per_line characters (break at spaces)."""
    if max_chars_per_line <= 0 or not text or not text.strip():
        return text.strip() if text else ""
    words = text.strip().split()
    lines: List[str] = []
    current: List[str] = []
    current_len = 0
    for w in words:
        need = len(w) + (1 if current else 0)
        if current_len + need <= max_chars_per_line or not current:
            current.append(w)
            current_len += need
        else:
            lines.append(" ".join(current))
            current = [w]
            current_len = len(w)
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def generate_subtitles(video_clip: VideoFileClip, srt_path: str, style_config: Dict[str, Any]) -> CompositeVideoClip:
    """
    Generates animated subtitles and overlays them on the video.
    """
    if not srt_path:
        print("No subtitles file provided, skipping subtitle generation.")
        return video_clip
    
    # Check if ImageMagick is available
    import shutil
    import glob
    import os
    
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
                break
    
    if not magick_path:
        print("Warning: ImageMagick not found. Skipping subtitle generation.")
        print("  Install ImageMagick and add 'magick' to PATH for subtitle support.")
        return video_clip
    
    # Configure MoviePy with the found ImageMagick
    try:
        from moviepy.config import change_settings
        change_settings({"IMAGEMAGICK_BINARY": magick_path})
    except Exception:
        pass
        
    try:
        subs = pysrt.open(srt_path)
    except Exception as e:
        print(f"Error loading subtitles: {e}")
        return video_clip

    print(f"Generating {len(subs)} subtitle clips...")
    
    subtitle_clips = [video_clip] # Start with the base video
    
    # Extract style config
    font = style_config.get("font", "Arial-Bold")
    fontsize = style_config.get("fontsize", 70)
    color = style_config.get("color", "white")
    stroke_color = style_config.get("stroke_color", "black")
    stroke_width = style_config.get("stroke_width", 2)
    position = style_config.get("position", "center_bottom") # simplified handling
    margin_bottom = style_config.get("margin_bottom", 100)
    
    highlight_enabled = style_config.get("highlight", {}).get("enabled", False)
    highlight_color = style_config.get("highlight", {}).get("color", "yellow")
    
    anim_enabled = style_config.get("animation", {}).get("enabled", False)
    anim_type = style_config.get("animation", {}).get("type", "pop_in")
    
    # Shadow config
    shadow_cfg = style_config.get("shadow", {})
    shadow_enabled = shadow_cfg.get("enabled", False)
    shadow_color = shadow_cfg.get("color", "black")
    shadow_offset = shadow_cfg.get("offset", 2)
    shadow_opacity = shadow_cfg.get("opacity", 0.5)
    shadow_blur = shadow_cfg.get("blur", 0)
    
    print(f"DEBUG: Shadow Config - Enabled: {shadow_enabled}, Blur: {shadow_blur}, Opacity: {shadow_opacity}")
    
    video_w, video_h = video_clip.size

    # Safe zone: tiktok (9:16) or uac (16:9) — scale all margins by resolution
    margin_left, margin_right = 0, 0
    margin_top = 0
    safe_width = video_w
    tiktok = style_config.get("tiktok_safe_margins", {})
    uac = style_config.get("uac_16x9_margins", {})
    is_vertical = video_h > video_w
    if is_vertical and tiktok:
        ref_w = tiktok.get("ref_width", 540)
        ref_h = tiktok.get("ref_height", 960)
        sx = video_w / ref_w
        sy = video_h / ref_h
        margin_left = int(tiktok.get("left", 60) * sx)
        margin_right = int(tiktok.get("right", 120) * sx)
        margin_bottom = int(tiktok.get("bottom", 352) * sy)
        margin_top = int(tiktok.get("top", 126) * sy)
        safe_width = video_w - margin_left - margin_right
    elif not is_vertical and uac:
        ref_w = uac.get("ref_width", 1920)
        ref_h = uac.get("ref_height", 1080)
        sx = video_w / ref_w
        sy = video_h / ref_h
        margin_left = int(uac.get("left", 105) * sx)
        margin_right = int(uac.get("right", 516) * sx)
        margin_bottom = int(uac.get("bottom", 504) * sy)
        margin_top = int(uac.get("top", 40) * sy)
        safe_width = video_w - margin_left - margin_right

    # SUPERSAMPLING FACTOR (3x for high quality antialiasing)
    SS = 3.0
    
    fs_render = fontsize * SS
    sw_render = stroke_width * SS
    
    # Animation function factory
    resize_func = None
    if anim_enabled and anim_type == 'pop_in':
        def resize_func(t):
            if t < 0.1:
                return 1.0 + 0.2 * (t / 0.1) # Pop up to 1.2
            elif t < 0.2:
                return 1.2 - 0.2 * ((t - 0.1) / 0.1) # Back to 1.0
            return 1.0

    def build_stroked_text_clip(
        txt: str,
        font_name: str,
        fs: float,
        fill_color: str,
        stroke_col: Optional[str],
        stroke_w: float,
        bg_color: str,
        method: str,
        size=None,
        align: Optional[str] = None
    ) -> TextClip:
        """Render text with a clean stroke by layering stroke + fill."""
        base_kwargs = {
            "txt": txt,
            "font": font_name,
            "fontsize": fs,
            "bg_color": bg_color,
            "method": method,
        }
        if size is not None:
            base_kwargs["size"] = size
        if align is not None:
            base_kwargs["align"] = align

        if not stroke_col or stroke_w <= 0:
            return TextClip(color=fill_color, stroke_color=None, stroke_width=0, **base_kwargs)

        stroke_clip = TextClip(
            color=stroke_col,
            stroke_color=stroke_col,
            stroke_width=stroke_w,
            **base_kwargs
        )
        fill_clip = TextClip(
            color=fill_color,
            stroke_color=None,
            stroke_width=0,
            **base_kwargs
        )
        return CompositeVideoClip([stroke_clip, fill_clip.set_position("center")], size=stroke_clip.size)
    
    # ... (rest of function)

    # Helper to create clip
    def create_part(txt, is_active=False, get_bg_info=False):
        # ImageMagick fails with empty strings
        if not txt or not txt.strip(): 
            return None
        
        c = color
        fs = fs_render # Use Render Font Size
        sc = stroke_color
        sw = sw_render # Use Render Stroke Width
        bg = 'transparent'
        bg_color_val = None
        
        if is_active:
            # Get bg_color from highlight config; text stays base color unless text_color override
            bg_color_val = style_config.get("highlight", {}).get("bg_color", "#FFE600")
            c = style_config.get("highlight", {}).get("text_color", color)
            # Warning: We will render BG separately to allow Shadow in between.
            # So here we keep bg='transparent' for the text clip itself if we are returning info.
            if get_bg_info:
                bg = 'transparent'
            else:
                bg = bg_color_val # Fallback/Legacy
        
        tc = build_stroked_text_clip(
            txt,
            font,
            fs,
            c,
            sc,
            sw,
            bg,
            "label"
        )
        
        if get_bg_info and is_active:
            # We must resize/downsample it first so the caller gets the correct 1x size
            return tc.resize(1.0/SS), bg_color_val
            
        return tc.resize(1.0/SS)

    # For Shadows, logic is different because we want to blur the High Res version first.
            
    # Modify Left/Right/Active/Standard shadow blocks:
    # 1. Create s_clip at High Res (fs_render)
    # 2. Get Frame (High Res)
    # 3. Blur (radius * SS)
    # 4. Create ImageClip
    # 5. Resize(1.0/SS)
    
    # ... I will apply these changes via separate chunks or a full rewrite of the loop body because it's intertwined.
    # Actually, simpler to just replace the whole generate_subtitles function body or large logic blocks.
    # But `replace_file_content` works best with chunks.
    
    # I will replace the initialization block first.

    for sub in subs:
        start_time = sub.start.ordinal / 1000.0
        end_time = sub.end.ordinal / 1000.0
        duration = end_time - start_time
        text = sub.text
        
        # Skip empty subtitles (ImageMagick fails with empty strings)
        if not text or not text.strip():
            continue
        
        # Determine position
        # For 'center_bottom', we calculate x=center, y=height - margin
        pos_x = 'center'
        if position == 'center_bottom':
            pos_y = video_h - margin_bottom - fontsize # Approximate
        elif position == 'center':
            pos_y = (video_h - fontsize) // 2  # Center vertically
        else:
            # Default to center_bottom for any unknown position
            pos_y = video_h - margin_bottom - fontsize

        # Create base text clip
        # Note: TextClip might fail if ImageMagick is not detected correctly.
        # We assume it works.
        
        # Karaoke Logic: Check for [ActiveWord]
        import re
        match = re.search(r'^(.*?)\[(.*?)\](.*?)$', text)
        
        if match and highlight_enabled:
            left_text = match.group(1).strip()
            active_text = match.group(2).strip()
            right_text = match.group(3).strip()
            
            # We need to render 3 clips and composite them.
            # Issue: We need to know the width of each part to position them correctly.
            # MoviePy TextClip doesn't give width easily without rendering.
            # Strategy: Render them, get size, then set position.
            
            clips_to_compose = []
            
            # Re-implementation of create_part with proper return
            def create_part(txt, is_active=False, get_bg_info=False):
                if not txt or not txt.strip(): return None # Simplified

                c = color
                fs = fs_render
                sc = stroke_color
                sw = sw_render
                bg = 'transparent'
                bg_color_val = None
                
                if is_active:
                    highlight_cfg = style_config.get("highlight", {})
                    bg_color_val = highlight_cfg.get("bg_color", "#FFE600")
                    c = highlight_cfg.get("text_color", color)
                    sc = highlight_cfg.get("stroke_color", sc)
                    sw = (highlight_cfg.get("stroke_width", sw_render))
                    if get_bg_info:
                        bg = 'transparent'
                    else:
                        bg = bg_color_val

                tc = build_stroked_text_clip(
                    txt,
                    font,
                    fs,
                    c,
                    sc,
                    sw,
                    bg,
                    "label"
                )
                tc = tc.resize(1.0/SS)
                
                if get_bg_info and is_active:
                    return tc, bg_color_val
                return tc

            left_clip = create_part(left_text)
            active_clip, _ = create_part(active_text, is_active=True, get_bg_info=True) # Unpack mainly for size calculation check if redundant
            # Wait, original code was: active_clip = create_part(..., get_bg_info=False).
            # I must respect original signature usage or update calls.
            # Original call line 142: active_clip = create_part(active_text, is_active=True, get_bg_info=False)
            # So let's stick to original signature return type logic.
            
            # Re-implementation of create_part with proper return
            def create_part(txt, is_active=False, get_bg_info=False):
                if not txt or not txt.strip(): return None # Simplified

                c = color
                fs = fs_render
                sc = stroke_color
                sw = sw_render
                bg = 'transparent'
                bg_color_val = None
                
                if is_active:
                    highlight_cfg = style_config.get("highlight", {})
                    bg_color_val = highlight_cfg.get("bg_color", "#FFE600")
                    c = highlight_cfg.get("text_color", color)
                    sc = highlight_cfg.get("stroke_color", sc)
                    sw = (highlight_cfg.get("stroke_width", sw_render))
                    if get_bg_info:
                        bg = 'transparent'
                    else:
                        bg = bg_color_val

                tc = build_stroked_text_clip(
                    txt,
                    font,
                    fs,
                    c,
                    sc,
                    sw,
                    bg,
                    "label"
                )
                tc = tc.resize(1.0/SS)
                
                if get_bg_info and is_active:
                    return tc, bg_color_val
                return tc

            left_clip = create_part(left_text)
            active_clip = create_part(active_text, is_active=True, get_bg_info=False)
            right_clip = create_part(right_text)
            
            # Calculate total width
            w_left = left_clip.w if left_clip else 0
            w_active = active_clip.w if active_clip else 0
            w_right = right_clip.w if right_clip else 0
            
            total_w = w_left + w_active + w_right
            spacing = 10 # pixels between words
            if left_clip: total_w += spacing
            if right_clip: total_w += spacing
            
            # Center within safe zone; scale down if line overflows
            line_scale = 1.0
            if total_w > safe_width and safe_width > 0:
                line_scale = safe_width / total_w
            if line_scale < 1.0:
                if left_clip:
                    left_clip = left_clip.resize(line_scale)
                if active_clip:
                    active_clip = active_clip.resize(line_scale)
                if right_clip:
                    right_clip = right_clip.resize(line_scale)
                w_left = left_clip.w if left_clip else 0
                w_active = active_clip.w if active_clip else 0
                w_right = right_clip.w if right_clip else 0
                total_w = w_left + w_active + w_right
                if left_clip:
                    total_w += spacing
                if right_clip:
                    total_w += spacing
            start_x = margin_left + (safe_width - total_w) // 2
            current_x = start_x

            # Position and add clips
            # Position and add clips
            if left_clip:
                # Shadow
                # Shadow
                if shadow_enabled:
                     # Render Shadow at High Res
                     s_clip = TextClip(
                        left_text, font=font, fontsize=fs_render, color=shadow_color, 
                        stroke_color=None, stroke_width=0, bg_color='transparent', method='label'
                     )
                     
                     if shadow_blur > 0:
                         try:
                             img = s_clip.get_frame(0)
                             pil_img = Image.fromarray(img).convert('RGBA')
                             
                             if s_clip.mask:
                                 mask = s_clip.mask.get_frame(0)
                                 if mask.dtype != np.uint8:
                                     mask = (mask * 255).astype(np.uint8)
                                 pil_mask = Image.fromarray(mask, mode='L')
                                 pil_img.putalpha(pil_mask)
                             
                             radius = shadow_blur * SS
                             padding = int(radius * 3)
                             
                             new_w = pil_img.width + 2 * padding
                             new_h = pil_img.height + 2 * padding
                             
                             padded_img = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
                             padded_img.paste(pil_img, (padding, padding))
                             
                             blurred_img = padded_img.filter(ImageFilter.GaussianBlur(radius=radius))
                             s_clip = ImageClip(np.array(blurred_img))
                             
                             s_clip = s_clip.resize(1.0/SS)
                             
                             padding_1x = int(padding / SS)
                             pos_x_offset = -padding_1x
                             pos_y_offset = -padding_1x
                         except Exception as e:
                             print(f"Warning: Failed to apply blur to shadow: {e}")
                             s_clip = s_clip.resize(1.0/SS)
                             pos_x_offset = 0
                             pos_y_offset = 0
                     else:
                         s_clip = s_clip.resize(1.0/SS)
                         pos_x_offset = 0
                         pos_y_offset = 0

                     if line_scale < 1.0:
                         s_clip = s_clip.resize(line_scale)
                     effective_opacity = shadow_opacity

                     s_clip = s_clip.set_opacity(effective_opacity)
                     # Apply accumulated offsets
                     s_clip = s_clip.set_start(start_time).set_duration(duration).set_position((current_x + shadow_offset + pos_x_offset, pos_y + shadow_offset + pos_y_offset))
                     clips_to_compose.append(s_clip)

                left_clip = left_clip.set_start(start_time).set_duration(duration).set_position((current_x, pos_y))
                clips_to_compose.append(left_clip)
                current_x += w_left + spacing
                
            if active_clip:
                # Active Logic with Shadow support:
                # 1. Background Box (if needed)
                # 2. Shadow (if enabled)
                # 3. Text
                
                # Re-create active clip asking for bg info (transparent text for bg box overlay)
                active_text_clip, bg_color_hex = create_part(active_text, is_active=True, get_bg_info=True)
                if line_scale < 1.0 and active_text_clip:
                    active_text_clip = active_text_clip.resize(line_scale)

                if active_text_clip:
                    # Calculate dimensions
                    # Add some padding for the box
                    pad_w = 20
                    pad_h = 10
                    act_w, act_h = active_text_clip.size
                    box_w = act_w + pad_w
                    box_h = act_h + pad_h
                    hl_karaoke = style_config.get("highlight", {})
                    box_roundness_k = hl_karaoke.get("box_roundness", hl_karaoke.get("roundness", 0))
                    if isinstance(box_roundness_k, (int, float)) and box_roundness_k > 0:
                        radius_k = min(int(box_roundness_k), min(box_w, box_h) // 2)
                        bg_clip = create_rounded_box_clip(
                            box_w, box_h, hex_to_rgb(bg_color_hex), radius_k, duration
                        )
                    else:
                        bg_clip = ColorClip(size=(box_w, box_h), color=hex_to_rgb(bg_color_hex))
                        bg_clip = bg_clip.set_opacity(1.0)
                    
                    # Center text in box? 
                    # The box position:
                    box_x = current_x - (pad_w // 2)
                    box_y = pos_y - (pad_h // 2)
                    
                    # Animation function apply to ALL parts
                    
                    # Animation
                    if anim_enabled and anim_type == 'pop_in':
                         bg_clip = bg_clip.resize(resize_func)
                         active_text_clip = active_text_clip.resize(resize_func)
                         
                    bg_clip = bg_clip.set_start(start_time).set_duration(duration).set_position((box_x, box_y))
                    clips_to_compose.append(bg_clip)
                    
                    # 2. Shadow
                    if shadow_enabled:
                         s_clip = TextClip(
                            active_text, font=font, fontsize=fs_render, color=shadow_color, 
                            stroke_color=None, stroke_width=0, bg_color='transparent', method='label'
                         )
                         
                         if shadow_blur > 0:
                             # Blur the shadow with padding
                             try:
                                 img = s_clip.get_frame(0)
                                 pil_img = Image.fromarray(img).convert('RGBA')
                                 
                                 if s_clip.mask:
                                     mask = s_clip.mask.get_frame(0)
                                     if mask.dtype != np.uint8:
                                         mask = (mask * 255).astype(np.uint8)
                                     pil_mask = Image.fromarray(mask, mode='L')
                                     pil_img.putalpha(pil_mask)
                                 
                                 radius = shadow_blur * SS
                                 padding = int(radius * 3)
                                 
                                 new_w = pil_img.width + 2 * padding
                                 new_h = pil_img.height + 2 * padding
                                 
                                 padded_img = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
                                 padded_img.paste(pil_img, (padding, padding))
                                 
                                 blurred_img = padded_img.filter(ImageFilter.GaussianBlur(radius=radius))
                                 s_clip = ImageClip(np.array(blurred_img))
                                 
                                 s_clip = s_clip.resize(1.0/SS)
                                 
                                 padding_1x = int(padding / SS)
                                 pos_x_offset = -padding_1x
                                 pos_y_offset = -padding_1x
                             except Exception as e:
                                 print(f"Warning: Failed to apply blur to shadow: {e}")
                                 s_clip = s_clip.resize(1.0/SS)
                                 pos_x_offset = 0
                                 pos_y_offset = 0
                         else:
                             s_clip = s_clip.resize(1.0/SS)
                             pos_x_offset = 0
                             pos_y_offset = 0

                         if line_scale < 1.0:
                             s_clip = s_clip.resize(line_scale)
                         if anim_enabled and anim_type == 'pop_in':
                             s_clip = s_clip.resize(resize_func)
                         # If blur is high, the spread reduces visibility significantly.
                         # We arguably shouldn't reduce opacity further, or at least keep it high.
                         # For the user's specific case (Yellow Box), we need higher opacity.
                         effective_opacity = shadow_opacity 

                         s_clip = s_clip.set_opacity(effective_opacity)
                         # Set position with adjusted offset
                         s_clip = s_clip.set_start(start_time).set_duration(duration).set_position((current_x + shadow_offset + pos_x_offset, pos_y + shadow_offset + pos_y_offset))
                         clips_to_compose.append(s_clip)
                    
                    # 3. Main Text
                    active_text_clip = active_text_clip.set_start(start_time).set_duration(duration).set_position((current_x, pos_y))
                    clips_to_compose.append(active_text_clip)

                    # Advance X based on the text width (ignoring box padding for flow? or include it?)
                    # Usually flow is based on text.
                    current_x += w_active + spacing
                else:
                    # Fallback if creation failed
                    current_x += w_active + spacing
                
            if right_clip:
                # Shadow
                if shadow_enabled:
                     s_clip = TextClip(
                        right_text, font=font, fontsize=fs_render, color=shadow_color, 
                        stroke_color=None, stroke_width=0, bg_color='transparent', method='label'
                     )

                     if shadow_blur > 0:
                         # Blur the shadow with padding to avoid clipping
                         try:
                             img = s_clip.get_frame(0)
                             pil_img = Image.fromarray(img).convert('RGBA')
                             
                             if s_clip.mask:
                                 mask = s_clip.mask.get_frame(0)
                                 if mask.dtype != np.uint8:
                                     mask = (mask * 255).astype(np.uint8)
                                 pil_mask = Image.fromarray(mask, mode='L')
                                 pil_img.putalpha(pil_mask)
                             
                             radius = shadow_blur * SS
                             padding = int(radius * 3)
                             
                             new_w = pil_img.width + 2 * padding
                             new_h = pil_img.height + 2 * padding
                             
                             padded_img = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
                             padded_img.paste(pil_img, (padding, padding))
                             
                             blurred_img = padded_img.filter(ImageFilter.GaussianBlur(radius=radius))
                             s_clip = ImageClip(np.array(blurred_img))
                             
                             s_clip = s_clip.resize(1.0/SS)
                             
                             padding_1x = int(padding / SS)
                             pos_x_offset = -padding_1x
                             pos_y_offset = -padding_1x
                         except Exception as e:
                             print(f"Warning: Failed to apply blur to shadow: {e}")
                             s_clip = s_clip.resize(1.0/SS)
                             pos_x_offset = 0
                             pos_y_offset = 0
                     else:
                         s_clip = s_clip.resize(1.0/SS)
                         pos_x_offset = 0
                         pos_y_offset = 0

                     if line_scale < 1.0:
                         s_clip = s_clip.resize(line_scale)
                     effective_opacity = shadow_opacity

                     s_clip = s_clip.set_opacity(effective_opacity)
                     s_clip = s_clip.set_start(start_time).set_duration(duration).set_position((current_x + shadow_offset + pos_x_offset, pos_y + shadow_offset + pos_y_offset))
                     clips_to_compose.append(s_clip)

                right_clip = right_clip.set_start(start_time).set_duration(duration).set_position((current_x, pos_y))
                clips_to_compose.append(right_clip)
            
            subtitle_clips.extend(clips_to_compose)
            continue # Skip standard rendering

        # Standard rendering (fallback) - center within safe zone
        std_pos_x = margin_left
        # When highlight enabled (e.g. MELI): use highlight colors and draw yellow bg behind phrase (cajita)
        fill_color_std = color
        stroke_color_std = stroke_color
        hl = style_config.get("highlight", {}) if highlight_enabled else {}
        if highlight_enabled:
            fill_color_std = hl.get("text_color", color)
            stroke_color_std = hl.get("stroke_color", stroke_color)

        # Text to render: wrapped when highlight (cajita) so box fits content
        text_for_render = text
        if highlight_enabled:
            max_chars = hl.get("max_chars_per_line", 30)
            text_for_render = wrap_text_to_lines(text, max_chars)

        if shadow_enabled:
             if highlight_enabled:
                 # Content-sized shadow (same as txt_clip for cajita)
                 s_clip = TextClip(
                    text_for_render,
                    font=font,
                    fontsize=fs_render,
                    color=shadow_color,
                    stroke_color=None,
                    stroke_width=0,
                    method='label',
                    bg_color='transparent'
                 )
             else:
                 s_clip = TextClip(
                    text,
                    font=font,
                    fontsize=fs_render,
                    color=shadow_color,
                    stroke_color=None,
                    stroke_width=0,
                    method='caption',
                    size=(safe_width * SS, None),
                    align='center'
                 )
             
             if shadow_blur > 0:
                 # Blur with padding
                 try:
                     img = s_clip.get_frame(0)
                     pil_img = Image.fromarray(img).convert('RGBA')
                     
                     if s_clip.mask:
                         mask = s_clip.mask.get_frame(0)
                         if mask.dtype != np.uint8:
                             mask = (mask * 255).astype(np.uint8)
                         pil_mask = Image.fromarray(mask, mode='L')
                         pil_img.putalpha(pil_mask)
                     

                     
                     radius = shadow_blur * SS
                     padding = int(radius * 3)
                     
                     new_w = pil_img.width + 2 * padding
                     new_h = pil_img.height + 2 * padding
                     
                     padded_img = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
                     padded_img.paste(pil_img, (padding, padding))
                     
                     blurred_img = padded_img.filter(ImageFilter.GaussianBlur(radius=radius))
                     

                     
                     s_clip = ImageClip(np.array(blurred_img))
                     
                     s_clip = s_clip.resize(1.0/SS)
                     
                     # Offset logic (1x)
                     padding_1x = int(padding / SS)
                     pos_x_offset = -padding_1x
                     pos_y_offset = -padding_1x
                 except Exception as e:
                     print(f"Warning: Failed to apply blur to shadow (fallback): {e}")
                     s_clip = s_clip.resize(1.0/SS)
                     pos_x_offset = 0
                     pos_y_offset = 0
             else:
                 s_clip = s_clip.resize(1.0/SS)
                 pos_x_offset = 0
                 pos_y_offset = 0
             
             # Apply animation to shadow
             if anim_enabled and anim_type == 'pop_in':
                 s_clip = s_clip.resize(resize_func)

             effective_opacity = shadow_opacity

             s_clip = s_clip.set_opacity(effective_opacity)
             if highlight_enabled:
                 center_x = margin_left + safe_width // 2
                 text_pos_x_for_shadow = center_x - (s_clip.w // 2)
                 s_pos_x = text_pos_x_for_shadow + shadow_offset + pos_x_offset
             else:
                 s_pos_x = std_pos_x + shadow_offset + pos_x_offset
             s_pos_y = pos_y + shadow_offset + pos_y_offset
             s_clip = s_clip.set_start(start_time).set_duration(duration).set_position((s_pos_x, s_pos_y))
             subtitle_clips.append(s_clip)

        if highlight_enabled:
            # Cajita: content-sized text (method='label', no size)
            txt_clip = build_stroked_text_clip(
                text_for_render,
                font,
                fs_render,
                fill_color_std,
                stroke_color_std,
                sw_render,
                'transparent',
                'label',
                size=None,
                align=None
            )
        else:
            txt_clip = build_stroked_text_clip(
                text,
                font,
                fs_render,
                fill_color_std,
                stroke_color_std,
                sw_render,
                'transparent',
                'caption',
                size=(safe_width * SS, None),
                align='center'
            )
        # Downsample
        txt_clip = txt_clip.resize(1.0/SS)
        # When highlight enabled: draw yellow background behind phrase (cajita - content-sized box)
        if highlight_enabled:
            pad_w, pad_h = 20, 10
            txt_w = getattr(txt_clip, "w", None)
            txt_h = getattr(txt_clip, "h", None)
            center_x = margin_left + safe_width // 2
            text_pos_x = center_x - (int(txt_w) // 2) if txt_w is not None else std_pos_x
            if txt_w is not None and txt_h is not None:
                bg_color_hex = hl.get("bg_color", "#FFE600")
                bg_w = max(1, int(txt_w) + pad_w)
                bg_h = max(1, int(txt_h) + pad_h)
                box_roundness = hl.get("box_roundness", hl.get("roundness", 0))
                if isinstance(box_roundness, (int, float)) and box_roundness > 0:
                    radius = min(int(box_roundness), min(bg_w, bg_h) // 2)
                    bg_clip = create_rounded_box_clip(
                        bg_w, bg_h, hex_to_rgb(bg_color_hex), radius, duration
                    )
                else:
                    try:
                        bg_clip = ColorClip(size=(bg_w, bg_h), color=hex_to_rgb(bg_color_hex), duration=duration)
                    except TypeError:
                        bg_clip = ColorClip(size=(bg_w, bg_h), color=hex_to_rgb(bg_color_hex))
                        bg_clip = bg_clip.set_duration(duration)
                box_pos_x = text_pos_x - pad_w // 2
                bg_clip = bg_clip.set_start(start_time).set_position((box_pos_x, pos_y - pad_h // 2))
                subtitle_clips.append(bg_clip)
            txt_clip = txt_clip.set_start(start_time).set_duration(duration).set_position((text_pos_x, pos_y))
        else:
            txt_clip = txt_clip.set_start(start_time).set_duration(duration).set_position((std_pos_x, pos_y))
        
        # Animation
        if anim_enabled and anim_type == 'pop_in':
            def resize_func_std(t):
                if t < 0.2:
                    return 0.8 + 0.2 * (t / 0.2)
                return 1.0
            
            txt_clip = txt_clip.resize(resize_func_std)

        subtitle_clips.append(txt_clip) 

    final_video = CompositeVideoClip(subtitle_clips)
    return final_video

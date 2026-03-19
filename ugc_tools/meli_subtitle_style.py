"""
MELI flat subtitles: no stroke, fill = stroke_color (see MELI_EDIT_CONFIG_NOTES.md).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def apply_meli_flat_subtitle_style(
    style: Dict[str, Any],
    *,
    fontsize: Optional[int] = None,
    position: Optional[str] = None,
    shadow_enabled: Optional[bool] = None,
) -> None:
    if style.get("stroke_color"):
        style["color"] = style.get("stroke_color")
    style["stroke_width"] = 0
    if isinstance(style.get("highlight"), dict):
        style["highlight"]["stroke_width"] = 0
        if style["highlight"].get("stroke_color"):
            style["highlight"]["text_color"] = style["highlight"]["stroke_color"]
        elif style.get("stroke_color"):
            style["highlight"]["text_color"] = style.get("stroke_color")
    if fontsize is not None:
        style["fontsize"] = int(fontsize)
    if position is not None:
        style["position"] = position
    if shadow_enabled is not None:
        style.setdefault("shadow", {})
        if isinstance(style["shadow"], dict):
            style["shadow"]["enabled"] = bool(shadow_enabled)

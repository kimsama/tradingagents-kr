"""Render an .excalidraw file to PNG using Pillow only — no browser, no network.

Supports the subset of Excalidraw features used in this repo's diagrams:
  - rectangle (with optional rounded corners)
  - ellipse
  - line, arrow (with optional start/end arrowheads)
  - text (free-floating or inside a containerId)
  - solid + dashed stroke styles

Usage:
    python3 render_pillow.py <input.excalidraw> [-o output.png] [-s scale]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

PADDING = 60


def load_font(size: int, scale: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    if not Path(path).exists():
        return ImageFont.load_default()
    return ImageFont.truetype(path, max(8, int(size * scale)))


def compute_bbox(elements: list[dict]) -> tuple[float, float, float, float]:
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for e in elements:
        x = e.get("x", 0); y = e.get("y", 0)
        w = e.get("width", 0); h = e.get("height", 0)
        if e.get("type") in ("arrow", "line") and e.get("points"):
            for px, py in e["points"]:
                min_x = min(min_x, x + px); min_y = min(min_y, y + py)
                max_x = max(max_x, x + px); max_y = max(max_y, y + py)
        else:
            min_x = min(min_x, x); min_y = min(min_y, y)
            max_x = max(max_x, x + abs(w)); max_y = max(max_y, y + abs(h))
    if min_x == float("inf"):
        return (0, 0, 800, 600)
    return (min_x, min_y, max_x, max_y)


def draw_dashed_line(draw, p1, p2, color, width, dash=10, gap=6):
    x1, y1 = p1; x2, y2 = p2
    dx = x2 - x1; dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    pos = 0.0
    on = True
    while pos < length:
        seg = dash if on else gap
        end = min(pos + seg, length)
        if on:
            sx = x1 + ux * pos; sy = y1 + uy * pos
            ex = x1 + ux * end; ey = y1 + uy * end
            draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
        pos = end
        on = not on


def draw_polyline(draw, points, color, width, dashed=False):
    if dashed:
        for i in range(len(points) - 1):
            draw_dashed_line(draw, points[i], points[i + 1], color, width)
    else:
        draw.line(points, fill=color, width=width)


def draw_arrowhead(draw, p_from, p_to, color, stroke_width):
    dx = p_to[0] - p_from[0]
    dy = p_to[1] - p_from[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    head_len = max(10, stroke_width * 5)
    head_w = max(8, stroke_width * 4)
    perp_x, perp_y = -uy, ux
    base_x = p_to[0] - ux * head_len
    base_y = p_to[1] - uy * head_len
    p_left = (base_x + perp_x * head_w / 2, base_y + perp_y * head_w / 2)
    p_right = (base_x - perp_x * head_w / 2, base_y - perp_y * head_w / 2)
    draw.polygon([p_to, p_left, p_right], fill=color)


def render(input_path: Path, output_path: Path, scale: int = 2) -> Path:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    elements = [e for e in data["elements"] if not e.get("isDeleted")]
    bg_color = data.get("appState", {}).get("viewBackgroundColor", "#ffffff")

    min_x, min_y, max_x, max_y = compute_bbox(elements)
    diagram_w = max_x - min_x + PADDING * 2
    diagram_h = max_y - min_y + PADDING * 2
    canvas_w = int(diagram_w * scale)
    canvas_h = int(diagram_h * scale)

    img = Image.new("RGBA", (canvas_w, canvas_h), bg_color)
    draw = ImageDraw.Draw(img)

    def to_px(x, y):
        return (int((x - min_x + PADDING) * scale),
                int((y - min_y + PADDING) * scale))

    elements_by_id = {e["id"]: e for e in elements}

    for e in elements:
        et = e["type"]
        x = e.get("x", 0); y = e.get("y", 0)
        w = e.get("width", 0); h = e.get("height", 0)
        sw_raw = e.get("strokeWidth", 1)
        sw = max(1, int(sw_raw * scale))
        sc = e.get("strokeColor") or "#000000"
        bg = e.get("backgroundColor", "transparent")
        ss = e.get("strokeStyle", "solid")
        dashed = ss in ("dashed", "dotted")
        fill = None if bg in ("transparent", None, "") else bg

        if et == "rectangle":
            x1, y1 = to_px(x, y)
            x2, y2 = to_px(x + w, y + h)
            roundness = e.get("roundness")
            r = int(min(abs(w), abs(h)) * 0.12 * scale) if roundness else 0
            if r > 0:
                draw.rounded_rectangle([x1, y1, x2, y2], radius=r,
                                       fill=fill, outline=sc, width=sw)
            else:
                draw.rectangle([x1, y1, x2, y2],
                               fill=fill, outline=sc, width=sw)

        elif et == "diamond":
            cx = (x + w / 2); cy = (y + h / 2)
            pts_d = [
                to_px(cx, y),
                to_px(x + w, cy),
                to_px(cx, y + h),
                to_px(x, cy),
            ]
            if fill:
                draw.polygon(pts_d, fill=fill)
            draw.polygon(pts_d, outline=sc, width=sw)

        elif et == "ellipse":
            x1, y1 = to_px(x, y)
            x2, y2 = to_px(x + w, y + h)
            draw.ellipse([x1, y1, x2, y2], fill=fill, outline=sc, width=sw)

        elif et in ("line", "arrow"):
            pts = e.get("points") or []
            if len(pts) < 2:
                continue
            abs_pts = [to_px(x + px, y + py) for px, py in pts]
            draw_polyline(draw, abs_pts, sc, sw, dashed=dashed)
            if et == "arrow":
                if e.get("endArrowhead") == "arrow":
                    draw_arrowhead(draw, abs_pts[-2], abs_pts[-1], sc, sw)
                if e.get("startArrowhead") == "arrow":
                    draw_arrowhead(draw, abs_pts[1], abs_pts[0], sc, sw)

        elif et == "text":
            font_size = e.get("fontSize", 16)
            font = load_font(font_size, scale)
            text = e.get("text", "")
            text_align = e.get("textAlign", "left")
            v_align = e.get("verticalAlign", "top")
            color = sc

            container_id = e.get("containerId")
            if container_id and container_id in elements_by_id:
                c = elements_by_id[container_id]
                cx = c.get("x", 0); cy = c.get("y", 0)
                cw = c.get("width", 0); ch = c.get("height", 0)
                box_x1, box_y1 = to_px(cx, cy)
                box_x2, box_y2 = to_px(cx + cw, cy + ch)
                pad = max(4, int(6 * scale))
            else:
                box_x1, box_y1 = to_px(x, y)
                box_x2, box_y2 = to_px(x + w, y + h)
                pad = 0

            lines = text.split("\n")
            line_h = int(font_size * 1.25 * scale)
            total_h = line_h * len(lines)

            if v_align == "middle":
                start_y = box_y1 + ((box_y2 - box_y1) - total_h) // 2
            elif v_align == "bottom":
                start_y = box_y2 - total_h - pad
            else:
                start_y = box_y1 + pad

            for i, line in enumerate(lines):
                try:
                    tw = draw.textlength(line, font=font)
                except Exception:
                    tw = len(line) * font_size * scale * 0.6
                if text_align == "center":
                    tx = box_x1 + ((box_x2 - box_x1) - tw) // 2
                elif text_align == "right":
                    tx = box_x2 - tw - pad
                else:
                    tx = box_x1 + pad
                ty = start_y + i * line_h
                draw.text((tx, ty), line, fill=color, font=font)

    img.save(output_path, "PNG", optimize=True)
    return output_path


def main() -> None:
    p = argparse.ArgumentParser(description="Render .excalidraw to PNG with Pillow")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("-s", "--scale", type=int, default=2)
    args = p.parse_args()
    out = args.output or args.input.with_suffix(".png")
    render(args.input, out, args.scale)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

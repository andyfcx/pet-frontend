"""Framework-agnostic fisheye/SVF logic shared by the customtkinter GUI
(fisheye_view.py) and the Textual TUI (tui/widgets/fisheye_panel.py).
Nothing here imports tkinter, customtkinter, or textual.
"""

import datetime
from typing import Any, Callable, Dict, List, Tuple

from PIL import Image, ImageDraw


def fisheye_shading_at_hour(timeseries: List[Dict[str, Any]], hour_of_day: float) -> Tuple[bool, str]:
    """Return the fisheye shading flag and matched minute for a decimal hour."""
    hour = float(hour_of_day)
    if not 0 <= hour < 24:
        raise ValueError("hour_of_day must be between 0 and 24")
    minute_index = min(1439, int(round(hour * 60)))
    time_str = f"{minute_index // 60:02d}:{minute_index % 60:02d}"
    minute = next(item for item in timeseries if item["Time_Str"] == time_str)
    return bool(minute["Is_Shaded"]), minute["Time_Str"]


def auto_detect_circle(img: Image.Image) -> Dict[str, float]:
    """Mirrors the boundary-detection heuristic in fisheye.py's fisheye_svf()
    (near-white background bounding box). Only used to seed a preview circle;
    the actual SVF computation runs its own detection independently.
    """
    gray = img.convert("L")
    bbox_mask = gray.point(lambda p: 0 if p > 240 else 255)
    bbox = bbox_mask.getbbox()
    if bbox:
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        r = int((min(bbox[2] - bbox[0], bbox[3] - bbox[1]) // 2) * 0.98)
    else:
        cx, cy, r = img.width // 2, img.height // 2, min(img.width, img.height) // 2
    return {"cx": float(cx), "cy": float(cy), "r": float(r)}


def clamp_center(cx: float, cy: float, width: int, height: int) -> Tuple[float, float]:
    return max(0.0, min(float(width), cx)), max(0.0, min(float(height), cy))


def clamp_radius(cx: float, cy: float, r: float, width: int, height: int) -> float:
    max_r = max(5.0, min(cx, cy, width - cx, height - cy))
    return max(5.0, min(r, max_r))


def timeline_geometry(sunup: List[Dict[str, Any]], w: int, h: int, pad: int = 30):
    plot_w = w - 2 * pad
    plot_h = h - 2 * pad
    start_dt = sunup[0]["Datetime"]
    end_dt = sunup[-1]["Datetime"]
    total_seconds = (end_dt - start_dt).total_seconds() or 1
    max_alt = max(e["Solar_Altitude"] for e in sunup) or 1

    def x_of(dt):
        return pad + (dt - start_dt).total_seconds() / total_seconds * plot_w

    def y_of(alt):
        return pad + plot_h - (alt / max_alt) * plot_h

    return x_of, y_of, pad, plot_w, plot_h, start_dt, total_seconds


def parse_interval_dt(text: str, reference_dt: datetime.datetime) -> datetime.datetime:
    naive = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=reference_dt.tzinfo)


def draw_timeline_image(timeseries, intervals, w: int = 900, h: int = 300) -> Image.Image:
    sunup = [e for e in timeseries if e["Solar_Altitude"] > 0]
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    if not sunup:
        draw.text((10, 10), "No sunlight hours", fill="black")
        return img

    x_of, y_of, pad, plot_w, plot_h, start_dt, _ = timeline_geometry(sunup, w, h)

    for iv in intervals:
        x1 = x_of(parse_interval_dt(iv["Start_DateTime"], start_dt))
        x2 = x_of(parse_interval_dt(iv["End_DateTime"], start_dt))
        draw.rectangle([x1, pad, max(x2, x1 + 2), pad + plot_h], fill=(255, 128, 128))

    points = [(x_of(e["Datetime"]), y_of(e["Solar_Altitude"])) for e in sunup]
    draw.line(points, fill=(47, 111, 214), width=2)
    draw.line([(pad, pad + plot_h), (pad + plot_w, pad + plot_h)], fill=(128, 128, 128))
    return img

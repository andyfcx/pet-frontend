import datetime
import inspect
import math
import os
import shutil
import tempfile
import threading
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from tkinter import Canvas, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk

try:
    from tkinterdnd2 import DND_FILES
except Exception:  # pragma: no cover - optional at runtime
    DND_FILES = None

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    RESAMPLE = Image.LANCZOS

CALIB_MAX_DIM = 480
TIMELINE_W = 860
TIMELINE_H = 260
TIMELINE_PAD = 30
THUMB_W = 320
HIGHLIGHT_COLOR = ("#0f9d58", "#4ade80")


class FisheyeView(ctk.CTkFrame):
    """Custom screen for biometeo.fisheye_svf: circle calibration preview + shading timeline.

    Manual circle calibration here is preview-only. fisheye_svf() does not expose
    cx/cy/r overrides, so dragging the circle does not affect the computed SVF.
    """

    def __init__(self, master, bm_module, on_svf: Optional[Callable[[float, str], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.bm = bm_module
        self._on_svf = on_svf

        self.image_path: Optional[str] = None
        self.original_image: Optional[Image.Image] = None
        self.display_scale = 1.0
        self.circle: Dict[str, float] = {"cx": 0, "cy": 0, "r": 0}
        self.auto_circle: Optional[Dict[str, float]] = None
        self._drag_mode: Optional[str] = None

        self._analysis_running = False
        self._analysis_lock = threading.Lock()
        self._last_result: Optional[Dict[str, Any]] = None
        self._timeline_intervals: Dict[str, Dict[str, Any]] = {}
        self._tooltip: Optional[ctk.CTkLabel] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        sig = None
        if self.bm is not None:
            try:
                sig = inspect.signature(self.bm.fisheye_svf)
            except Exception:
                sig = None

        def default_of(name, fallback):
            if sig and name in sig.parameters and sig.parameters[name].default is not inspect._empty:
                return sig.parameters[name].default
            return fallback

        top = ctk.CTkFrame(self)
        top.pack(side="top", fill="x", padx=8, pady=8)

        img_row = ctk.CTkFrame(top)
        img_row.pack(side="top", fill="x")
        ctk.CTkButton(img_row, text="Select Fisheye Photo", command=self._on_select_image).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(img_row, text="Clear", command=self._on_clear_image, width=70).pack(
            side="left", padx=(0, 8)
        )
        self.image_path_label = ctk.CTkLabel(img_row, text="No image selected — you can also drop a photo onto the canvas below")
        self.image_path_label.pack(side="left")

        params_row = ctk.CTkFrame(top)
        params_row.pack(side="top", fill="x", pady=(8, 0))

        ctk.CTkLabel(params_row, text="Date (YYYY-MM-DD)").pack(side="left")
        self.date_entry = ctk.CTkEntry(params_row, width=110)
        self.date_entry.insert(0, datetime.date.today().isoformat())
        self.date_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(params_row, text="Latitude").pack(side="left")
        self.lat_entry = ctk.CTkEntry(params_row, width=90)
        self.lat_entry.insert(0, str(default_of("latitude", 25.055)))
        self.lat_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(params_row, text="Longitude").pack(side="left")
        self.lon_entry = ctk.CTkEntry(params_row, width=90)
        self.lon_entry.insert(0, str(default_of("longitude", 121.611)))
        self.lon_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(params_row, text="Timezone (UTC+)").pack(side="left")
        self.tz_entry = ctk.CTkEntry(params_row, width=60)
        self.tz_entry.insert(0, str(default_of("tz_hours", 8)))
        self.tz_entry.pack(side="left", padx=(4, 12))

        self.run_btn = ctk.CTkButton(params_row, text="Run Analysis", command=self._on_run_analysis)
        self.run_btn.pack(side="left", padx=(12, 0))

        self.progress_bar = ctk.CTkProgressBar(top, mode="indeterminate")
        self.progress_bar.pack(fill="x", pady=(8, 0))
        self.progress_bar.pack_forget()

        self.status_label = ctk.CTkLabel(top, text="Select an image to begin")
        self.status_label.pack(side="top", anchor="w", pady=(4, 0))

        # ---- Calibration ----
        calib_frame = ctk.CTkFrame(self)
        calib_frame.pack(side="top", fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(
            calib_frame,
            text="This calibration is preview-only and does not affect the SVF calculation "
            "(drag the center dot to move, drag the orange handle to resize)",
            text_color="#ff8800",
        ).pack(anchor="w", padx=8, pady=(6, 0))

        calib_body = ctk.CTkFrame(calib_frame)
        calib_body.pack(side="top", fill="x", padx=8, pady=8)

        self.canvas = Canvas(calib_body, width=CALIB_MAX_DIM, height=CALIB_MAX_DIM, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(side="left")
        self.canvas.create_text(
            CALIB_MAX_DIM // 2, CALIB_MAX_DIM // 2, text="No image selected", fill="gray70", tags="placeholder"
        )
        if DND_FILES is not None:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        circle_controls = ctk.CTkFrame(calib_body)
        circle_controls.pack(side="left", fill="y", padx=(12, 0))

        ctk.CTkLabel(circle_controls, text="Center X").pack(anchor="w")
        self.cx_entry = ctk.CTkEntry(circle_controls, width=100)
        self.cx_entry.pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(circle_controls, text="Center Y").pack(anchor="w")
        self.cy_entry = ctk.CTkEntry(circle_controls, width=100)
        self.cy_entry.pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(circle_controls, text="Radius R").pack(anchor="w")
        self.r_entry = ctk.CTkEntry(circle_controls, width=100)
        self.r_entry.pack(anchor="w", pady=(0, 6))

        ctk.CTkButton(circle_controls, text="Apply Values", command=self._on_apply_circle_values).pack(
            fill="x", pady=(6, 4)
        )
        ctk.CTkButton(circle_controls, text="Reset to Auto-Detect", command=self._on_reset_circle).pack(fill="x")

        # ---- Results ----
        results_frame = ctk.CTkFrame(self)
        results_frame.pack(side="top", fill="x", padx=8, pady=(0, 8))

        images_row = ctk.CTkFrame(results_frame)
        images_row.pack(side="top", fill="x", padx=8, pady=8)
        self.mask_image_label = ctk.CTkLabel(
            images_row, text="Sky mask (shown after analysis)", width=THUMB_W, height=THUMB_W
        )
        self.mask_image_label.pack(side="left", padx=(0, 8))
        self.sunpath_image_label = ctk.CTkLabel(
            images_row, text="Sun-path overlay (shown after analysis)", width=THUMB_W, height=THUMB_W
        )
        self.sunpath_image_label.pack(side="left")

        self.svf_value_label = ctk.CTkLabel(results_frame, text="SVF: -", font=ctk.CTkFont(size=16, weight="bold"))
        self.svf_value_label.pack(side="top", anchor="w", padx=8)
        self._svf_default_color = self.svf_value_label.cget("text_color")
        self.summary_label = ctk.CTkLabel(results_frame, text="")
        self.summary_label.pack(side="top", anchor="w", padx=8, pady=(0, 8))

        ctk.CTkLabel(results_frame, text="Daily Shading Timeline").pack(side="top", anchor="w", padx=8)
        self.timeline_canvas = Canvas(
            results_frame, width=TIMELINE_W, height=TIMELINE_H, bg="white", highlightthickness=1,
            highlightbackground="gray70",
        )
        self.timeline_canvas.pack(side="top", padx=8, pady=8)

        export_row = ctk.CTkFrame(results_frame)
        export_row.pack(side="top", fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(export_row, text="Export Shading Intervals CSV", command=self._on_export_csv).pack(side="left")
        ctk.CTkButton(export_row, text="Export Timeline Image", command=self._on_export_timeline_image).pack(
            side="left", padx=(8, 0)
        )

    # ------------------------------------------------------------------
    # Image loading + auto circle detection
    # ------------------------------------------------------------------
    def _on_select_image(self):
        path = filedialog.askopenfilename(
            title="Select Fisheye Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_image(path)

    def _on_drop(self, event):
        data = event.data
        if not data:
            return
        parts = self._parse_dnd_paths(data)
        if not parts:
            return
        path = parts[0]
        if path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
            self._load_image(path)

    @staticmethod
    def _parse_dnd_paths(data: str) -> List[str]:
        parts = []
        buf = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                buf = ""
            elif ch == "}":
                in_brace = False
                parts.append(buf)
                buf = ""
            elif ch == " " and not in_brace:
                if buf:
                    parts.append(buf)
                    buf = ""
            else:
                buf += ch
        if buf:
            parts.append(buf)
        return parts

    def _load_image(self, path: str):
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Failed to Load Image", str(e))
            return
        self.image_path = path
        self.original_image = img
        self.image_path_label.configure(text=path)

        scale = min(CALIB_MAX_DIM / img.width, CALIB_MAX_DIM / img.height, 1.0)
        self.display_scale = scale
        disp_w, disp_h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        self.canvas.configure(width=disp_w, height=disp_h)
        self._tk_image = ImageTk.PhotoImage(img.resize((disp_w, disp_h), RESAMPLE))

        self._auto_detect_circle()
        self.circle = dict(self.auto_circle)
        self._render_calibration_canvas()
        self._update_circle_labels()

    def _on_clear_image(self):
        self.image_path = None
        self.original_image = None
        self.auto_circle = None
        self.circle = {"cx": 0, "cy": 0, "r": 0}
        self._drag_mode = None
        self._last_result = None
        self._timeline_intervals = {}
        self._tk_image = None

        self.image_path_label.configure(text="No image selected — you can also drop a photo onto the canvas below")

        self.canvas.configure(width=CALIB_MAX_DIM, height=CALIB_MAX_DIM)
        self.canvas.delete("all")
        self.canvas.create_text(
            CALIB_MAX_DIM // 2, CALIB_MAX_DIM // 2, text="No image selected", fill="gray70", tags="placeholder"
        )

        for entry in (self.cx_entry, self.cy_entry, self.r_entry):
            entry.delete(0, "end")

        # CTkLabel.configure(image=None) leaves the underlying tkinter widget's
        # own -image option pointing at the (about to be garbage-collected)
        # PhotoImage, causing a later "image ... doesn't exist" TclError on
        # redraw. Clear that raw option directly to avoid the dangling reference.
        self.mask_image_label.configure(image=None, text="Sky mask (shown after analysis)")
        self.mask_image_label._label.configure(image="")
        self.mask_image_label.image = None
        self.sunpath_image_label.configure(image=None, text="Sun-path overlay (shown after analysis)")
        self.sunpath_image_label._label.configure(image="")
        self.sunpath_image_label.image = None
        self.svf_value_label.configure(text="SVF: -", text_color=self._svf_default_color)
        self.summary_label.configure(text="")
        self.timeline_canvas.delete("all")
        self.status_label.configure(text="Select an image to begin")

    def _auto_detect_circle(self):
        # Mirrors the boundary-detection heuristic in fisheye.py's fisheye_svf()
        # (near-white background bounding box). Only used to seed the preview
        # circle here; the actual SVF computation still runs its own detection.
        img = self.original_image
        gray = img.convert("L")
        bbox_mask = gray.point(lambda p: 0 if p > 240 else 255)
        bbox = bbox_mask.getbbox()
        if bbox:
            cx = (bbox[0] + bbox[2]) // 2
            cy = (bbox[1] + bbox[3]) // 2
            r = int((min(bbox[2] - bbox[0], bbox[3] - bbox[1]) // 2) * 0.98)
        else:
            cx, cy, r = img.width // 2, img.height // 2, min(img.width, img.height) // 2
        self.auto_circle = {"cx": float(cx), "cy": float(cy), "r": float(r)}

    # ------------------------------------------------------------------
    # Circle overlay interaction
    # ------------------------------------------------------------------
    def _render_calibration_canvas(self):
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_image)
        self._draw_circle_overlay()

    def _draw_circle_overlay(self):
        self.canvas.delete("circle_overlay")
        cx, cy, r = self.circle["cx"], self.circle["cy"], self.circle["r"]
        s = self.display_scale
        dcx, dcy, dr = cx * s, cy * s, r * s

        self.canvas.create_oval(
            dcx - dr, dcy - dr, dcx + dr, dcy + dr, outline="#00ffcc", width=2,
            tags=("circle_overlay", "circle_body"),
        )
        self.canvas.create_oval(
            dcx - 4, dcy - 4, dcx + 4, dcy + 4, fill="#00ffcc", outline="",
            tags=("circle_overlay", "circle_center"),
        )
        hx, hy = dcx + dr, dcy
        self.canvas.create_rectangle(
            hx - 5, hy - 5, hx + 5, hy + 5, fill="#ff6600", outline="",
            tags=("circle_overlay", "circle_handle"),
        )

        self.canvas.tag_bind("circle_center", "<ButtonPress-1>", lambda e: self._start_drag("move"))
        self.canvas.tag_bind("circle_body", "<ButtonPress-1>", lambda e: self._start_drag("move"))
        self.canvas.tag_bind("circle_handle", "<ButtonPress-1>", lambda e: self._start_drag("resize"))

    def _start_drag(self, mode: str):
        if self.original_image is None:
            return
        self._drag_mode = mode
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)

    def _on_drag(self, event):
        s = self.display_scale
        orig_x, orig_y = event.x / s, event.y / s
        if self._drag_mode == "move":
            cx, cy = self._clamp_center(orig_x, orig_y, self.circle["r"])
            self.circle["cx"], self.circle["cy"] = cx, cy
        elif self._drag_mode == "resize":
            dx = orig_x - self.circle["cx"]
            dy = orig_y - self.circle["cy"]
            r = math.hypot(dx, dy)
            self.circle["r"] = self._clamp_radius(self.circle["cx"], self.circle["cy"], r)
        self._draw_circle_overlay()
        self._update_circle_labels()

    def _end_drag(self, event):
        self._drag_mode = None
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")

    def _clamp_center(self, cx, cy, r):
        w, h = self.original_image.width, self.original_image.height
        return max(0.0, min(float(w), cx)), max(0.0, min(float(h), cy))

    def _clamp_radius(self, cx, cy, r):
        w, h = self.original_image.width, self.original_image.height
        max_r = max(5.0, min(cx, cy, w - cx, h - cy))
        return max(5.0, min(r, max_r))

    def _update_circle_labels(self):
        for entry, key in ((self.cx_entry, "cx"), (self.cy_entry, "cy"), (self.r_entry, "r")):
            entry.delete(0, "end")
            entry.insert(0, f"{self.circle[key]:.1f}")

    def _on_apply_circle_values(self):
        if self.original_image is None:
            messagebox.showinfo("No Image Selected", "Please select an image first")
            return
        try:
            cx = float(self.cx_entry.get())
            cy = float(self.cy_entry.get())
            r = float(self.r_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Center/radius must be numbers")
            return
        cx, cy = self._clamp_center(cx, cy, r)
        r = self._clamp_radius(cx, cy, r)
        self.circle = {"cx": cx, "cy": cy, "r": r}
        self._draw_circle_overlay()
        self._update_circle_labels()

    def _on_reset_circle(self):
        if self.auto_circle is None:
            return
        self.circle = dict(self.auto_circle)
        self._draw_circle_overlay()
        self._update_circle_labels()

    # ------------------------------------------------------------------
    # Analysis run
    # ------------------------------------------------------------------
    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for w in (self.run_btn, self.date_entry, self.lat_entry, self.lon_entry, self.tz_entry):
            try:
                w.configure(state=state)
            except Exception:
                pass

    def _on_run_analysis(self):
        if self.bm is None:
            messagebox.showerror("Cannot Run", "The biometeo package failed to load")
            return
        if self._analysis_running:
            return
        if self.image_path is None:
            messagebox.showinfo("No Image Selected", "Please select an image first")
            return
        try:
            target_date = datetime.datetime.strptime(self.date_entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Invalid Date Format", "Please use the YYYY-MM-DD format")
            return
        try:
            lat = float(self.lat_entry.get())
            lon = float(self.lon_entry.get())
            tz = float(self.tz_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Latitude/Longitude/Timezone must be numbers")
            return

        self._analysis_running = True
        self._set_controls_enabled(False)
        self.progress_bar.pack(fill="x", pady=(8, 0))
        self.progress_bar.start()
        self.status_label.configure(text="Analyzing…")

        thread = threading.Thread(
            target=self._run_analysis_worker, args=(self.image_path, target_date, lat, lon, tz), daemon=True
        )
        thread.start()

    def _run_analysis_worker(self, image_path, target_date, lat, lon, tz):
        result: Optional[Dict[str, Any]] = None
        error: Optional[Exception] = None
        with self._analysis_lock:
            prev_cwd = os.getcwd()
            tmp_dir = tempfile.mkdtemp(prefix="biometeo_fisheye_")
            try:
                os.chdir(tmp_dir)
                svf, timeseries = self.bm.fisheye_svf(
                    image_path, target_date, latitude=lat, longitude=lon, tz_hours=tz, draw_and_save=True
                )
                intervals = self.bm.extract_shading_intervals(timeseries)
                date_tag = target_date.strftime("%Y%m%d")
                mask_path = os.path.join(tmp_dir, f"auto_generated_sky_mask_{date_tag}.png")
                sunpath_path = os.path.join(tmp_dir, f"integrated_sunpath_pillow_{date_tag}.jpg")
                mask_img = Image.open(mask_path).convert("RGB")
                mask_img.load()
                sunpath_img = Image.open(sunpath_path).convert("RGB")
                sunpath_img.load()
                result = {
                    "svf": svf,
                    "timeseries": timeseries,
                    "intervals": intervals,
                    "mask_img": mask_img,
                    "sunpath_img": sunpath_img,
                    "date_str": target_date.strftime("%Y-%m-%d"),
                }
            except Exception as e:
                error = e
            finally:
                os.chdir(prev_cwd)
                shutil.rmtree(tmp_dir, ignore_errors=True)
        self.after(0, lambda: self._on_analysis_done(result, error))

    def _on_analysis_done(self, result, error):
        self._analysis_running = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self._set_controls_enabled(True)
        if error is not None:
            messagebox.showerror("Analysis Failed", str(error))
            self.status_label.configure(text="An error occurred")
            return
        self._last_result = result
        self._render_results(result)
        if self._on_svf is not None:
            self._on_svf(result["svf"], self.image_path)
            self.status_label.configure(
                text=f"Done — SVF = {result['svf']:.4f} filled into Tmrt_calc's OmegaF field"
            )
        else:
            self.status_label.configure(text="Done")

    # ------------------------------------------------------------------
    # Results rendering
    # ------------------------------------------------------------------
    def _render_results(self, result: Dict[str, Any]):
        for img, label in ((result["mask_img"], self.mask_image_label), (result["sunpath_img"], self.sunpath_image_label)):
            w, h = img.size
            scale = THUMB_W / w
            disp = img.resize((THUMB_W, max(1, int(h * scale))), RESAMPLE)
            ctk_img = ctk.CTkImage(light_image=disp, dark_image=disp, size=disp.size)
            label.configure(image=ctk_img, text="")
            label.image = ctk_img  # keep a reference so it is not garbage-collected

        self.svf_value_label.configure(text=f"SVF: {result['svf']:.4f}", text_color=HIGHLIGHT_COLOR)
        shaded_minutes = sum(iv["Duration_Mins"] for iv in result["intervals"])
        sunup_minutes = sum(1 for e in result["timeseries"] if e["Solar_Altitude"] > 0)
        visible_minutes = max(0, sunup_minutes - shaded_minutes)
        self.summary_label.configure(
            text=f"Sunlight: {sunup_minutes} min | Shaded: {shaded_minutes} min | Visible: {visible_minutes} min"
        )

        self._render_timeline(result["timeseries"], result["intervals"])

    @staticmethod
    def _timeline_geometry(sunup: List[Dict[str, Any]], w: int, h: int, pad: int = TIMELINE_PAD):
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

    def _render_timeline(self, timeseries, intervals):
        self.timeline_canvas.delete("all")
        self._timeline_intervals = {}
        sunup = [e for e in timeseries if e["Solar_Altitude"] > 0]
        if not sunup:
            self.timeline_canvas.create_text(10, 10, anchor="nw", text="No sunlight hours on this day")
            return

        x_of, y_of, pad, plot_w, plot_h, start_dt, _ = self._timeline_geometry(sunup, TIMELINE_W, TIMELINE_H)

        for idx, iv in enumerate(intervals):
            x1 = x_of(self._parse_interval_dt(iv["Start_DateTime"], start_dt))
            x2 = x_of(self._parse_interval_dt(iv["End_DateTime"], start_dt))
            tag = f"interval_{idx}"
            self.timeline_canvas.create_rectangle(
                x1, pad, max(x2, x1 + 2), pad + plot_h, fill="#ff8080", outline="", tags=("interval", tag)
            )
            self._timeline_intervals[tag] = iv
            self.timeline_canvas.tag_bind(tag, "<Enter>", lambda e, t=tag: self._show_tooltip(e, t))
            self.timeline_canvas.tag_bind(tag, "<Leave>", lambda e: self._hide_tooltip())

        points = []
        for e in sunup:
            points.extend([x_of(e["Datetime"]), y_of(e["Solar_Altitude"])])
        if len(points) >= 4:
            self.timeline_canvas.create_line(*points, fill="#2f6fd6", width=2, smooth=True)

        self.timeline_canvas.create_line(pad, pad + plot_h, pad + plot_w, pad + plot_h, fill="gray50")

        tick_count = 6
        total_seconds = (sunup[-1]["Datetime"] - start_dt).total_seconds() or 1
        for i in range(tick_count + 1):
            frac = i / tick_count
            dt = start_dt + datetime.timedelta(seconds=total_seconds * frac)
            x = x_of(dt)
            self.timeline_canvas.create_line(x, pad + plot_h, x, pad + plot_h + 4, fill="gray50")
            self.timeline_canvas.create_text(x, pad + plot_h + 14, text=dt.strftime("%H:%M"), font=("TkDefaultFont", 9))

    @staticmethod
    def _parse_interval_dt(text: str, reference_dt: datetime.datetime) -> datetime.datetime:
        naive = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
        return naive.replace(tzinfo=reference_dt.tzinfo)

    def _show_tooltip(self, event, tag):
        iv = self._timeline_intervals.get(tag)
        if not iv:
            return
        text = f"{iv['Start_DateTime']} → {iv['End_DateTime']}\n{iv['Duration_Mins']} min | SVF {iv['SVF']}"
        if self._tooltip is None:
            self._tooltip = ctk.CTkLabel(self, text=text, fg_color="#222222", text_color="white", corner_radius=4)
        else:
            self._tooltip.configure(text=text)
        x = self.timeline_canvas.winfo_x() + event.x + 12
        y = self.timeline_canvas.winfo_y() + event.y + 12
        self._tooltip.place(x=x, y=y)

    def _hide_tooltip(self):
        if self._tooltip is not None:
            self._tooltip.place_forget()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _on_export_csv(self):
        if self.bm is None or self._last_result is None:
            messagebox.showinfo("No Results", "Please run an analysis first")
            return
        path = filedialog.asksaveasfilename(
            title="Export Shading Intervals CSV", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.bm.save_shading_intervals_csv(
                self._last_result["intervals"], path, self._last_result["svf"], self._last_result["date_str"]
            )
            self.status_label.configure(text=f"CSV exported to {path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _on_export_timeline_image(self):
        if self._last_result is None:
            messagebox.showinfo("No Results", "Please run an analysis first")
            return
        path = filedialog.asksaveasfilename(
            title="Export Timeline Image", defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            img = self._draw_timeline_image(self._last_result["timeseries"], self._last_result["intervals"])
            img.save(path)
            self.status_label.configure(text=f"Timeline image exported to {path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _draw_timeline_image(self, timeseries, intervals, w=900, h=300) -> Image.Image:
        sunup = [e for e in timeseries if e["Solar_Altitude"] > 0]
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        if not sunup:
            draw.text((10, 10), "No sunlight hours", fill="black")
            return img

        x_of, y_of, pad, plot_w, plot_h, start_dt, _ = self._timeline_geometry(sunup, w, h)

        for iv in intervals:
            x1 = x_of(self._parse_interval_dt(iv["Start_DateTime"], start_dt))
            x2 = x_of(self._parse_interval_dt(iv["End_DateTime"], start_dt))
            draw.rectangle([x1, pad, max(x2, x1 + 2), pad + plot_h], fill=(255, 128, 128))

        points = [(x_of(e["Datetime"]), y_of(e["Solar_Altitude"])) for e in sunup]
        draw.line(points, fill=(47, 111, 214), width=2)
        draw.line([(pad, pad + plot_h), (pad + plot_w, pad + plot_h)], fill=(128, 128, 128))
        return img

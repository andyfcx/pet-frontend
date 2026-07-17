"""Fisheye photo -> Sky View Factor sub-panel.

Mirrors fisheye_view.py's FisheyeView (customtkinter) but built from Textual
widgets. Circle calibration is numeric-only (no draggable canvas overlay) per
the reduced-scope decision for the terminal UI; it remains preview-only and
does not feed into the actual bm.fisheye_svf() computation, exactly as in the
original.
"""

import datetime
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image
from textual import work
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Input, Label, LoadingIndicator, Static
from textual_fspicker import FileOpen, FileSave, Filters
from textual_image.widget import AutoImage
from textual_plotext import PlotextPlot

from biometeo_frontend import core_fisheye
from biometeo_frontend.core import bm

THUMB_HEIGHT = 16


class TimelineChart(PlotextPlot):
    """Solar-altitude curve with shaded intervals highlighted, via plotext."""

    def plot_timeline(self, timeseries: List[Dict[str, Any]], intervals: List[Dict[str, Any]]) -> None:
        sunup = [e for e in timeseries if e["Solar_Altitude"] > 0]
        self.plt.clear_data()
        self.plt.clear_figure()
        if not sunup:
            self.refresh()
            return

        x_labels = [e["Time_Str"] for e in sunup]
        altitudes = [e["Solar_Altitude"] for e in sunup]
        x = list(range(len(sunup)))

        shaded_x = [xi for xi, e in zip(x, sunup) if e["Is_Shaded"]]
        shaded_y = [e["Solar_Altitude"] for e in sunup if e["Is_Shaded"]]

        self.plt.plot(x, altitudes, marker="braille", color="blue")
        if shaded_x:
            self.plt.scatter(shaded_x, shaded_y, marker="fhd", color="red")

        tick_count = min(6, len(x_labels))
        step = max(1, len(x_labels) // max(1, tick_count))
        self.plt.xticks(x[::step], x_labels[::step])
        self.plt.title("Daily Shading Timeline (red = shaded)")
        self.refresh()


class FisheyePanel(Vertical):
    """Photo -> SVF + shading analysis panel embedded above the Tmrt_calc form."""

    DEFAULT_CSS = """
    FisheyePanel {
        height: auto;
        padding: 1;
    }
    FisheyePanel .row {
        height: auto;
        margin-bottom: 1;
    }
    FisheyePanel .warning-note {
        color: $warning;
        margin-bottom: 1;
    }
    FisheyePanel .svf-value {
        text-style: bold;
        margin-top: 1;
    }
    FisheyePanel .svf-value-filled {
        color: $success;
    }
    FisheyePanel Input {
        width: 16;
        margin-right: 1;
    }
    FisheyePanel AutoImage {
        width: 1fr;
        height: 12;
        border: round $primary-background-lighten-2;
        margin-right: 1;
    }
    FisheyePanel TimelineChart {
        height: 14;
        margin-top: 1;
    }
    FisheyePanel DataTable {
        height: 8;
        margin-top: 1;
    }
    """

    class AnalysisComplete(Message):
        def __init__(self, svf: float, image_path: str, timeseries: List[Dict[str, Any]]) -> None:
            self.svf = svf
            self.image_path = image_path
            self.timeseries = timeseries
            super().__init__()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.image_path: Optional[str] = None
        self.original_image: Optional[Image.Image] = None
        self.circle: Dict[str, float] = {"cx": 0, "cy": 0, "r": 0}
        self.auto_circle: Optional[Dict[str, float]] = None
        self.last_result: Optional[Dict[str, Any]] = None

    def compose(self):
        with Horizontal(classes="row"):
            yield Button("Select Fisheye Photo", id="fisheye-select-btn")
            yield Button("Clear", id="fisheye-clear-btn")
            yield Label("No image selected", id="fisheye-path-label")

        with Horizontal(classes="row"):
            yield Label("Date (YYYY-MM-DD)")
            yield Input(value=datetime.date.today().isoformat(), id="fisheye-date-input")
            yield Label("Latitude")
            yield Input(value="25.055", id="fisheye-lat-input")
            yield Label("Longitude")
            yield Input(value="121.611", id="fisheye-lon-input")
            yield Label("Timezone (UTC+)")
            yield Input(value="8", id="fisheye-tz-input")
            yield Button("Run Analysis", id="fisheye-run-btn", variant="primary")

        yield LoadingIndicator(id="fisheye-loading")
        yield Label("Select an image to begin", id="fisheye-status-label")

        yield Label(
            "Calibration is preview-only and does not affect the SVF calculation.",
            classes="warning-note",
        )
        with Horizontal(classes="row"):
            yield Label("Center X")
            yield Input(id="fisheye-cx-input")
            yield Label("Center Y")
            yield Input(id="fisheye-cy-input")
            yield Label("Radius R")
            yield Input(id="fisheye-r-input")
            yield Button("Apply Values", id="fisheye-apply-circle-btn")
            yield Button("Reset to Auto-Detect", id="fisheye-reset-circle-btn")

        with Horizontal(classes="row"):
            yield AutoImage(id="fisheye-photo-image")
            yield AutoImage(id="fisheye-mask-image")
            yield AutoImage(id="fisheye-sunpath-image")

        yield Label("SVF: -", id="fisheye-svf-label", classes="svf-value")
        yield Label("", id="fisheye-summary-label")
        yield TimelineChart(id="fisheye-timeline-chart")
        yield DataTable(id="fisheye-intervals-table")

        with Horizontal(classes="row"):
            yield Button("Export Shading Intervals CSV", id="fisheye-export-csv-btn")
            yield Button("Export Timeline Image", id="fisheye-export-png-btn")

    def on_mount(self) -> None:
        self.query_one("#fisheye-loading", LoadingIndicator).display = False
        table = self.query_one("#fisheye-intervals-table", DataTable)
        table.add_columns("Start", "End", "Duration (min)", "SVF")

    # ------------------------------------------------------------------
    # Image selection
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "fisheye-select-btn":
            self._open_image_picker()
        elif button_id == "fisheye-clear-btn":
            self._clear_image()
        elif button_id == "fisheye-run-btn":
            self._start_analysis()
        elif button_id == "fisheye-apply-circle-btn":
            self._apply_circle_values()
        elif button_id == "fisheye-reset-circle-btn":
            self._reset_circle()
        elif button_id == "fisheye-export-csv-btn":
            self._export_csv()
        elif button_id == "fisheye-export-png-btn":
            self._export_timeline_image()

    def _open_image_picker(self) -> None:
        filters = Filters(
            ("Image files", lambda p: p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")),
        )
        self.app.push_screen(FileOpen(title="Select Fisheye Photo", filters=filters), self._on_image_picked)

    def _on_image_picked(self, path: Optional[Path]) -> None:
        if path is None:
            return
        self._load_image(str(path))

    def _load_image(self, path: str) -> None:
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            self.app.notify(f"Failed to load image: {e}", severity="error")
            return
        self.image_path = path
        self.original_image = img
        self.query_one("#fisheye-path-label", Label).update(path)
        self.query_one("#fisheye-photo-image", AutoImage).image = img

        self.auto_circle = core_fisheye.auto_detect_circle(img)
        self.circle = dict(self.auto_circle)
        self._update_circle_inputs()

    def _clear_image(self) -> None:
        self.image_path = None
        self.original_image = None
        self.auto_circle = None
        self.circle = {"cx": 0, "cy": 0, "r": 0}
        self.last_result = None

        self.query_one("#fisheye-path-label", Label).update("No image selected")
        self.query_one("#fisheye-photo-image", AutoImage).image = None
        self.query_one("#fisheye-mask-image", AutoImage).image = None
        self.query_one("#fisheye-sunpath-image", AutoImage).image = None
        for iid in ("#fisheye-cx-input", "#fisheye-cy-input", "#fisheye-r-input"):
            self.query_one(iid, Input).value = ""
        svf_label = self.query_one("#fisheye-svf-label", Label)
        svf_label.update("SVF: -")
        svf_label.remove_class("svf-value-filled")
        self.query_one("#fisheye-summary-label", Label).update("")
        self.query_one(TimelineChart).plot_timeline([], [])
        table = self.query_one("#fisheye-intervals-table", DataTable)
        table.clear()
        self.query_one("#fisheye-status-label", Label).update("Select an image to begin")

    # ------------------------------------------------------------------
    # Circle calibration (numeric only, preview information only)
    # ------------------------------------------------------------------
    def _update_circle_inputs(self) -> None:
        self.query_one("#fisheye-cx-input", Input).value = f"{self.circle['cx']:.1f}"
        self.query_one("#fisheye-cy-input", Input).value = f"{self.circle['cy']:.1f}"
        self.query_one("#fisheye-r-input", Input).value = f"{self.circle['r']:.1f}"

    def _apply_circle_values(self) -> None:
        if self.original_image is None:
            self.app.notify("Please select an image first", severity="warning")
            return
        try:
            cx = float(self.query_one("#fisheye-cx-input", Input).value)
            cy = float(self.query_one("#fisheye-cy-input", Input).value)
            r = float(self.query_one("#fisheye-r-input", Input).value)
        except ValueError:
            self.app.notify("Center/radius must be numbers", severity="error")
            return
        w, h = self.original_image.width, self.original_image.height
        cx, cy = core_fisheye.clamp_center(cx, cy, w, h)
        r = core_fisheye.clamp_radius(cx, cy, r, w, h)
        self.circle = {"cx": cx, "cy": cy, "r": r}
        self._update_circle_inputs()

    def _reset_circle(self) -> None:
        if self.auto_circle is None:
            return
        self.circle = dict(self.auto_circle)
        self._update_circle_inputs()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    def _set_controls_enabled(self, enabled: bool) -> None:
        for wid in (
            "#fisheye-run-btn",
            "#fisheye-date-input",
            "#fisheye-lat-input",
            "#fisheye-lon-input",
            "#fisheye-tz-input",
        ):
            widget = self.query_one(wid)
            if isinstance(widget, Button):
                widget.disabled = not enabled
            elif isinstance(widget, Input):
                widget.disabled = not enabled

    def _start_analysis(self) -> None:
        if bm is None:
            self.app.notify("The biometeo package failed to load", severity="error")
            return
        if self.image_path is None:
            self.app.notify("Please select an image first", severity="warning")
            return
        try:
            target_date = datetime.datetime.strptime(
                self.query_one("#fisheye-date-input", Input).value.strip(), "%Y-%m-%d"
            ).date()
        except ValueError:
            self.app.notify("Please use the YYYY-MM-DD date format", severity="error")
            return
        try:
            lat = float(self.query_one("#fisheye-lat-input", Input).value)
            lon = float(self.query_one("#fisheye-lon-input", Input).value)
            tz = float(self.query_one("#fisheye-tz-input", Input).value)
        except ValueError:
            self.app.notify("Latitude/Longitude/Timezone must be numbers", severity="error")
            return

        self._set_controls_enabled(False)
        self.query_one("#fisheye-loading", LoadingIndicator).display = True
        self.query_one("#fisheye-status-label", Label).update("Analyzing…")
        self._run_analysis_worker(self.image_path, target_date, lat, lon, tz)

    @work(exclusive=True, thread=True, group="fisheye")
    def _run_analysis_worker(
        self, image_path: str, target_date: datetime.date, lat: float, lon: float, tz: float
    ) -> None:
        result: Optional[Dict[str, Any]] = None
        error: Optional[Exception] = None
        prev_cwd = os.getcwd()
        tmp_dir = tempfile.mkdtemp(prefix="biometeo_fisheye_")
        try:
            os.chdir(tmp_dir)
            svf, timeseries = bm.fisheye_svf(
                image_path, target_date, latitude=lat, longitude=lon, tz_hours=tz, draw_and_save=True
            )
            intervals = bm.extract_shading_intervals(timeseries)
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
        self.app.call_from_thread(self._on_analysis_done, result, error, image_path)

    def _on_analysis_done(
        self, result: Optional[Dict[str, Any]], error: Optional[Exception], image_path: str
    ) -> None:
        self._set_controls_enabled(True)
        self.query_one("#fisheye-loading", LoadingIndicator).display = False
        if error is not None:
            self.app.notify(f"Analysis failed: {error}", severity="error")
            self.query_one("#fisheye-status-label", Label).update("An error occurred")
            return
        self.last_result = result
        self._render_results(result)
        self.query_one("#fisheye-status-label", Label).update(
            f"Done — SVF = {result['svf']:.4f} filled into Tmrt_calc's OmegaF and Is_Shaded fields"
        )
        self.post_message(self.AnalysisComplete(result["svf"], image_path, result["timeseries"]))

    def _render_results(self, result: Dict[str, Any]) -> None:
        self.query_one("#fisheye-mask-image", AutoImage).image = result["mask_img"]
        self.query_one("#fisheye-sunpath-image", AutoImage).image = result["sunpath_img"]

        svf_label = self.query_one("#fisheye-svf-label", Label)
        svf_label.update(f"SVF: {result['svf']:.4f}")
        svf_label.add_class("svf-value-filled")

        shaded_minutes = sum(iv["Duration_Mins"] for iv in result["intervals"])
        sunup_minutes = sum(1 for e in result["timeseries"] if e["Solar_Altitude"] > 0)
        visible_minutes = max(0, sunup_minutes - shaded_minutes)
        self.query_one("#fisheye-summary-label", Label).update(
            f"Sunlight: {sunup_minutes} min | Shaded: {shaded_minutes} min | Visible: {visible_minutes} min"
        )

        self.query_one(TimelineChart).plot_timeline(result["timeseries"], result["intervals"])

        table = self.query_one("#fisheye-intervals-table", DataTable)
        table.clear()
        for iv in result["intervals"]:
            table.add_row(iv["Start_DateTime"], iv["End_DateTime"], str(iv["Duration_Mins"]), str(iv["SVF"]))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_csv(self) -> None:
        if bm is None or self.last_result is None:
            self.app.notify("Please run an analysis first", severity="warning")
            return
        self.app.push_screen(
            FileSave(title="Export Shading Intervals CSV", default_file="shading_intervals.csv"),
            self._on_export_csv_path,
        )

    def _on_export_csv_path(self, path: Optional[Path]) -> None:
        if path is None or self.last_result is None:
            return
        try:
            bm.save_shading_intervals_csv(
                self.last_result["intervals"], str(path), self.last_result["svf"], self.last_result["date_str"]
            )
            self.query_one("#fisheye-status-label", Label).update(f"CSV exported to {path}")
        except Exception as e:
            self.app.notify(f"Export failed: {e}", severity="error")

    def _export_timeline_image(self) -> None:
        if self.last_result is None:
            self.app.notify("Please run an analysis first", severity="warning")
            return
        self.app.push_screen(
            FileSave(title="Export Timeline Image", default_file="timeline.png"),
            self._on_export_png_path,
        )

    def _on_export_png_path(self, path: Optional[Path]) -> None:
        if path is None or self.last_result is None:
            return
        try:
            img = core_fisheye.draw_timeline_image(self.last_result["timeseries"], self.last_result["intervals"])
            img.save(str(path))
            self.query_one("#fisheye-status-label", Label).update(f"Timeline image exported to {path}")
        except Exception as e:
            self.app.notify(f"Export failed: {e}", severity="error")

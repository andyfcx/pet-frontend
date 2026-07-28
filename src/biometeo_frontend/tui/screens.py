"""Main screen for the Textual biometeo front end.

Functionally mirrors main.py's App class (customtkinter): function selector,
dynamic parameter form, documentation panel, CSV batch import, results table,
output export controls, on-demand citations, and the fisheye SVF sub-panel with
its OmegaF/Is_Shaded auto-fill/highlight/clear/persist behavior.
"""

import inspect
import io
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    Select,
    TextArea,
)
from textual_fspicker import FileOpen, FileSave, Filters

from biometeo_frontend import core
from biometeo_frontend.core import get_callable, parse_value
from biometeo_frontend.core_fisheye import fisheye_shading_at_hour
from biometeo_frontend.tui.widgets.fisheye_panel import FisheyePanel
from biometeo_frontend.tui.widgets.param_form import ParamForm

FISHEYE_TITLE = "Fisheye Photo → Sky View Factor (optional, fills OmegaF & Is_Shaded)"


class MainScreen(Screen):
    DEFAULT_CSS = """
    #top-bar {
        height: auto;
        padding: 1;
    }
    #top-bar Select {
        width: 24;
        margin-right: 1;
    }
    #top-bar Button {
        margin-right: 1;
    }
    #status-label {
        width: 1fr;
        content-align: right middle;
    }
    #middle {
        height: 3fr;
        min-height: 8;
    }
    #docs-pane {
        width: 34;
        height: 1fr;
        border: round $primary-background-lighten-2;
        padding: 0 1;
    }
    #docs-header {
        height: auto;
    }
    #docs-title {
        width: 1fr;
        text-style: bold;
    }
    #docs-back-btn {
        width: auto;
        min-width: 12;
    }
    #docs-pane TextArea {
        height: 1fr;
    }
    #results-table {
        height: 2fr;
        min-height: 5;
        max-height: 12;
        margin: 1 0;
    }
    #output-controls {
        height: auto;
        padding: 0 1;
    }
    #output-controls Select {
        width: 12;
        margin-right: 1;
    }
    #output-controls Button {
        margin-right: 1;
        min-width: 0;
        width: auto;
    }
    """

    BINDINGS = [
        Binding("shift+enter", "run_single", "Run", show=True),
    ]

    fisheye_svf_info: reactive[Optional[Dict[str, Any]]] = reactive(None)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.current_output_df: Optional[pd.DataFrame] = None
        self.current_output_fn: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-bar"):
            yield Select(
                [(name, name) for name in core.TARGET_FUNCTIONS],
                value=core.TARGET_FUNCTIONS[0],
                allow_blank=False,
                id="fn-select",
            )
            yield Button("Open CSV", id="open-csv-btn")
            yield Button("Run", id="run-btn", variant="primary")
            yield Label("Ready", id="status-label")

        with Collapsible(title=FISHEYE_TITLE, collapsed=True, id="fisheye-collapsible"):
            yield FisheyePanel(id="fisheye-panel")

        with Horizontal(id="middle"):
            yield ParamForm(id="param-form")
            with Vertical(id="docs-pane"):
                with Horizontal(id="docs-header"):
                    yield Label("Documentation", id="docs-title")
                    yield Button("← Back", id="docs-back-btn")
                yield TextArea(read_only=True, id="docs-text")

        yield DataTable(id="results-table", cursor_type="cell")
        yield ProgressBar(id="csv-progress", total=100)

        with Horizontal(id="output-controls"):
            yield Label("Output:")
            yield Label("Format:")
            yield Select(
                [("csv", "csv"), ("json", "json")],
                value="csv",
                allow_blank=False,
                compact=True,
                id="format-select",
            )
            yield Label("Decimals:")
            yield Select(
                [(str(value), value) for value in range(9)],
                value=1,
                allow_blank=False,
                compact=True,
                id="decimals-select",
            )
            yield Button("Save Output", id="save-output-btn")
            yield Button("Copy to Clipboard", id="copy-output-btn")
            yield Button("Clear", id="clear-output-btn")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#csv-progress", ProgressBar).display = False
        self.query_one("#docs-back-btn", Button).display = False
        self._on_function_change(core.TARGET_FUNCTIONS[0])

    # ------- Status helper -------
    def set_status(self, text: str) -> None:
        self.query_one("#status-label", Label).update(text)

    # ------- Function change -------
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "fn-select":
            self._on_function_change(str(event.value))
        elif event.select.id == "decimals-select" and self.current_output_df is not None:
            self._render_table(self.current_output_df)

    def _on_function_change(self, fn_name: str) -> None:
        collapsible = self.query_one("#fisheye-collapsible", Collapsible)
        collapsible.display = fn_name == "Tmrt_calc"

        fn = get_callable(fn_name)
        form = self.query_one(ParamForm)
        form.rebuild(fn_name)

        if fn is None:
            self._set_docs_panel("Function not found.")
            self.set_status(f"Function {fn_name} not found")
            return
        self._show_function_docs()

        if fn_name == "Tmrt_calc" and self.fisheye_svf_info is not None:
            self._apply_fisheye_svf_to_form()

    # ------- Documentation / citation panel -------
    def _set_docs_panel(self, text: str, title: str = "Documentation", show_back: bool = False) -> None:
        self.query_one("#docs-text", TextArea).text = text
        self.query_one("#docs-title", Label).update(title)
        self.query_one("#docs-back-btn", Button).display = show_back

    def _show_function_docs(self) -> None:
        fn_name = str(self.query_one("#fn-select", Select).value)
        fn = get_callable(fn_name)
        doc = (inspect.getdoc(fn) or "No documentation available.") if fn else "Function not found."
        self._set_docs_panel(doc)

    def _show_citation(self, fn_name: str) -> None:
        self._set_docs_panel(
            core.build_citation_text(fn_name),
            title="Citation Suggestions",
            show_back=True,
        )

    def _notify_citation(self) -> None:
        fn_name = self.current_output_fn or str(self.query_one("#fn-select", Select).value)
        self._show_citation(fn_name)
        self.app.notify(
            f"Citation suggestions for {fn_name} are now shown in the Documentation panel.",
            title="Citation Suggestion",
        )

    # ------- Fisheye SVF sync -------
    def on_fisheye_panel_analysis_complete(self, message: FisheyePanel.AnalysisComplete) -> None:
        self.fisheye_svf_info = {
            "svf": message.svf,
            "path": message.image_path,
            "timeseries": message.timeseries,
        }
        form = self.query_one(ParamForm)
        if form.current_fn_name == "Tmrt_calc":
            self._apply_fisheye_svf_to_form()

    def _apply_fisheye_svf_to_form(self) -> None:
        info = self.fisheye_svf_info
        if info is None:
            return
        form = self.query_one(ParamForm)
        ann, omega_widget = form.param_entries.get("OmegaF", (None, None))
        if not isinstance(omega_widget, Input):
            return
        omega_widget.value = f"{info['svf']:.4f}"
        omega_widget.add_class("svf-filled")

        shading_text = ""
        hour_ann, hour_widget = form.param_entries.get("hour_of_day", (None, None))
        shade_ann, shade_widget = form.param_entries.get("Is_Shaded", (None, None))
        if isinstance(hour_widget, Input) and isinstance(shade_widget, Checkbox):
            try:
                is_shaded, time_str = fisheye_shading_at_hour(info["timeseries"], hour_widget.value.strip())
                shade_widget.value = is_shaded
                shading_text = f"; Is_Shaded = {is_shaded} at {time_str}"
            except (KeyError, StopIteration, TypeError, ValueError):
                shading_text = "; Is_Shaded not filled (invalid hour or missing timeseries data)"

        if form.omega_hint is not None:
            form.omega_hint.update(
                f"✓ SVF = {info['svf']:.4f}{shading_text} obtained from photo (source: {info['path']})"
            )
            form.omega_hint.add_class("svf-filled")
        if form.omega_clear_btn is not None:
            form.omega_clear_btn.disabled = False
        self.set_status(f"Filled OmegaF = {info['svf']:.4f}{shading_text} from fisheye photo analysis")

    def _clear_fisheye_svf(self) -> None:
        self.fisheye_svf_info = None
        form = self.query_one(ParamForm)
        ann, omega_widget = form.param_entries.get("OmegaF", (None, None))
        if isinstance(omega_widget, Input):
            omega_widget.value = ""
            omega_widget.remove_class("svf-filled")
        shade_ann, shade_widget = form.param_entries.get("Is_Shaded", (None, None))
        if isinstance(shade_widget, Checkbox):
            shade_widget.value = False
        if form.omega_hint is not None:
            form.omega_hint.update("")
            form.omega_hint.remove_class("svf-filled")
        if form.omega_clear_btn is not None:
            form.omega_clear_btn.disabled = True
        self.set_status("Cleared image-derived OmegaF and Is_Shaded")

    # ------- Buttons -------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "open-csv-btn":
            self._open_csv_picker()
        elif button_id == "run-btn":
            self._on_run_single()
        elif button_id == "save-output-btn":
            self._open_save_picker()
        elif button_id == "copy-output-btn":
            self._on_copy_output()
        elif button_id == "clear-output-btn":
            self._on_clear_output()
        elif button_id == "clear-photo-values-btn":
            self._clear_fisheye_svf()
        elif button_id == "docs-back-btn":
            self._show_function_docs()

    # ------- CSV import -------
    def _open_csv_picker(self) -> None:
        filters = Filters(("CSV files", lambda p: p.suffix.lower() == ".csv"))
        self.app.push_screen(FileOpen(title="Open CSV", filters=filters), self._on_csv_picked)

    def _on_csv_picked(self, path: Optional[Path]) -> None:
        if path is None:
            return
        self._process_csv(str(path))

    def _process_csv(self, path: str) -> None:
        fn_name = self.query_one("#fn-select", Select).value
        fn = get_callable(fn_name)
        if fn is None:
            self.app.notify(f"Function {fn_name} not found", severity="error")
            return
        try:
            df = pd.read_csv(path)
        except Exception as e:
            self.app.notify(f"Failed to read CSV: {e}", severity="error")
            return
        sig = inspect.signature(fn)
        err = core.validate_headers(df, sig)
        if err:
            self.app.notify(err, severity="error")
            return

        target = core.humidity_target_param(sig)
        rows_args: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            kwargs = {}
            for name, p in sig.parameters.items():
                if name in ("self", "cls") or name == target:
                    continue
                ann = p.annotation
                if name in df.columns:
                    val = row[name]
                    if pd.isna(val):
                        val = None
                    parsed = parse_value(val, ann)
                else:
                    parsed = p.default
                kwargs[name] = parsed
            if target is not None:
                target_ann = sig.parameters[target].annotation
                rh_val = parse_value(row["RH"], target_ann) if "RH" in df.columns and not pd.isna(row["RH"]) else None
                vp_val = parse_value(row["VP"], target_ann) if "VP" in df.columns and not pd.isna(row["VP"]) else None
                try:
                    kwargs[target] = core.resolve_humidity_value(target, kwargs.get("Ta"), rh_val, vp_val)
                except (ValueError, RuntimeError):
                    kwargs[target] = None
            rows_args.append(kwargs)

        progress = self.query_one("#csv-progress", ProgressBar)
        progress.display = True
        progress.update(total=len(rows_args), progress=0)
        self._set_controls_enabled(False)
        self.set_status("Processing CSV…")
        self._run_csv_worker(fn, rows_args, df, fn_name)

    @work(exclusive=True, thread=True, group="csv")
    def _run_csv_worker(
        self, fn, rows_args: List[Dict[str, Any]], df: pd.DataFrame, fn_name: str
    ) -> None:
        results: List[Any] = []
        errors: List[str] = []
        total = len(rows_args)
        for i, kwargs in enumerate(rows_args):
            try:
                res = fn(**kwargs)
                results.append(res)
            except Exception as e:
                results.append(None)
                errors.append(f"Row {i}: {e}")
            self.app.call_from_thread(self._update_csv_progress, i + 1, total)
        self.app.call_from_thread(self._on_csv_done, results, errors, df, fn_name)

    def _update_csv_progress(self, done: int, total: int) -> None:
        self.query_one("#csv-progress", ProgressBar).update(progress=done)

    def _on_csv_done(self, results: List[Any], errors: List[str], df: pd.DataFrame, fn_name: str) -> None:
        if errors:
            self.set_status(f"Completed with {len(errors)} errors; see console.")
            for e in errors:
                print(e, file=sys.stderr)
        else:
            self.set_status("Completed")

        out_df = core.normalize_results(results, fn_name)
        joined = pd.concat([df.reset_index(drop=True), out_df], axis=1)
        self.current_output_df = joined
        self.current_output_fn = fn_name
        self._render_table(joined)

        self.query_one("#csv-progress", ProgressBar).display = False
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for wid in (
            "#open-csv-btn",
            "#run-btn",
            "#format-select",
            "#decimals-select",
            "#save-output-btn",
            "#copy-output-btn",
            "#clear-output-btn",
        ):
            self.query_one(wid).disabled = not enabled

    # ------- Manual run -------
    def action_run_single(self) -> None:
        self._on_run_single()

    def _on_run_single(self) -> None:
        fn_name = self.query_one("#fn-select", Select).value
        fn = get_callable(fn_name)
        if fn is None:
            self.app.notify(f"Function {fn_name} not found", severity="error")
            return
        if fn_name == "Tmrt_calc" and self.fisheye_svf_info is not None:
            self._apply_fisheye_svf_to_form()

        form = self.query_one(ParamForm)
        try:
            kwargs = form.read_values()
        except ValueError as e:
            self.app.notify(str(e), severity="error")
            return

        try:
            result = fn(**kwargs)
            out_df = core.normalize_results([result], fn_name)
            self.current_output_df = out_df
            self.current_output_fn = fn_name
            self._render_table(out_df)
            self.set_status("Completed")
        except Exception:
            buf = io.StringIO()
            traceback.print_exc(file=buf)
            self.app.notify(buf.getvalue(), severity="error", timeout=10)
            self.set_status("Error")

    # ------- Table rendering -------
    def _render_table(self, df: pd.DataFrame) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)
        cols = list(df.columns)
        table.add_columns(*[str(c) for c in cols])
        for _, row in df.iterrows():
            values = [self._format_cell(row[c]) for c in cols]
            table.add_row(*values)

    def _format_cell(self, value: Any) -> Any:
        if isinstance(value, float):
            return f"{value:.{self._get_decimals()}f}"
        return value

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        value = event.value
        self.app.copy_to_clipboard("" if value is None else str(value))
        self.set_status("Copied cell to clipboard")

    # ------- Output controls -------
    def _get_decimals(self) -> int:
        value = self.query_one("#decimals-select", Select).value
        try:
            return max(0, min(8, int(value)))
        except (TypeError, ValueError):
            return 1

    def _open_save_picker(self) -> None:
        if self.current_output_df is None or self.current_output_df.empty:
            self.app.notify("No output to save yet.", severity="warning")
            return
        fmt = self.query_one("#format-select", Select).value or "csv"
        default_file = f"output.{fmt}"
        self.app.push_screen(FileSave(title="Save output", default_file=default_file), self._on_save_path)

    def _on_save_path(self, path: Optional[Path]) -> None:
        if path is None or self.current_output_df is None:
            return
        fmt = self.query_one("#format-select", Select).value or "csv"
        decimals = self._get_decimals()
        try:
            if fmt == "json":
                text = self.current_output_df.to_json(orient="records", double_precision=decimals)
                Path(path).write_text(text, encoding="utf-8")
            else:
                self.current_output_df.to_csv(path, index=False, float_format=f"%.{decimals}f")
            self.set_status(f"Saved to {path}")
            self._notify_citation()
        except Exception as e:
            self.app.notify(f"Save error: {e}", severity="error")

    def _on_copy_output(self) -> None:
        if self.current_output_df is None or self.current_output_df.empty:
            self.app.notify("No output to copy yet.", severity="warning")
            return
        fmt = self.query_one("#format-select", Select).value or "csv"
        decimals = self._get_decimals()
        try:
            if fmt == "json":
                text = self.current_output_df.to_json(orient="records", double_precision=decimals)
            else:
                text = self.current_output_df.to_csv(index=False, float_format=f"%.{decimals}f")
            self.app.copy_to_clipboard(text)
            self.set_status(f"Copied {fmt.upper()} to clipboard")
            self._notify_citation()
        except Exception as e:
            self.app.notify(f"Copy error: {e}", severity="error")

    def _on_clear_output(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)
        self.current_output_df = None
        self.current_output_fn = None
        self._show_function_docs()
        self.set_status("Cleared output")

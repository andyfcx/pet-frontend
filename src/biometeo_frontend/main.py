import inspect
import io
import sys
import traceback
import json
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

# UI libs
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox

# Drag and drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # pragma: no cover - optional at runtime
    DND_FILES = None
    TkinterDnD = None

# biometeo functions
try:
    import biometeo as bm
except Exception as e:
    bm = None
    bm_import_error = e
else:
    bm_import_error = None


APP_TITLE = "Biometeo UI"
HIGHLIGHT_COLOR = ("#0f9d58", "#4ade80")
TARGET_FUNCTIONS = [
    "mPET",
    "mPET_quick",
    "PET",
    "Tmrt_calc",
    "PMV",
    "SET",
    "UTCI",
]

# Citation suggestions shown after results table per function
CITATIONS: Dict[str, str] = {
    # UTCI
    "UTCI": (
        "For applying Universal Thermal Climate Index (UTCI), please cite:\n\n"
        "- Bröde, P. et al. Deriving the operational procedure for the universal thermal climate index (UTCI). "
        "International Journal of Biometeorology 56, 481–494 (2012). http://link.springer.com/10.1007/s00484-011-0454-1\n\n"
        "- Jendritzky, G., de Dear, R. & Havenith, G. UTCI—why another thermal index? "
        "International Journal of Biometeorology 56, 421–428 (2012). http://link.springer.com/10.1007/s00484-011-0513-7\n"
    ),
    # PMV
    "PMV": (
        "For calculation of Predicted Mean Vote (PMV), please cite:\n\n"
        "- Fanger, P. O. Thermal comfort: Analysis and applications in environmental engineering, vol. 3 "
        "(Danish Technical Press, 1972). http://www.cabdirect.org/abstracts/19722700268.html "
        "https://linkinghub.elsevier.com/retrieve/pii/S0003687072800747\n"
    ),
    # SET*
    "SET": (
        "For using Outdoor Standard Effective Temperature (SET*), please cite:\n\n"
        "- Gagge, A. P., Fobelets, A. P. & Berglund, L. G. Standard predictive index of human response to the thermal "
        "environment. ASHRAE Transactions 92, 709–731 (1986). https://www.aivc.org/sites/default/files/airbase_2522.pdf "
        "http://oceanrep.geomar.de/42985/\n"
    ),
    # PET
    "PET": (
        "For application of Physiologically Equivalent Temperature (PET), please cite:\n\n"
        "- Höppe, P. The physiological equivalent temperature — a universal index for the biometeorological assessment of "
        "the thermal environment. International Journal of Biometeorology 43, 71–75 (1999). "
        "http://link.springer.com/10.1007/s004840050118\n"
    ),
    # mPET and quick variant share the same references
    "mPET": (
        "For application of modified Physiologically Equivalent Temperature (mPET), please cite:\n\n"
        "- Chen, YC. Thermal indices for human biometeorology based on Python. Sci Rep 13, 20825 (2023). https://doi.org/10.1038/s41598-023-47388-y\n\n"
        "- Chen, Y.-C. & Matzarakis, A. Modification of physiologically equivalent temperature. Journal of Heat Island "
        "Institute International 9, 26–32 (2014). http://www.heat-island.jp/web_journal/Special_Issue_7JGM/15_chen.pdf\n\n"
        "- Chen, Y.-C. & Matzarakis, A. Modified physiologically equivalent temperature—basics and applications for "
        "western European climate. Theoretical and Applied Climatology 132, 1275–1289 (2018). "
        "http://link.springer.com/10.1007/s00704-017-2158-x\n\n"
        "- Chen, Y.-C., Chen, W.-N., Chou, C. & Matzarakis, A. Concepts and new implements for modified physiologically "
        "equivalent temperature. Atmosphere 11, 694 (2020). https://www.mdpi.com/2073-4433/11/7/694\n"
    ),
    "mPET_quick": (
        "For application of modified Physiologically Equivalent Temperature (mPET), please cite:\n\n"
        "- Chen, YC. Thermal indices for human biometeorology based on Python. Sci Rep 13, 20825 (2023). https://doi.org/10.1038/s41598-023-47388-y\n\n"
        "- Chen, Y.-C. & Matzarakis, A. Modification of physiologically equivalent temperature. Journal of Heat Island "
        "Institute International 9, 26–32 (2014). http://www.heat-island.jp/web_journal/Special_Issue_7JGM/15_chen.pdf\n\n"
        "- Chen, Y.-C. & Matzarakis, A. Modified physiologically equivalent temperature—basics and applications for "
        "western European climate. Theoretical and Applied Climatology 132, 1275–1289 (2018). "
        "http://link.springer.com/10.1007/s00704-017-2158-x\n\n"
        "- Chen, Y.-C., Chen, W.-N., Chou, C. & Matzarakis, A. Concepts and new implements for modified physiologically "
        "equivalent temperature. Atmosphere 11, 694 (2020). https://www.mdpi.com/2073-4433/11/7/694\n"
    ),
    # Tmrt
    "Tmrt_calc": (
        "For simulation of mean radiant temperature (Tmrt), please cite:\n\n"
        "- Matzarakis, A., Rutz, F. & Mayer, H. Modelling radiation fluxes in simple and complex environments—application "
        "of the RayMan model. International Journal of Biometeorology 51, 323–334 (2007). https://doi.org/10.1007/s00484-006-0061-8\n\n"
        "- Matzarakis, A., Rutz, F. & Mayer, H. Modelling radiation fluxes in simple and complex environments: basics of the "
        "RayMan model. International Journal of Biometeorology 54, 131–139 (2010). https://doi.org/10.1007/s00484-009-0261-0\n"
    ),
}

# General note about the biometeo package review and wind speed reduction exponent reference
CITATION_HEADER = (
    "The citation about Python package biometeo is still under reviewing. For use of the function or thermal indices in biometeo, "
    "the following citations are suggested.\n\n"
)
WIND_EXPONENT_NOTE = (
    "For using the exponent equation as a reducing mechanism of wind speed from some height to 1.1 m, please also see:\n\n"
    "- Matzarakis, A., Rocco, M. D. & Najjar, G. Thermal bioclimate in Strasbourg — the 2003 heat wave. Theoretical and Applied "
    "Climatology 98, 209–220 (2009). http://link.springer.com/10.1007/s00704-009-0102-4\n"
)


# Grouping of input parameters into labeled sections in the form.
# Any parameter not listed here falls back into the "other" group.
GROUP_ORDER = ["geo_time", "physio", "meteo", "other"]
GROUP_TITLES: Dict[str, str] = {
    "geo_time": "Date/Time & Location",
    "physio": "Physiological Info",
    "meteo": "Meteorological Data",
    "other": "Other Parameters",
}
PARAM_GROUP_MAP: Dict[str, str] = {
    # Date/time + geographic info
    "day_of_year": "geo_time",
    "hour_of_day": "geo_time",
    "longitude": "geo_time",
    "latitude": "geo_time",
    "sea_level_height": "geo_time",
    "timezone_offset": "geo_time",
    # Physiological info
    "ht": "physio",
    "mbody": "physio",
    "age": "physio",
    "sex": "physio",
    "icl": "physio",
    "clo_auto": "physio",
    "work": "physio",
    "pos": "physio",
    # Meteorological data
    "Ta": "meteo",
    "VP": "meteo",
    "RH": "meteo",
    "v": "meteo",
    "Tmrt": "meteo",
    "N": "meteo",
    "G": "meteo",
    "DGratio": "meteo",
    "Tob": "meteo",
    "ltf": "meteo",
    "OmegaF": "meteo",
    "alb": "meteo",
    "albhum": "meteo",
    "RedGChk": "meteo",
    "foglimit": "meteo",
    "bowen": "meteo",
    "Is_Shaded": "meteo",
}
LABEL_ALIASES: Dict[str, str] = {
    "day_of_year": "Day of Year",
    "hour_of_day": "Hour of Day",
    "longitude": "Longitude",
    "latitude": "Latitude",
    "sea_level_height": "Altitude",
    "timezone_offset": "Timezone",
    "ht": "Height (ht)",
    "mbody": "Weight (mbody)",
    "age": "Age",
    "sex": "Gender (sex)",
    "icl": "Clothing (Icl)",
    "clo_auto": "Auto Clothing",
    "work": "Activity (work)",
    "pos": "Position (pos)",
    "Ta": "Air Temp (Ta)",
    "VP": "Vapor Pressure (VP)",
    "RH": "Rel. Humidity (RH)",
    "v": "Wind Speed (v)",
    "Tmrt": "Mean Radiant Temp (Tmrt)",
    "N": "Cloud Cover (N)",
    "G": "Global Radiation (G)",
    "OmegaF": "Sky View Factor (OmegaF)",
    "Is_Shaded": "Shaded by Obstacle (Is_Shaded)",
}


def get_callable(name: str) -> Optional[Callable]:
    if bm is None:
        return None
    fn = getattr(bm, name, None)
    if callable(fn):
        return fn
    return None


def parse_value(text: str, annotation: Any) -> Any:
    """Parse text to python value based on type annotation if possible.
    Falls back to float, int, bool, or str heuristics.
    """
    if text is None:
        return None
    s = str(text).strip()
    if s == "":
        return None

    # Try annotation-based parsing
    try:
        if annotation in (int, "int"):
            return int(s)
        if annotation in (float, "float"):
            return float(s)
        if annotation in (bool, "bool"):
            if s.lower() in ("1", "true", "yes", "y", "t"):  # common truthy
                return True
            if s.lower() in ("0", "false", "no", "n", "f"):
                return False
            # as fallback, non-empty → True
            return bool(s)
        if annotation in (str, "str"):
            return s
    except Exception:
        pass

    # Heuristics
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        if "." in s or "e" in low:
            return float(s)
        return int(s)
    except Exception:
        return s


def fisheye_shading_at_hour(timeseries: List[Dict[str, Any]], hour_of_day: float):
    """Return the fisheye shading flag and matched minute for a decimal hour."""
    hour = float(hour_of_day)
    if not 0 <= hour < 24:
        raise ValueError("hour_of_day must be between 0 and 24")
    minute_index = min(1439, int(round(hour * 60)))
    time_str = f"{minute_index // 60:02d}:{minute_index % 60:02d}"
    minute = next(item for item in timeseries if item["Time_Str"] == time_str)
    return bool(minute["Is_Shaded"]), minute["Time_Str"]


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # Top: function selection
        top = ctk.CTkFrame(root)
        top.pack(side="top", fill="x", padx=8, pady=8)

        ctk.CTkLabel(top, text="Select function:").pack(side="left")
        self.fn_var = ctk.StringVar(value=TARGET_FUNCTIONS[0])
        self.fn_combo = ctk.CTkComboBox(top, values=TARGET_FUNCTIONS, variable=self.fn_var,
                                        command=self.on_function_change, width=200)
        self.fn_combo.pack(side="left", padx=8)

        self.open_btn = ctk.CTkButton(top, text="Open CSV", command=self.on_open_csv)
        self.open_btn.pack(side="left", padx=8)

        self.run_btn = ctk.CTkButton(top, text="Run", command=self.on_run_single)
        self.run_btn.pack(side="left", padx=8)


        self.status_var = ctk.StringVar(value="Ready")
        self.status_lbl = ctk.CTkLabel(top, textvariable=self.status_var)
        self.status_lbl.pack(side="right")

        # Drag-and-drop area for CSV files
        self.drop_frame = ctk.CTkFrame(root, border_width=1, border_color="gray50")
        self.drop_frame.pack(side="top", fill="x", padx=8, pady=(0, 8))
        self.drop_label = ctk.CTkLabel(self.drop_frame, text="Drag a CSV file here, or click to browse", height=40)
        self.drop_label.pack(fill="x", padx=8, pady=8)
        # Allow clicking the drop area to open file dialog
        self.drop_label.bind("<Button-1>", lambda e: self.on_open_csv())
        
        # Register DnD on the drop area if supported
        if TkinterDnD is not None and DND_FILES is not None:
            for widget in (self.drop_label, self.drop_frame):
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind('<<Drop>>', self.on_drop)
                except Exception:
                    pass
        else:
            # Fallback: inform user that DnD is unavailable
            try:
                self.drop_label.configure(text="Click to open a CSV (drag-and-drop extension not available)")
            except Exception:
                pass

        # Middle: left form, right docs
        self.middle = ctk.CTkFrame(root)
        middle = self.middle
        self.middle.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        self.form_frame = ctk.CTkScrollableFrame(middle, width=560)
        self.form_frame.pack(side="left", fill="both", expand=False, padx=(0, 8))

        self.docs_frame = ctk.CTkFrame(middle)
        self.docs_frame.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(self.docs_frame, text="Documentation").pack(anchor="w", padx=8, pady=4)
        self.docs_text = ctk.CTkTextbox(self.docs_frame)
        self.docs_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.docs_text.configure(state="disabled")

        # Fisheye photo -> Sky View Factor helper, shown only for Tmrt_calc.
        # Collapsed by default; expanding lazily builds the (heavy) FisheyeView widget.
        self.fisheye_section = ctk.CTkFrame(root, border_width=1, border_color="gray50")
        self._fisheye_expanded = False
        fisheye_header = ctk.CTkFrame(self.fisheye_section, fg_color="transparent")
        fisheye_header.pack(fill="x")
        self.fisheye_toggle_btn = ctk.CTkButton(
            fisheye_header,
            text="▸ Fisheye Photo → Sky View Factor (optional, fills OmegaF & Is_Shaded)",
            command=self.on_toggle_fisheye_section,
            fg_color="transparent",
            anchor="w",
        )
        self.fisheye_toggle_btn.pack(fill="x", padx=4, pady=4)
        self.fisheye_body = ctk.CTkFrame(self.fisheye_section, fg_color="transparent")

        # Bottom: output table
        self.bottom_frame = ctk.CTkFrame(root)
        bottom = self.bottom_frame
        self.bottom_frame.pack(side="bottom", fill="both", expand=True, padx=8, pady=(0, 8))

        self.table = ttk.Treeview(bottom, show="headings")
        self.table.pack(side="left", fill="both", expand=True)
        self.table.bind("<Button-1>", self.on_table_click_copy)

        yscroll = ttk.Scrollbar(bottom, orient="vertical", command=self.table.yview)
        yscroll.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=yscroll.set)

        # Output controls (format selector, Save, Copy) placed near the table
        self.output_controls = ctk.CTkFrame(root)
        self.output_controls.pack(side="bottom", fill="x", expand=False, padx=8, pady=(0, 8))
        ctk.CTkLabel(self.output_controls, text="Output:").pack(side="left", padx=(8, 4))
        ctk.CTkLabel(self.output_controls, text="Format:").pack(side="left", padx=(4, 4))
        self.format_var = ctk.StringVar(value="csv")
        self.format_menu = ctk.CTkOptionMenu(self.output_controls, values=["csv", "json"], variable=self.format_var)
        self.format_menu.pack(side="left", padx=(0, 12))
        self.save_btn = ctk.CTkButton(self.output_controls, text="Save Output", command=self.on_save_output)
        self.save_btn.pack(side="left", padx=(0, 8))
        self.copy_btn = ctk.CTkButton(self.output_controls, text="Copy to Clipboard", command=self.on_copy_output)
        self.copy_btn.pack(side="left", padx=(0, 8))
        self.clear_btn = ctk.CTkButton(self.output_controls, text="Clear", command=self.on_clear_output)
        self.clear_btn.pack(side="left", padx=(0, 8))

        # Progress area (shown during CSV processing)
        self.progress_frame = ctk.CTkFrame(root)
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Processing CSV…")
        self.progress_label.pack(anchor="w", padx=8, pady=(4, 0))
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=8, pady=(4, 0))
        self.progress_pct = ctk.CTkLabel(self.progress_frame, text="")
        self.progress_pct.pack(anchor="e", padx=8, pady=(0, 4))
        # hidden by default
        try:
            self.progress_frame.pack_forget()
        except Exception:
            pass

        # Citation area below the table
        self.citation_frame = ctk.CTkFrame(root)
        self.citation_frame.pack(side="bottom", fill="both", expand=False, padx=8, pady=(0, 8))
        ctk.CTkLabel(self.citation_frame, text="Citation suggestions").pack(anchor="w", padx=8, pady=(4, 0))
        self.citation_text = ctk.CTkTextbox(self.citation_frame, height=140)
        self.citation_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.citation_text.configure(state="disabled")

        # Storage for dynamic widgets and data
        self.param_entries: Dict[str, Any] = {}
        self.param_widgets: List[Any] = []
        self.current_output_df: Optional[pd.DataFrame] = None
        self.fisheye_view = None

        # SVF and per-minute shading carried over from the fisheye photo analysis
        # so both can be reapplied when the user returns to Tmrt_calc.
        self._fisheye_svf_info: Optional[Dict[str, Any]] = None
        self._omega_default_text_color = None
        self.omega_hint_label = None
        self.omega_clear_btn = None

        # Drag and drop registration if available
        if TkinterDnD is not None and DND_FILES is not None and hasattr(root, "drop_target_register"):
            try:
                root.drop_target_register(DND_FILES)
                root.dnd_bind('<<Drop>>', self.on_drop)
            except Exception:
                pass

        # Initialize with default function
        self.on_function_change(self.fn_var.get())
        self.clear_citation()

        if bm_import_error is not None:
            messagebox.showerror("Import error", f"Failed to import biometeo: {bm_import_error}")

    # ------- Fisheye SVF helper embedded in the Tmrt page -------
    def _ensure_fisheye_view(self):
        if self.fisheye_view is None:
            from biometeo_frontend.fisheye_view import FisheyeView
            self.fisheye_view = FisheyeView(self.fisheye_body, bm, on_svf=self.on_fisheye_svf)
        return self.fisheye_view

    def on_toggle_fisheye_section(self):
        self._fisheye_expanded = not self._fisheye_expanded
        if self._fisheye_expanded:
            view = self._ensure_fisheye_view()
            view.pack(fill="both", expand=True)
            self.fisheye_body.pack(fill="both", expand=True, padx=4, pady=(0, 4))
            self.fisheye_toggle_btn.configure(
                text="▾ Fisheye Photo → Sky View Factor (optional, fills OmegaF & Is_Shaded)"
            )
        else:
            self.fisheye_body.pack_forget()
            self.fisheye_toggle_btn.configure(
                text="▸ Fisheye Photo → Sky View Factor (optional, fills OmegaF & Is_Shaded)"
            )

    def on_fisheye_svf(self, svf: float, image_path: str, timeseries: List[Dict[str, Any]]):
        self._fisheye_svf_info = {"svf": svf, "path": image_path, "timeseries": timeseries}
        # Only apply immediately if the Tmrt form (with an OmegaF field) is the active form;
        # otherwise it is reapplied when the user switches back to Tmrt_calc.
        if self.fn_var.get() != "Tmrt_calc":
            return
        self._apply_fisheye_svf_to_form()

    def _apply_fisheye_svf_to_form(self):
        info = self._fisheye_svf_info
        if info is None:
            return
        ann, widget = self.param_entries.get("OmegaF", (None, None))
        if not isinstance(widget, ctk.CTkEntry):
            return
        widget.delete(0, "end")
        widget.insert(0, f"{info['svf']:.4f}")
        widget.configure(text_color=HIGHLIGHT_COLOR)

        shading_text = ""
        hour_ann, hour_widget = self.param_entries.get("hour_of_day", (None, None))
        shade_ann, shade_widget = self.param_entries.get("Is_Shaded", (None, None))
        if isinstance(hour_widget, ctk.CTkEntry) and isinstance(shade_widget, ctk.BooleanVar):
            try:
                is_shaded, time_str = fisheye_shading_at_hour(
                    info["timeseries"], hour_widget.get().strip()
                )
                shade_widget.set(is_shaded)
                shading_text = f"; Is_Shaded = {is_shaded} at {time_str}"
            except (KeyError, StopIteration, TypeError, ValueError):
                shading_text = "; Is_Shaded not filled (invalid hour or missing timeseries data)"

        if self.omega_hint_label is not None:
            self.omega_hint_label.configure(
                text=f"✓ SVF = {info['svf']:.4f}{shading_text} obtained from photo (source: {info['path']})",
                text_color=HIGHLIGHT_COLOR,
            )
        if self.omega_clear_btn is not None:
            self.omega_clear_btn.configure(state="normal")
        self.set_status(f"Filled OmegaF = {info['svf']:.4f}{shading_text} from fisheye photo analysis")

    def _clear_fisheye_svf(self):
        self._fisheye_svf_info = None
        ann, widget = self.param_entries.get("OmegaF", (None, None))
        if isinstance(widget, ctk.CTkEntry):
            widget.delete(0, "end")
            widget.configure(text_color=self._omega_default_text_color)
        shade_ann, shade_widget = self.param_entries.get("Is_Shaded", (None, None))
        if isinstance(shade_widget, ctk.BooleanVar):
            shade_widget.set(False)
        if self.omega_hint_label is not None:
            self.omega_hint_label.configure(text="")
        if self.omega_clear_btn is not None:
            self.omega_clear_btn.configure(state="disabled")
        self.set_status("Cleared image-derived OmegaF and Is_Shaded")

    def _update_fisheye_section_visibility(self, fn_name: str):
        if fn_name == "Tmrt_calc":
            self.fisheye_section.pack(side="top", fill="x", padx=8, pady=(0, 8), before=self.middle)
        else:
            self.fisheye_section.pack_forget()

    # ------- Function and form handling -------
    def on_function_change(self, fn_name: str):
        self._update_fisheye_section_visibility(fn_name)
        fn = get_callable(fn_name)
        self.clear_form()
        if fn is None:
            self.set_status(f"Function {fn_name} not found")
            return

        # Docs
        doc = inspect.getdoc(fn) or "No documentation available."
        self.docs_text.configure(state="normal")
        self.docs_text.delete("1.0", "end")
        self.docs_text.insert("1.0", doc)
        self.docs_text.configure(state="disabled")

        # Clear citation when switching functions
        self.clear_citation()

        # Build form, grouped into labeled sections (date/time+location,
        # physiological info, meteorological data, other).
        sig = inspect.signature(fn)
        params = [(n, p) for n, p in sig.parameters.items() if n not in ("self", "cls")]
        grouped: Dict[str, List] = {key: [] for key in GROUP_ORDER}
        for name, param in params:
            grouped[PARAM_GROUP_MAP.get(name, "other")].append((name, param))

        max_cols = 4
        for group_key in GROUP_ORDER:
            items = grouped[group_key]
            if not items:
                continue

            section = ctk.CTkFrame(self.form_frame)
            section.pack(fill="x", padx=4, pady=(8, 4))
            self.param_widgets.append(section)

            title = ctk.CTkLabel(
                section, text=GROUP_TITLES[group_key],
                font=ctk.CTkFont(weight="bold"),
            )
            title.grid(row=0, column=0, columnspan=max_cols, sticky="w", padx=6, pady=(6, 4))

            for idx, (name, param) in enumerate(items):
                row = 1 + (idx // max_cols) * 2
                col = idx % max_cols

                ann = param.annotation
                default = None if param.default is inspect._empty else param.default
                required = param.default is inspect._empty

                label_text = LABEL_ALIASES.get(name, name)
                if required:
                    label_text += " *"
                else:
                    label_text += f" ({default})"
                lbl = ctk.CTkLabel(section, text=label_text, anchor="w")
                lbl.grid(row=row, column=col, sticky="w", padx=6, pady=(2, 0))

                if ann in (bool, "bool") or isinstance(default, bool):
                    var = ctk.BooleanVar(value=bool(default) if default is not None else False)
                    cb = ctk.CTkCheckBox(section, text="", variable=var)
                    cb.grid(row=row + 1, column=col, sticky="w", padx=6, pady=(0, 8))
                    self.param_entries[name] = ("bool", var)
                else:
                    entry = ctk.CTkEntry(section, width=110)
                    if default is not None:
                        entry.insert(0, str(default))
                    entry.grid(row=row + 1, column=col, sticky="w", padx=6, pady=(0, 8))
                    self.param_entries[name] = (ann, entry)
                    if name == "OmegaF":
                        self._omega_default_text_color = entry.cget("text_color")

            for c in range(max_cols):
                section.grid_columnconfigure(c, weight=1)

            if any(name == "OmegaF" for name, _ in items):
                hint_row = 1 + ((len(items) - 1) // max_cols) * 2 + 2
                self.omega_hint_label = ctk.CTkLabel(section, text="", anchor="w", font=ctk.CTkFont(size=11))
                self.omega_hint_label.grid(
                    row=hint_row, column=0, columnspan=max_cols, sticky="w", padx=6, pady=(0, 2)
                )
                self.omega_clear_btn = ctk.CTkButton(
                    section, text="Clear Photo Values", width=140, command=self._clear_fisheye_svf, state="disabled"
                )
                self.omega_clear_btn.grid(row=hint_row + 1, column=0, sticky="w", padx=6, pady=(0, 8))
                self.param_widgets.append(self.omega_hint_label)
                self.param_widgets.append(self.omega_clear_btn)
                if self._fisheye_svf_info is not None:
                    self._apply_fisheye_svf_to_form()

        # Hint
        hint = ctk.CTkLabel(self.form_frame, text="* Required field", text_color="gray")
        hint.pack(anchor="w", padx=8, pady=8)
        self.param_widgets.append(hint)

    def clear_form(self):
        for w in self.param_widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self.param_widgets.clear()
        self.param_entries.clear()
        self.omega_hint_label = None
        self.omega_clear_btn = None

    def clear_citation(self):
        try:
            self.citation_text.configure(state="normal")
            self.citation_text.delete("1.0", "end")
            self.citation_text.configure(state="disabled")
        except Exception:
            pass

    def update_citation(self, fn_name: str):
        text_parts = [CITATION_HEADER]
        body = CITATIONS.get(fn_name)
        if body:
            text_parts.append(body)
        # Append wind exponent note for functions likely using wind reduction (UTCI, PET, mPET/mPET_quick, Tmrt)
        if fn_name in {"UTCI", "PET", "mPET", "mPET_quick", "Tmrt_calc"}:
            text_parts.append("\n" + WIND_EXPONENT_NOTE)
        text = "".join(text_parts)
        self.citation_text.configure(state="normal")
        self.citation_text.delete("1.0", "end")
        self.citation_text.insert("1.0", text)
        self.citation_text.configure(state="disabled")

    # ------- Progress helpers -------
    def show_progress(self, total: int):
        try:
            # guard against zero
            self._progress_total = max(1, int(total))
        except Exception:
            self._progress_total = 1
        self._progress_done = 0
        # reset visuals
        try:
            self.progress_bar.set(0)
            self.progress_label.configure(text="Processing CSV…")
            self.progress_pct.configure(text="0% (0/{} )".format(self._progress_total))
        except Exception:
            pass
        # show frame
        try:
            self.progress_frame.pack(side="bottom", fill="x", expand=False, padx=8, pady=(0, 8))
        except Exception:
            pass

    def update_progress(self, done: int, total: Optional[int] = None):
        if total is None:
            total = getattr(self, "_progress_total", 1)
        # clamp
        if total <= 0:
            total = 1
        if done < 0:
            done = 0
        if done > total:
            done = total
        self._progress_done = done
        frac = done / total
        try:
            self.progress_bar.set(frac)
            self.progress_pct.configure(text=f"{int(frac*100)}% ({done}/{total})")
        except Exception:
            pass

    def finish_progress(self):
        # hide frame and reset
        try:
            self.progress_bar.set(0)
            self.progress_pct.configure(text="")
            self.progress_frame.pack_forget()
        except Exception:
            pass

    def set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        try:
            self.open_btn.configure(state=state)
        except Exception:
            pass
        try:
            self.run_btn.configure(state=state)
        except Exception:
            pass
        try:
            self.format_menu.configure(state=state)
        except Exception:
            pass
        try:
            self.save_btn.configure(state=state)
        except Exception:
            pass
        try:
            self.copy_btn.configure(state=state)
        except Exception:
            pass
        try:
            self.clear_btn.configure(state=state)
        except Exception:
            pass

    # ------- CSV Handling -------
    def on_open_csv(self):
        path = filedialog.askopenfilename(title="Open CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self.process_csv(path)

    def on_drop(self, event):
        # event.data may contain one or several file paths, possibly wrapped in braces {}
        data = event.data
        if not data:
            return
        # Handle multiple files, take the first
        # TkDND sends paths separated by spaces; paths with spaces are enclosed in {}
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
        if not parts:
            return
        first = parts[0]
        if first.lower().endswith(".csv"):
            self.process_csv(first)

    def validate_headers(self, df: pd.DataFrame, sig: inspect.Signature) -> Optional[str]:
        cols = set(df.columns.tolist())
        required = set(
            name for name, p in sig.parameters.items()
            if name not in ("self", "cls") and p.default is inspect._empty
        )
        missing = required - cols
        if missing:
            return f"Missing required columns: {', '.join(sorted(missing))}"
        return None

    def process_csv(self, path: str):
        fn_name = self.fn_var.get()
        fn = get_callable(fn_name)
        if fn is None:
            messagebox.showerror("Error", f"Function {fn_name} not found")
            return
        try:
            df = pd.read_csv(path)
        except Exception as e:
            messagebox.showerror("CSV Error", f"Failed to read CSV: {e}")
            return
        sig = inspect.signature(fn)
        err = self.validate_headers(df, sig)
        if err:
            messagebox.showerror("Header mismatch", err + f"\nExpected at least: {', '.join([k for k in sig.parameters if k not in ('self','cls') and sig.parameters[k].default is inspect._empty])}")
            return

        # Build argument rows
        rows_args: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            kwargs = {}
            for name, p in sig.parameters.items():
                if name in ("self", "cls"):
                    continue
                ann = p.annotation
                if name in df.columns:
                    val = row[name]
                    if pd.isna(val):
                        val = None
                    parsed = parse_value(val, ann)
                else:
                    if p.default is inspect._empty:
                        messagebox.showerror("Error", f"Missing required column {name}")
                        return
                    parsed = p.default
                kwargs[name] = parsed
            rows_args.append(kwargs)

        # Prepare progress and disable controls
        total = len(rows_args)
        self.show_progress(total)
        self.set_controls_enabled(False)
        self.set_status("Processing CSV…")

        # Compute
        results: List[Any] = []
        errors: List[str] = []
        try:
            for i, kwargs in enumerate(rows_args):
                try:
                    res = fn(**kwargs)
                    results.append(res)
                except Exception as e:
                    results.append(None)
                    errors.append(f"Row {i}: {e}")
                # update progress
                self.update_progress(i + 1, total)
                try:
                    self.root.update_idletasks()
                except Exception:
                    pass
        finally:
            # ensure progress bar reaches 100% visual even on exceptions
            self.update_progress(total, total)

        if errors:
            self.set_status(f"Completed with {len(errors)} errors; see console.")
            for e in errors:
                print(e, file=sys.stderr)
        else:
            self.set_status("Completed")

        out_df = self.normalize_results(results)
        # Include original columns alongside result
        joined = pd.concat([df.reset_index(drop=True), out_df], axis=1)
        self.current_output_df = joined
        self.render_table(joined)
        # Show citation suggestions
        self.update_citation(fn_name)
        # Finish progress and re-enable controls
        self.finish_progress()
        self.set_controls_enabled(True)

    # ------- Manual run -------
    def on_run_single(self):
        fn_name = self.fn_var.get()
        fn = get_callable(fn_name)
        if fn is None:
            messagebox.showerror("Error", f"Function {fn_name} not found")
            return
        if fn_name == "Tmrt_calc" and self._fisheye_svf_info is not None:
            self._apply_fisheye_svf_to_form()
        sig = inspect.signature(fn)
        kwargs = {}
        for name, p in sig.parameters.items():
            if name in ("self", "cls"):
                continue
            ann, widget = self.param_entries.get(name, (None, None))
            if widget is None:
                continue
            if isinstance(widget, ctk.CTkEntry):
                text = widget.get().strip()
                val = parse_value(text, ann)
                if (text == "" or val is None) and p.default is inspect._empty:
                    messagebox.showerror("Missing input", f"Required field '{name}' is empty")
                    return
                if text == "" and p.default is not inspect._empty:
                    val = p.default
            else:
                # checkbox case
                if isinstance(widget, ctk.BooleanVar):
                    val = widget.get()
                elif isinstance(widget, tuple) and widget[0] == "bool":
                    # stored as ("bool", var)
                    val = widget[1].get()
                else:
                    # ("bool", BooleanVar)
                    try:
                        val = widget.get()
                    except Exception:
                        val = None
            kwargs[name] = val
        try:
            result = fn(**kwargs)
            out_df = self.normalize_results([result])
            self.current_output_df = out_df
            self.render_table(out_df)
            # Show citation suggestions
            self.update_citation(fn_name)
            self.set_status("Completed")
        except Exception:
            buf = io.StringIO()
            traceback.print_exc(file=buf)
            messagebox.showerror("Execution error", buf.getvalue())
            self.set_status("Error")

    def normalize_results(self, results: List[Any]) -> pd.DataFrame:
        """Convert function results to a DataFrame with reasonable columns.
        - If result is a scalar, name column 'result'.
        - If result is a tuple/list, create columns result_0, result_1, ...
        - If result is a dict/Series, use keys as columns.
        - If result is a pandas object, try to convert accordingly.
        """
        if not results:
            return pd.DataFrame()
        first = results[0]
        # If biometeo returns pandas
        if isinstance(first, pd.DataFrame):
            df = pd.concat(results, ignore_index=True)
        elif isinstance(first, pd.Series):
            df = pd.DataFrame(results)
        # Dicts
        elif isinstance(first, dict):
            df = pd.DataFrame(results)
        # Tuples/lists
        elif isinstance(first, (list, tuple)):
            max_len = max(len(r) if isinstance(r, (list, tuple)) else 1 for r in results)
            cols = [f"result_{i}" for i in range(max_len)]
            norm = []
            for r in results:
                if isinstance(r, (list, tuple)):
                    row = list(r) + [None] * (max_len - len(r))
                else:
                    row = [r] + [None] * (max_len - 1)
                norm.append(row)
            df = pd.DataFrame(norm, columns=cols)
        else:
            # Scalars
            df = pd.DataFrame({"result": results})
        return self.round_numeric(df)

    def round_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """Round float-valued columns to 2 decimal places for display/output."""
        for col in df.columns:
            if pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].round(2)
        return df

    # ------- Table rendering and utilities -------
    def render_table(self, df: pd.DataFrame):
        # Clear current columns and rows
        for col in self.table["columns"]:
            self.table.heading(col, text="")
            self.table.column(col, width=0)
        self.table.delete(*self.table.get_children())

        cols = list(df.columns)
        self.table["columns"] = cols
        for c in cols:
            self.table.heading(c, text=c)
            self.table.column(c, width=120, anchor="center")

        for _, row in df.iterrows():
            values = [self._format_cell(row[c]) for c in cols]
            self.table.insert("", "end", values=values)

    @staticmethod
    def _format_cell(value: Any) -> Any:
        if isinstance(value, float):
            return f"{value:.2f}"
        return value

    def on_table_click_copy(self, event):
        # Identify row and column; copy the cell value to clipboard
        region = self.table.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.table.identify_row(event.y)
        col_id = self.table.identify_column(event.x)  # e.g., '#1'
        if not row_id or not col_id:
            return
        col_index = int(col_id[1:]) - 1
        item = self.table.item(row_id)
        values = item.get("values", [])
        if 0 <= col_index < len(values):
            val = values[col_index]
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append("" if val is None else str(val))
                self.set_status("Copied cell to clipboard")
            except Exception:
                pass

    def on_save_output(self):
        if self.current_output_df is None or self.current_output_df.empty:
            messagebox.showinfo("Save Output", "No output to save yet.")
            return
        fmt = "csv"
        try:
            fmt = (self.format_var.get() or "csv").lower()
        except Exception:
            pass
        if fmt not in ("csv", "json"):
            fmt = "csv"
        # Configure dialog according to format
        if fmt == "json":
            defext = ".json"
            ftypes = [("JSON files", "*.json"), ("All files", "*.*")]
        else:
            defext = ".csv"
            ftypes = [("CSV files", "*.csv"), ("All files", "*.*")]
        path = filedialog.asksaveasfilename(title="Save output", defaultextension=defext, filetypes=ftypes)
        if not path:
            return
        try:
            if fmt == "json":
                text = self.current_output_df.to_json(orient="records", double_precision=2)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            else:
                self.current_output_df.to_csv(path, index=False, float_format="%.2f")
            self.set_status(f"Saved to {path}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def on_copy_output(self):
        if self.current_output_df is None or self.current_output_df.empty:
            messagebox.showinfo("Copy Output", "No output to copy yet.")
            return
        fmt = "csv"
        try:
            fmt = (self.format_var.get() or "csv").lower()
        except Exception:
            pass
        if fmt not in ("csv", "json"):
            fmt = "csv"
        try:
            if fmt == "json":
                text = self.current_output_df.to_json(orient="records", double_precision=2)
            else:
                text = self.current_output_df.to_csv(index=False, float_format="%.2f")
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.set_status(f"Copied {fmt.upper()} to clipboard")
        except Exception as e:
            messagebox.showerror("Copy error", str(e))

    def on_clear_output(self):
        # Clear the table and related output state
        try:
            # Reset headings and column widths
            for col in self.table["columns"]:
                try:
                    self.table.heading(col, text="")
                    self.table.column(col, width=0)
                except Exception:
                    pass
            # Remove all rows
            self.table.delete(*self.table.get_children())
            # Remove column definitions
            self.table["columns"] = []
        except Exception:
            pass
        # Reset stored DataFrame
        self.current_output_df = None
        # Also clear citation suggestions to avoid stale refs
        self.clear_citation()
        # Update status
        self.set_status("Cleared output")

    def set_status(self, text: str):
        self.status_var.set(text)


def main():
    # Use TkinterDnD root if available for drag-and-drop; otherwise, standard Tk
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = ctk.CTk()
    app = App(root)
    root.geometry("1300x1000")
    root.mainloop()


if __name__ == "__main__":
    main()

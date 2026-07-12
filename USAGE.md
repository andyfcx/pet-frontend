# Biometeo Frontend — User Guide

A desktop app that gives the `biometeo` Python package a friendly UI: pick a thermal-comfort function, fill in the parameters (or import a CSV), run it, and export the results.

## Installation

**Option A — pip / uv**

```bash
pip install biometeo-frontend
biometeo-front
```

**Option B — native installer**

Download the macOS `.dmg` or Windows installer from the project's [GitHub Releases](https://github.com/andyfcx/pet-frontend/releases) page and run it. No Python installation required.

> On macOS, the app is only ad-hoc signed. If Gatekeeper blocks it on first launch, right-click the app → **Open**.

## Basic Workflow

1. **Select function** — choose one of `mPET`, `mPET_quick`, `PET`, `Tmrt_calc`, `PMV`, `SET`, `UTCI` from the dropdown. The **Documentation** panel on the right shows the function's docstring, and the input form on the left updates to match its parameters, grouped into:
   - Date/Time & Location
   - Physiological Info
   - Meteorological Data
   - Other Parameters

   Required fields are marked with `*`; optional fields show their default value next to the label.

2. **Provide input** — either:
   - Fill in the form fields and click **Run**, or
   - Click **Open CSV** (or drag a `.csv` file onto the drop area) to batch-process many rows at once. The CSV's column headers must match the function's parameter names; missing required columns will be reported before anything runs.

3. **Review results** — results appear in the table at the bottom. Click any cell to copy its value to the clipboard.

4. **Export** — choose `csv` or `json` from the **Format** dropdown, then **Save Output** (to a file) or **Copy to Clipboard**. **Clear** resets the table and output state.

5. **Citation** — after a run, the panel below the table shows suggested citations for the function you used (and, where relevant, a note about the wind-speed reduction exponent).

## Fisheye Photo → Sky View Factor (Tmrt_calc only)

When `Tmrt_calc` is selected, a collapsible **Fisheye Photo → Sky View Factor** section appears above the form. This lets you compute the Sky View Factor (`OmegaF`) from a fisheye photo instead of entering it manually.

1. Click the section header to expand it.
2. **Select Fisheye Photo**, or drag a photo directly onto the canvas.
3. Set **Date**, **Latitude**, **Longitude**, and **Timezone**.
4. (Optional) Adjust the calibration circle by dragging the center dot (move) or the orange handle (resize) — this preview is for visual reference only and does not affect the actual SVF calculation. **Apply Values** commits typed-in Center X/Y/Radius; **Reset to Auto-Detect** reverts to the automatically detected circle.
5. Click **Run Analysis**. When it finishes:
   - The **SVF** value is shown in a highlighted color, along with the sky mask, sun-path overlay, and a summary of sunlit/shaded/visible minutes.
   - A **Daily Shading Timeline** chart is drawn; hover over a shaded interval to see its start/end time and duration.
   - The computed SVF is **automatically filled into the `OmegaF` field** of the Tmrt_calc form below, highlighted in the same color, with a note showing which photo it came from.
6. To load a different photo, click **Clear** on the fisheye section — this empties the canvas and analysis results so you can drop in a new image.
7. To remove the auto-filled SVF from the form (e.g. to enter `OmegaF` manually instead), click **Clear Photo SVF** next to the `OmegaF` field.
8. **Export Shading Intervals CSV** / **Export Timeline Image** save the shading analysis to a file.

## Tips

- Switching away from `Tmrt_calc` and back preserves the last computed SVF — it's reapplied automatically to the `OmegaF` field.
- Dragging files (photos or CSVs) requires the app to support drag-and-drop; if it's unavailable in your build, use the **Select** / **Open CSV** buttons instead.

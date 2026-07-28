"""Framework-agnostic logic shared by the customtkinter GUI (main.py) and the
Textual TUI (tui/). Nothing in this module imports tkinter, customtkinter, or
textual, so it can be used by either front end unchanged.
"""

import datetime
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

try:
    import biometeo as bm
except Exception as e:  # pragma: no cover - optional at runtime
    bm = None
    bm_import_error = e
else:
    bm_import_error = None


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

# Functions that likely use wind-speed reduction and should show the extra note.
WIND_EXPONENT_FUNCTIONS = {"UTCI", "PET", "mPET", "mPET_quick", "Tmrt_calc"}

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
    "day_of_year": "Date (YYYY-MM-DD)",
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


def day_of_year_to_date_str(day_of_year: int, year: Optional[int] = None) -> str:
    """Render a day-of-year as an example YYYY-MM-DD date in `year` (defaults
    to the current year), used to seed the Tmrt date input with a concrete
    date instead of a bare day-of-year number.
    """
    if year is None:
        year = datetime.date.today().year
    return (datetime.date(year, 1, 1) + datetime.timedelta(days=int(day_of_year) - 1)).isoformat()


def date_str_to_day_of_year(date_str: str) -> int:
    """Parse a YYYY-MM-DD date string into the day-of-year integer that
    biometeo's Tmrt_calc requires (it has no direct date parameter)."""
    try:
        parsed = datetime.date.fromisoformat(date_str.strip())
    except ValueError as e:
        raise ValueError(f"Invalid date '{date_str}': expected YYYY-MM-DD") from e
    return parsed.timetuple().tm_yday


def humidity_target_param(sig: inspect.Signature) -> Optional[str]:
    """Return 'RH' or 'VP' if the callable accepts exactly one of the two
    humidity parameters, else None (neither, or both independently)."""
    has_vp = "VP" in sig.parameters
    has_rh = "RH" in sig.parameters
    if has_vp and not has_rh:
        return "VP"
    if has_rh and not has_vp:
        return "RH"
    return None


def resolve_humidity_value(target: str, Ta: Any, RH: Optional[float], VP: Optional[float]) -> float:
    """Return the value for the humidity parameter `target` ('RH' or 'VP')
    that a biometeo function needs, given the user's mutually-exclusive RH/VP
    input. Converts via biometeo.VP_RH_exchange when the user supplied the
    other unit instead.
    """
    if RH is not None and VP is not None:
        raise ValueError("Enter only one of RH or VP, not both")
    if RH is None and VP is None:
        raise ValueError("Enter a value for RH or VP")
    if (target == "RH" and RH is not None) or (target == "VP" and VP is not None):
        return RH if target == "RH" else VP
    if bm is None:
        raise RuntimeError(f"biometeo is not available: {bm_import_error}")
    return bm.VP_RH_exchange(Ta=Ta, RH=RH, VP=VP)[target]


def group_signature_params(fn: Callable) -> Dict[str, List[Tuple[str, inspect.Parameter]]]:
    """Group a callable's parameters into labeled sections, in GROUP_ORDER."""
    sig = inspect.signature(fn)
    params = [(n, p) for n, p in sig.parameters.items() if n not in ("self", "cls")]
    grouped: Dict[str, List[Tuple[str, inspect.Parameter]]] = {key: [] for key in GROUP_ORDER}
    for name, param in params:
        grouped[PARAM_GROUP_MAP.get(name, "other")].append((name, param))
    return grouped


def build_citation_text(fn_name: str) -> str:
    """Build the full citation-suggestion text for a given function name."""
    text_parts = [CITATION_HEADER]
    body = CITATIONS.get(fn_name)
    if body:
        text_parts.append(body)
    if fn_name in WIND_EXPONENT_FUNCTIONS:
        text_parts.append("\n" + WIND_EXPONENT_NOTE)
    return "".join(text_parts)


def validate_headers(df: pd.DataFrame, sig: inspect.Signature) -> Optional[str]:
    cols = set(df.columns.tolist())
    required = set(
        name for name, p in sig.parameters.items()
        if name not in ("self", "cls") and p.default is inspect._empty
    )
    target = humidity_target_param(sig)
    if target is not None:
        required.discard(target)
        if not (cols & {"RH", "VP"}):
            required.add("RH or VP")
    missing = required - cols
    if missing:
        return f"Missing required columns: {', '.join(sorted(missing))}"
    return None


def round_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Round float-valued columns to 2 decimal places for display/output."""
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].round(2)
    return df


def normalize_results(results: List[Any], fn_name: str = "result") -> pd.DataFrame:
    """Convert function results to a DataFrame with reasonable columns.
    - If result is a scalar, name the column after the selected function.
    - If result is a tuple/list, create function-prefixed columns.
    - If result is a dict/Series, use keys as columns.
    - If result is a pandas object, try to convert accordingly.

    Values retain their original precision. Each front end applies the user's
    selected precision only when displaying or exporting the DataFrame.
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
        # biometeo's PET() names its primary output key "PET_v"; the other
        # functions already name theirs after the function (e.g. mPET's
        # "mPET" key), so align PET with that convention for display.
        df = df.rename(columns={"PET_v": "PET"})
    # Tuples/lists
    elif isinstance(first, (list, tuple)):
        max_len = max(len(r) if isinstance(r, (list, tuple)) else 1 for r in results)
        cols = [f"{fn_name}_{i}" for i in range(max_len)]
        norm = []
        for r in results:
            if isinstance(r, (list, tuple)):
                row = list(r) + [None] * (max_len - len(r))
            else:
                row = [r] + [None] * (max_len - 1)
            norm.append(row)
        df = pd.DataFrame(norm, columns=cols)
    else:
        # Scalars (e.g. UTCI and SET)
        df = pd.DataFrame({fn_name: results})
    return df

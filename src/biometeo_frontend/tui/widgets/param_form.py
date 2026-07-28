"""Dynamic, reflection-based parameter input form.

Mirrors main.py's on_function_change()/clear_form()/on_run_single() form
logic (customtkinter) but built from Textual widgets instead.
"""

import inspect
from typing import Any, Dict, List, Optional, Tuple

from textual import events
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label

from biometeo_frontend import core


class GridInput(Input):
    """Input that hands Left/Right off to the owning ParamForm's grid
    navigation once the cursor is at the start/end of the text, instead of
    always moving the text cursor.
    """

    def __init__(self, *args, owner_form: "ParamForm", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.owner_form = owner_form

    def action_cursor_left(self, select: bool = False) -> None:
        if not select and self.cursor_position == 0:
            self.owner_form.move_focus(self, 0, -1)
        else:
            super().action_cursor_left(select)

    def action_cursor_right(self, select: bool = False) -> None:
        if not select and self.cursor_at_end and not self._suggestion:
            self.owner_form.move_focus(self, 0, 1)
        else:
            super().action_cursor_right(select)


class ParamForm(VerticalScroll):
    """Responsive, dynamically-rebuilt form for the selected function."""

    MAX_COLUMNS = 8
    MIN_COLUMN_WIDTH = 14

    DEFAULT_CSS = """
    ParamForm {
        width: 1fr;
        height: 1fr;
        border: round $primary-background-lighten-2;
        padding: 0 1;
    }
    ParamForm .group-title {
        text-style: bold;
        margin-top: 1;
    }
    ParamForm .param-grid {
        grid-size: 8;
        grid-gutter: 0 1;
        height: auto;
        margin-bottom: 1;
    }
    ParamForm .param-cell {
        height: auto;
    }
    ParamForm .param-label {
        color: $text-muted;
    }
    ParamForm .required-hint {
        color: $text-muted;
        margin-top: 1;
    }
    ParamForm .svf-hint {
        margin-top: 1;
    }
    ParamForm .svf-filled {
        color: $success;
        text-style: bold;
    }
    ParamForm .humidity-box {
        border: solid blue;
        padding: 0 1;
        height: auto;
        column-span: 2;
    }
    ParamForm .humidity-row {
        height: auto;
    }
    ParamForm .humidity-col {
        width: 1fr;
        height: auto;
        margin-right: 1;
    }
    ParamForm .humidity-hint {
        color: $text-muted;
        text-align: center;
        width: 1fr;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("up", "nav_up", "Field up", show=False),
        Binding("down", "nav_down", "Field down", show=False),
        Binding("left", "nav_left", "Field left", show=False),
        Binding("right", "nav_right", "Field right", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.param_entries: Dict[str, Tuple[Any, Any]] = {}
        self.omega_hint: Optional[Label] = None
        self.omega_clear_btn: Optional[Button] = None
        self.current_fn_name: Optional[str] = None
        # 'RH' or 'VP' when the current function accepts exactly one of the
        # two and the form offers both fields as mutually-exclusive inputs.
        self._humidity_target: Optional[str] = None
        # Rows of field widgets (Input/Checkbox), in visual grid order, used
        # for arrow-key navigation between cells (see move_focus()).
        self._nav_rows: List[List[Any]] = []
        self._nav_groups: List[List[Any]] = []
        self._column_count = self.MAX_COLUMNS

    def rebuild(self, fn_name: str) -> None:
        """Tear down and rebuild the whole form for the given function name."""
        self.current_fn_name = fn_name
        self.remove_children()
        self.param_entries = {}
        self.omega_hint = None
        self.omega_clear_btn = None
        self._humidity_target = None
        self._nav_rows = []
        self._nav_groups = []

        fn = core.get_callable(fn_name)
        if fn is None:
            self.mount(Label(f"Function {fn_name} not found"))
            return

        self._humidity_target = core.humidity_target_param(inspect.signature(fn))
        grouped = core.group_signature_params(fn)
        sections = []
        for group_key in core.GROUP_ORDER:
            items = grouped[group_key]
            if not items:
                continue

            cells = []
            field_widgets = []
            for name, param in items:
                ann = param.annotation
                default = None if param.default is inspect._empty else param.default
                required = param.default is inspect._empty

                if self._humidity_target is not None and name == self._humidity_target:
                    rh_input = GridInput(value="", owner_form=self)
                    vp_input = GridInput(value="", owner_form=self)
                    self.param_entries["RH"] = (ann, rh_input)
                    self.param_entries["VP"] = (ann, vp_input)
                    field_widgets.append(rh_input)
                    cells.append(Vertical(
                        Horizontal(
                            Vertical(
                                Label(core.LABEL_ALIASES.get("RH", "RH"), classes="param-label"),
                                rh_input,
                                classes="humidity-col",
                            ),
                            Vertical(
                                Label(core.LABEL_ALIASES.get("VP", "VP"), classes="param-label"),
                                vp_input,
                                classes="humidity-col",
                            ),
                            classes="humidity-row",
                        ),
                        Label("(Enter RH or VP)", classes="humidity-hint"),
                        classes="param-cell humidity-box",
                    ))
                    continue

                # Tmrt_calc's day_of_year param only accepts a day-of-year
                # integer, but users think in dates, so the form shows a
                # YYYY-MM-DD field and converts to day-of-year on run.
                is_day_of_year = name == "day_of_year"
                display_default = core.day_of_year_to_date_str(default) if is_day_of_year and default is not None else default

                label_text = core.LABEL_ALIASES.get(name, name)
                label_text += " *" if required else f" ({display_default})"

                if ann in (bool, "bool") or isinstance(default, bool):
                    widget = Checkbox(value=bool(default) if default is not None else False)
                    self.param_entries[name] = ("bool", widget)
                else:
                    widget = GridInput(value="" if display_default is None else str(display_default), owner_form=self)
                    self.param_entries[name] = (ann, widget)

                field_widgets.append(widget)
                cells.append(Vertical(Label(label_text, classes="param-label"), widget, classes="param-cell"))

            self._nav_groups.append(field_widgets)

            section_children = [Label(core.GROUP_TITLES[group_key], classes="group-title"), Grid(*cells, classes="param-grid")]

            if any(name == "OmegaF" for name, _ in items):
                self.omega_hint = Label("", classes="svf-hint")
                self.omega_clear_btn = Button("Clear Photo Values", id="clear-photo-values-btn", disabled=True)
                section_children.extend([self.omega_hint, self.omega_clear_btn])

            sections.append(Vertical(*section_children))

        sections.append(Label("* Required field", classes="required-hint"))
        self.mount_all(sections)
        self.call_after_refresh(self._update_column_count, self.size.width)

    def on_resize(self, event: events.Resize) -> None:
        """Use up to eight columns, shrinking only on narrower terminals."""
        self._update_column_count(event.size.width)

    def _update_column_count(self, width: int) -> None:
        columns = max(1, min(self.MAX_COLUMNS, width // self.MIN_COLUMN_WIDTH))
        if columns == self._column_count and self._nav_rows:
            return
        self._column_count = columns
        for grid in self.query(Grid):
            grid.styles.grid_size_columns = columns
        self._nav_rows = []
        for widgets in self._nav_groups:
            for row_start in range(0, len(widgets), columns):
                self._nav_rows.append(widgets[row_start:row_start + columns])

    # ------- Arrow-key grid navigation -------
    def move_focus(self, current: Any, drow: int, dcol: int) -> None:
        """Move focus from `current` by (drow, dcol) within the field grid."""
        pos = None
        for row_idx, row in enumerate(self._nav_rows):
            for col_idx, widget in enumerate(row):
                if widget is current:
                    pos = (row_idx, col_idx)
                    break
            if pos is not None:
                break
        if pos is None:
            return
        row_idx, col_idx = pos

        if dcol != 0:
            target_row = self._nav_rows[row_idx]
            new_col = col_idx + dcol
            if 0 <= new_col < len(target_row):
                target_row[new_col].focus()
            return

        new_row = row_idx + drow
        if 0 <= new_row < len(self._nav_rows):
            target_row = self._nav_rows[new_row]
            target_col = min(col_idx, len(target_row) - 1)
            target_row[target_col].focus()

    def action_nav_up(self) -> None:
        if self.screen.focused is not None:
            self.move_focus(self.screen.focused, -1, 0)

    def action_nav_down(self) -> None:
        if self.screen.focused is not None:
            self.move_focus(self.screen.focused, 1, 0)

    def action_nav_left(self) -> None:
        if self.screen.focused is not None:
            self.move_focus(self.screen.focused, 0, -1)

    def action_nav_right(self) -> None:
        if self.screen.focused is not None:
            self.move_focus(self.screen.focused, 0, 1)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Enforce RH/VP mutual exclusion: filling one disables (and clears)
        the other, since only one may be entered at a time."""
        if self._humidity_target is None:
            return
        rh_widget = self.param_entries.get("RH", (None, None))[1]
        vp_widget = self.param_entries.get("VP", (None, None))[1]
        if event.input is rh_widget:
            other = vp_widget
        elif event.input is vp_widget:
            other = rh_widget
        else:
            return
        if other is None:
            return
        if event.value.strip():
            if other.value:
                other.value = ""
            other.disabled = True
        else:
            other.disabled = False

    def read_values(self) -> Dict[str, Any]:
        """Read and parse current form values, raising ValueError on a missing
        required field (mirrors on_run_single's validation, main.py).
        """
        fn = core.get_callable(self.current_fn_name)
        if fn is None:
            raise ValueError(f"Function {self.current_fn_name} not found")
        sig = inspect.signature(fn)
        target = core.humidity_target_param(sig)
        kwargs: Dict[str, Any] = {}
        for name, p in sig.parameters.items():
            if name in ("self", "cls") or name == target:
                continue
            ann, widget = self.param_entries.get(name, (None, None))
            if widget is None:
                continue
            if isinstance(widget, Checkbox):
                val = widget.value
            elif name == "day_of_year":
                text = widget.value.strip()
                if text == "":
                    if p.default is inspect._empty:
                        raise ValueError(f"Required field '{name}' is empty")
                    val = p.default
                else:
                    val = core.date_str_to_day_of_year(text)
            else:
                text = widget.value.strip()
                val = core.parse_value(text, ann)
                if (text == "" or val is None) and p.default is inspect._empty:
                    raise ValueError(f"Required field '{name}' is empty")
                if text == "" and p.default is not inspect._empty:
                    val = p.default
            kwargs[name] = val

        if target is not None:
            target_ann = self.param_entries.get(target, (None, None))[0]
            rh_widget = self.param_entries.get("RH", (None, None))[1]
            vp_widget = self.param_entries.get("VP", (None, None))[1]
            rh_val = core.parse_value(rh_widget.value, target_ann) if isinstance(rh_widget, Input) else None
            vp_val = core.parse_value(vp_widget.value, target_ann) if isinstance(vp_widget, Input) else None
            kwargs[target] = core.resolve_humidity_value(target, kwargs.get("Ta"), rh_val, vp_val)
        return kwargs

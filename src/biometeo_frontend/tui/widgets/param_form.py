"""Dynamic, reflection-based parameter input form.

Mirrors main.py's on_function_change()/clear_form()/on_run_single() form
logic (customtkinter) but built from Textual widgets instead.
"""

import inspect
from typing import Any, Dict, Optional, Tuple

from textual.app import ComposeResult
from textual.containers import Grid, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label

from biometeo_frontend import core


class ParamForm(VerticalScroll):
    """Scrollable, dynamically-rebuilt parameter form for the selected function."""

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
        grid-size: 2;
        grid-gutter: 0 2;
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
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.param_entries: Dict[str, Tuple[Any, Any]] = {}
        self.omega_hint: Optional[Label] = None
        self.omega_clear_btn: Optional[Button] = None
        self.current_fn_name: Optional[str] = None

    def rebuild(self, fn_name: str) -> None:
        """Tear down and rebuild the whole form for the given function name."""
        self.current_fn_name = fn_name
        self.remove_children()
        self.param_entries = {}
        self.omega_hint = None
        self.omega_clear_btn = None

        fn = core.get_callable(fn_name)
        if fn is None:
            self.mount(Label(f"Function {fn_name} not found"))
            return

        grouped = core.group_signature_params(fn)
        sections = []
        for group_key in core.GROUP_ORDER:
            items = grouped[group_key]
            if not items:
                continue

            cells = []
            for name, param in items:
                ann = param.annotation
                default = None if param.default is inspect._empty else param.default
                required = param.default is inspect._empty

                label_text = core.LABEL_ALIASES.get(name, name)
                label_text += " *" if required else f" ({default})"

                if ann in (bool, "bool") or isinstance(default, bool):
                    widget = Checkbox(value=bool(default) if default is not None else False)
                    self.param_entries[name] = ("bool", widget)
                else:
                    widget = Input(value="" if default is None else str(default))
                    self.param_entries[name] = (ann, widget)

                cells.append(Vertical(Label(label_text, classes="param-label"), widget, classes="param-cell"))

            section_children = [Label(core.GROUP_TITLES[group_key], classes="group-title"), Grid(*cells, classes="param-grid")]

            if any(name == "OmegaF" for name, _ in items):
                self.omega_hint = Label("", classes="svf-hint")
                self.omega_clear_btn = Button("Clear Photo Values", id="clear-photo-values-btn", disabled=True)
                section_children.extend([self.omega_hint, self.omega_clear_btn])

            sections.append(Vertical(*section_children))

        sections.append(Label("* Required field", classes="required-hint"))
        self.mount_all(sections)

    def read_values(self) -> Dict[str, Any]:
        """Read and parse current form values, raising ValueError on a missing
        required field (mirrors on_run_single's validation, main.py).
        """
        fn = core.get_callable(self.current_fn_name)
        if fn is None:
            raise ValueError(f"Function {self.current_fn_name} not found")
        sig = inspect.signature(fn)
        kwargs: Dict[str, Any] = {}
        for name, p in sig.parameters.items():
            if name in ("self", "cls"):
                continue
            ann, widget = self.param_entries.get(name, (None, None))
            if widget is None:
                continue
            if isinstance(widget, Checkbox):
                val = widget.value
            else:
                text = widget.value.strip()
                val = core.parse_value(text, ann)
                if (text == "" or val is None) and p.default is inspect._empty:
                    raise ValueError(f"Required field '{name}' is empty")
                if text == "" and p.default is not inspect._empty:
                    val = p.default
            kwargs[name] = val
        return kwargs

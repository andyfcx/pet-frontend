"""Entry point for the Textual TUI front end (biometeo-front-tui)."""

from textual.app import App

from biometeo_frontend.core import bm_import_error
from biometeo_frontend.tui.screens import MainScreen


class BiometeoTUIApp(App):
    TITLE = "Biometeo TUI"

    def on_mount(self) -> None:
        self.push_screen(MainScreen())
        if bm_import_error is not None:
            self.notify(f"Failed to import biometeo: {bm_import_error}", severity="error", timeout=10)


def main() -> None:
    BiometeoTUIApp().run()


if __name__ == "__main__":
    main()

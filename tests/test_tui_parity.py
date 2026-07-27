import tempfile
import unittest
from pathlib import Path

import pandas as pd
from textual.widgets import Button, Select, TextArea

from biometeo_frontend.tui.app import BiometeoTUIApp
from biometeo_frontend.tui.widgets.param_form import ParamForm


class TUIParityTests(unittest.IsolatedAsyncioTestCase):
    async def test_latest_gui_output_and_documentation_flow(self) -> None:
        app = BiometeoTUIApp()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            screen = app.screen

            self.assertFalse(screen.query_one("#docs-back-btn", Button).display)
            self.assertEqual(len(screen.query("#citation-pane")), 0)
            controls = screen.query_one("#output-controls")
            self.assertLessEqual(controls.region.bottom, app.size.height - 1)

            output = pd.DataFrame({"UTCI": [1.23456789]})
            screen.current_output_df = output
            screen.current_output_fn = "UTCI"

            decimals = screen.query_one("#decimals-select", Select)
            decimals.value = 4
            await pilot.pause()
            self.assertEqual(screen._format_cell(1.23456789), "1.2346")

            with tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "output.csv"
                screen._on_save_path(path)
                self.assertIn("1.2346", path.read_text(encoding="utf-8"))

            docs = screen.query_one("#docs-text", TextArea)
            self.assertIn("Universal Thermal Climate Index", docs.text)
            self.assertTrue(screen.query_one("#docs-back-btn", Button).display)

            screen._show_function_docs()
            self.assertFalse(screen.query_one("#docs-back-btn", Button).display)
            self.assertNotIn("The citation about Python package", docs.text)

    async def test_form_expands_to_eight_columns_on_a_wide_terminal(self) -> None:
        app = BiometeoTUIApp()
        async with app.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            app.screen.query_one("#fn-select", Select).value = "Tmrt_calc"
            await pilot.pause()
            form = app.screen.query_one(ParamForm)

            self.assertEqual(form._column_count, 8)
            self.assertTrue(all(len(row) <= 8 for row in form._nav_rows))
            self.assertEqual(form.max_scroll_y, 0)


if __name__ == "__main__":
    unittest.main()

import inspect
import unittest

import pandas as pd

from biometeo_frontend import core


class HumidityConversionTests(unittest.TestCase):
    def test_target_param_detects_single_humidity_field(self) -> None:
        self.assertEqual(core.humidity_target_param(inspect.signature(core.bm.mPET)), "VP")
        self.assertEqual(core.humidity_target_param(inspect.signature(core.bm.Tmrt_calc)), "RH")

    def test_group_signature_params_offers_both_rh_and_vp(self) -> None:
        grouped = core.group_signature_params(core.bm.mPET)
        meteo_names = [name for name, _ in grouped["meteo"]]
        self.assertIn("RH", meteo_names)
        self.assertIn("VP", meteo_names)

    def test_resolve_humidity_value_passes_through_matching_unit(self) -> None:
        self.assertEqual(core.resolve_humidity_value("VP", Ta=25, RH=None, VP=15.0), 15.0)

    def test_resolve_humidity_value_converts_other_unit(self) -> None:
        converted = core.resolve_humidity_value("VP", Ta=25, RH=50, VP=None)
        self.assertAlmostEqual(converted, 15.81, places=1)

    def test_resolve_humidity_value_rejects_both_given(self) -> None:
        with self.assertRaises(ValueError):
            core.resolve_humidity_value("RH", Ta=25, RH=50, VP=15.0)

    def test_resolve_humidity_value_rejects_neither_given(self) -> None:
        with self.assertRaises(ValueError):
            core.resolve_humidity_value("RH", Ta=25, RH=None, VP=None)


class NormalizeResultsTests(unittest.TestCase):
    def test_scalar_uses_function_name_and_keeps_precision(self) -> None:
        result = core.normalize_results([1.23456789], "UTCI")

        self.assertEqual(list(result.columns), ["UTCI"])
        self.assertEqual(result.iloc[0, 0], 1.23456789)

    def test_sequence_uses_function_prefixed_columns(self) -> None:
        result = core.normalize_results([(1.0, 2.0), (3.0,)], "PET")

        self.assertEqual(list(result.columns), ["PET_0", "PET_1"])
        self.assertTrue(pd.isna(result.iloc[1, 1]))

    def test_mapping_keeps_its_own_column_names(self) -> None:
        result = core.normalize_results([{"mPET": 24.125, "status": "ok"}], "mPET")

        self.assertEqual(list(result.columns), ["mPET", "status"])


if __name__ == "__main__":
    unittest.main()

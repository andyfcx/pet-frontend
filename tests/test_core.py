import unittest

import pandas as pd

from biometeo_frontend import core


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

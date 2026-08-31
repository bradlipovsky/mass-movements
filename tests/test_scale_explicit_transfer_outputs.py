import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class TransferOutputTests(unittest.TestCase):
    def test_complete_registered_outputs(self):
        root = Path("data/scale_explicit_transfer")
        long = pd.read_csv(root / "equivalent_area_long.csv", dtype={"region": str})
        decisions = pd.read_csv(root / "decisions.csv", dtype={"region": str})
        strata, overall = pd.read_csv(root / "stratum_decisions.csv"), pd.read_csv(root / "overall_decision.csv")
        self.assertEqual((len(long), len(decisions), len(strata), len(overall)), (40, 8, 2, 1))
        self.assertEqual(set(long.variant), {"p00", "p10", "p01", "p11", "r90"})
        self.assertFalse(long.duplicated(["region", "stratum", "variant"]).any())
        self.assertEqual(list(decisions.columns), "region,stratum,reference_equivalent_area_m2,area_90m_m2,departure_90m,phase_mean_area_m2,phase_cv,structural_zero,zero_reference_positive_variant,reference_departure_bound,reference_phase_cv_bound,usable_transfer,resolution_pass,phase_pass,window_pass".split(","))
        np.testing.assert_allclose(long.equivalent_steep_area_m2, long.weighted_cell_sum * long.spacing_m**2)
        for row in decisions.itertuples(index=False):
            group = long[(long.region == row.region) & (long.stratum == row.stratum)].set_index("variant")
            phases = group.loc[["p00", "p10", "p01", "p11"], "equivalent_steep_area_m2"].to_numpy()
            self.assertAlmostEqual(row.departure_90m, abs(group.at["r90", "equivalent_steep_area_m2"] - phases[0]) / phases[0])
            self.assertAlmostEqual(row.phase_cv, np.std(phases) / np.mean(phases))
        self.assertTrue((decisions[["usable_transfer", "resolution_pass", "phase_pass", "window_pass"]] == "yes").all().all())
        self.assertTrue((strata.stratum_pass == "yes").all() and overall.at[0, "transfer_gate_pass"] == "yes")
        for path in (root / "equivalent_area_long.csv", root / "decisions.csv", root / "stratum_decisions.csv", root / "overall_decision.csv"):
            self.assertTrue(path.read_bytes().endswith(b"\n") and b"\r" not in path.read_bytes())

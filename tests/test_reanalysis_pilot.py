import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reanalysis_pilot as pilot  # noqa: E402

class ReanalysisEquationsTest(unittest.TestCase):
    def test_nearest_two_and_longitude_wrap(self):
        grid = np.arange(0.0, 360.0, 0.25)
        self.assertEqual(list(pilot.nearest_two(grid, 10.0)), [10.0, 9.75])
        self.assertEqual(list(pilot.nearest_two(grid, 10.13)), [10.25, 10.0])
        self.assertEqual(list(pilot.nearest_two(grid, 359.9, circular=True)), [0.0, 359.75])

    def test_utc_window_end_is_exclusive(self):
        time0 = np.datetime64("1940-01-01T00:00:00")
        indices = pilot.interval_indices(time0, "2021-02-07", 2004, -7, 0)
        self.assertEqual(len(indices), 168)
        self.assertTrue(np.all(np.diff(indices) == 1))
        stop = int((np.datetime64("2004-02-07") - time0) / np.timedelta64(1, "h"))
        self.assertEqual(indices[-1], stop - 1)

    def test_midrank_and_fixed_lapse_cancellation(self):
        controls = np.array([1.0, 2.0, 2.0, 4.0])
        self.assertEqual(pilot.midrank(2.0, controls), 0.5)
        correction = 6.5 * 1.2
        self.assertEqual(pilot.midrank(2.0, controls),
                         pilot.midrank(2.0 - correction, controls - correction))

    def test_theil_sen_decomposition(self):
        years = np.arange(1979, 2026)
        values = 250.0 + 0.2 * (years - 1979)
        values[years == 2005] += 5.0
        matched = pd.DataFrame({"candidate_id": "test", "grid_latitude_deg": 0.0,
                                "grid_longitude_deg_east": 0.0, "primary_cell": True,
                                "year": years, "window": "7d", "hours": 168,
                                "mean_t2m_k": values})
        cells = pd.DataFrame({"candidate_id": ["test"], "grid_latitude_deg": [0.0],
                              "grid_longitude_deg_east": [0.0], "event_year": [2005],
                              "primary_cell": [True], "dependence_component": ["test"],
                              "component_representative": [True]})
        result = pilot.derive_diagnostics(matched, cells).iloc[0]
        self.assertAlmostEqual(result.theil_sen_k_per_decade, 2.0)
        self.assertEqual(result.linear_trend_residual_rank, 1.0)
        shifted = matched.assign(mean_t2m_k=matched.mean_t2m_k - 7.8)
        shifted_result = pilot.derive_diagnostics(shifted, cells).iloc[0]
        for field in ("warm_state_anomaly_k", "warm_state_rank", "theil_sen_k_per_decade",
                      "fitted_change_1991_to_event_k", "linear_trend_residual_rank"):
            self.assertAlmostEqual(result[field], shifted_result[field])


class ReanalysisOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "data" / "reanalysis"
        with open(cls.out / "retrieval_manifest.json") as stream:
            cls.manifest = json.load(stream)
        read = lambda name: pd.read_csv(cls.out / name, float_precision="round_trip")
        cls.cells, cls.matched = read("event_cells.csv"), read("matched_windows.csv")
        cls.diagnostics = read("diagnostics.csv")
        cls.air, cls.probes = read("above_freezing_sensitivity.csv"), read("cross_layout_probes.csv")

    def test_frozen_sample_and_cell_selection(self):
        self.assertEqual(self.cells.candidate_id.nunique(), 29)
        self.assertEqual(len(self.cells), 116)
        self.assertTrue((self.cells.groupby("candidate_id").size() == 4).all())
        self.assertEqual(int(self.cells.primary_cell.sum()), 29)
        for _, group in self.cells.groupby("candidate_id"):
            selected = group[group.primary_cell].iloc[0]
            order = group.sort_values(["land_fraction", "distance_km",
                                       "grid_latitude_deg", "grid_longitude_deg_east"],
                                      ascending=[False, True, True, True]).iloc[0]
            self.assertEqual(selected.cell_rank, order.cell_rank)

    def test_registered_output_dimensions_and_bounds(self):
        self.assertEqual(len(self.matched), 27260)
        self.assertEqual(len(self.diagnostics), 580)
        self.assertEqual(len(self.air), 696)
        self.assertTrue(self.diagnostics[["warm_state_rank", "linear_trend_residual_rank"]]
                        .apply(lambda column: column.between(0, 1).all()).all())
        expected_hours = {"2d": 48, "7d": 168, "7d_buffered": 168,
                          "30d": 720, "event_day": 24}
        self.assertTrue((self.matched.hours == self.matched.window.map(expected_hours)).all())
        self.assertTrue(self.matched.mean_t2m_k.between(180, 340).all())

    def test_provenance_hashes_and_probes(self):
        self.assertEqual(self.manifest["protocol_commit"], pilot.PROTOCOL_COMMIT)
        self.assertEqual(self.manifest["icechunk_snapshot"], pilot.SNAPSHOT)
        self.assertEqual(self.manifest["audit_amendment_commit"], pilot.AUDIT_AMENDMENT_COMMIT)
        self.assertEqual(self.manifest["source_uri"], pilot.SOURCE_URI)
        self.assertTrue(self.probes.exact_match.all())
        for filename, expected in self.manifest["catalog_input_sha256"].items():
            self.assertEqual(pilot.sha256(ROOT / filename), expected)
        for filename, expected in self.manifest["output_sha256"].items():
            self.assertEqual(pilot.sha256(self.out / filename), expected)
        for filename, expected in self.manifest["source_sha256"].items():
            self.assertEqual(pilot.sha256(self.out / "source" / filename), expected)

    def test_saved_means_reproduce_saved_diagnostics(self):
        rebuilt = pilot.derive_diagnostics(self.matched, self.cells)
        columns = ["candidate_id", "grid_latitude_deg", "grid_longitude_deg_east", "window"]
        saved = self.diagnostics.sort_values(columns).reset_index(drop=True)
        rebuilt = rebuilt.sort_values(columns).reset_index(drop=True)
        self.assertTrue(np.allclose(saved.linear_trend_residual_rank,
                                    rebuilt.linear_trend_residual_rank, rtol=0, atol=2e-16))


if __name__ == "__main__":
    unittest.main()

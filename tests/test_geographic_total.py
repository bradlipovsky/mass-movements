import hashlib, unittest
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np, pandas as pd
from scripts.geographic_total import HASHES, REPAIR_RELATIVE_TOLERANCE, admissible_repair, coverage_estimates, diagnostics, estimates, population, verify
from scripts.geographic_total_source import OUTPUT, cell_label, cells, dem_requests, expected_dem_ids, grid, pzi_request, pzi_requests
class GeographicTotalTests(unittest.TestCase):
    def test_frozen_request_universe_and_edges(self):
        self.assertEqual((len(cells()), len(dem_requests()), len(pzi_requests())), (96, 776, 54))
        self.assertEqual((pzi_request(-60)["row0"], pzi_request(-60)["rows"], pzi_request(-60)["byte_end"]), (17868, 132, 3110399999))
        self.assertEqual(pzi_request(-59)["rows"], 144)
        self.assertEqual(len(expected_dem_ids(0, 179)), 9)
        self.assertEqual([item.split("_00_")[1][:4] for item in expected_dem_ids(0, 179)[:3]], ["W180", "E178", "E179"])
        self.assertEqual(cell_label(-6, 7), "s-006_w+0007")
    def test_grids_and_frozen_programs(self):
        shape, affine, _ = grid(0, 0, "p00")
        self.assertEqual((shape[0] % 3, shape[1] % 3, affine.c % 30, affine.f % 30), (0, 0, 0, 0))
        verify()
        self.assertEqual(REPAIR_RELATIVE_TOLERANCE, 1e-8)
        self.assertEqual(int(population().sum()), 1826)
        for name, expected in HASHES.items(): self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(), expected)
    def test_projection_repair_gate(self):
        good=Mock(geom_type="Polygon", is_empty=False, is_valid=True)
        self.assertTrue(all(admissible_repair(good, *x) for x in [(0, 0), (1e-8, 0), (0, 1e-8)]))
        self.assertFalse(any(admissible_repair(good, *x) for x in [(1.00000001e-8, 0), (0, 1.00000001e-8)]))
        self.assertFalse(any(admissible_repair(Mock(geom_type=t, is_empty=e, is_valid=v), 0, 0) for t,e,v in [("LineString",False,True),("Polygon",True,True),("Polygon",False,False)]))
    def test_ht_variance_covariance_and_conservative_zero_rse(self):
        rows=[]
        for key, g, p in (("a", 1., 2.), ("b", 3., 6.)):
            for outcome, value in (("glacier_proximity", g), ("permafrost", p)):
                rows.append(dict(cell_key=key, stratum=outcome, dominant_region="01", stratum_population_cells=4,
                    stratum_sample_cells=2, inclusion_probability=.5, reference_equivalent_area_m2=value, cell_quality_pass="yes"))
        with patch("scripts.geographic_total.population", return_value=pd.Series({"01": 4})):
            strata, covariance, totals = estimates(pd.DataFrame(rows))
        np.testing.assert_allclose(totals.estimated_total_m2, [8, 16]); np.testing.assert_allclose(totals.SE_m2, np.sqrt([8, 32]))
        self.assertEqual((len(strata), len(covariance), covariance.iloc[0].covariance_contribution_m4), (2, 1, 16))
        self.assertTrue((totals.precision_pass == "no").all())
        with patch("scripts.geographic_total.population", return_value=pd.Series({"01": 4})):
            _, _, zero = estimates(pd.DataFrame(rows).assign(reference_equivalent_area_m2=1.))
        self.assertTrue((zero.precision_pass == "no").all() and np.isinf(zero.degrees_of_freedom).all())
    def test_coverage_inference_uses_complete_frame(self):
        table=cells()[["dominant_region", "stratum_population_cells", "stratum_sample_cells"]].copy()
        table=table.assign(variant="p00", spacing_m=30, report_center_count=10, complete_dem_support_count=5,
            glacier_predicate_coverage_count=10, outside_RGI_center_count=4, outside_RGI_finite_PZI_count=3)
        result=coverage_estimates(table)
        np.testing.assert_allclose(result.mean_cell_coverage_fraction, [.5, 1, .75]); np.testing.assert_allclose(result.expanded_area_coverage_ratio, [.5, 1, .75])
        self.assertTrue((result.mean_cell_variance.abs() < 1e-30).all())
    def test_structural_zero_uses_mask_specific_coverage(self):
        cell = cells().iloc[0]; key = cell.cell_key; variants = ["p00", "p10", "p01", "p11", "r90"]
        records = pd.DataFrame([dict(window_key=key, stratum="glacier_proximity", variant=v, equivalent_steep_area_m2=0.) for v in variants])
        coverage = pd.DataFrame([dict(cell_key=key, glacier_proximity_center_count=2,
            glacier_proximity_complete_dem_count=1, outside_RGI_center_count=1, outside_RGI_finite_PZI_count=1,
            PZI_mask_center_count=0, PZI_mask_complete_dem_count=0) for _ in variants])
        result = diagnostics(records, coverage).iloc[0]
        self.assertEqual((result.structural_zero, result.coverage_limited_zero, result.adequate_coverage_zero, result.phase_cv), ("yes", "yes", "no", 0))
    @unittest.skipUnless((OUTPUT / "source_replay.csv").exists(), "source staging pending")
    def test_source_freeze_replay_and_schema(self):
        replay=pd.read_csv(OUTPUT / "source_replay.csv"); coverage=pd.read_csv(OUTPUT / "source_coverage.csv")
        self.assertEqual((len(replay), len(coverage), replay.value_sha256.equals(replay.replay_value_sha256)), (480, 480, True))
        self.assertTrue(replay[["stored_crs_equal", "replay_affine_equal", "finite_mask_equal"]].all().all())
        self.assertTrue((replay.replay_max_abs_difference == 0).all())
        from scripts.geographic_total import layers
        from scripts.denominator_pilot import aggregate_3x3
        cell=cells().iloc[0]
        np.testing.assert_array_equal(layers(None, cell.south, cell.west, "r90")[0], aggregate_3x3(layers(None, cell.south, cell.west, "p00")[0]))
if __name__ == "__main__": unittest.main()

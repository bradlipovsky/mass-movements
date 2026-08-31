import hashlib, json, subprocess
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from affine import Affine
from shapely import box

from scripts.scale_explicit_steep_area import (
    PHASES,
    center_coordinates,
    comparisons,
    disk_offsets,
    integrate,
    plane_gradient,
    steepness_weight,
    vector_masks,
)
from scripts.susceptible_area_convergence import phase_grid


class ScaleExplicitSteepAreaTests(unittest.TestCase):
    def test_disk_counts_and_moments(self):
        for spacing, shape, count, denominator in ((30, (21, 21), 317, 7205400),
                                                    (90, (9, 9), 37, 874800)):
            u, v, disk = disk_offsets(spacing)
            self.assertEqual((disk.shape, int(disk.sum())), (shape, count))
            self.assertEqual((u[disk].sum(), v[disk].sum(), (u * v)[disk].sum()), (0, 0, 0))
            self.assertEqual((int((u * u)[disk].sum()), int((v * v)[disk].sum())),
                             (denominator, denominator))

    def test_signed_plane_recovery_at_both_spacings(self):
        for spacing in (30, 90):
            size = 2 * int(np.ceil(300 / spacing)) + 9
            rows, columns = np.indices((size, size))
            x, y = columns * spacing + 1234, -rows * spacing - 567
            z = 900 + 0.2 * x - 0.1 * y
            a, b, complete = plane_gradient(z, spacing)
            center = (size // 2, size // 2)
            self.assertTrue(complete[center])
            self.assertAlmostEqual(a[center], 0.2, places=12)
            self.assertAlmostEqual(b[center], -0.1, places=12)
            shifted_a, shifted_b, _ = plane_gradient(z + 4321, spacing)
            self.assertAlmostEqual(shifted_a[center], a[center], places=12)
            self.assertAlmostEqual(shifted_b[center], b[center], places=12)

    def test_strict_nodata_support(self):
        z = np.ones((31, 31), dtype=float)
        center = (15, 15)
        _, _, complete = plane_gradient(z, 30)
        self.assertTrue(complete[center])
        z[15, 16] = np.nan
        a, b, complete = plane_gradient(z, 30)
        self.assertFalse(complete[center])
        self.assertTrue(np.isnan(a[center]) and np.isnan(b[center]))
        z[:] = 1
        z[5, 5] = np.nan
        _, _, complete = plane_gradient(z, 30)
        self.assertTrue(complete[center])

    def test_registered_gradient_weight(self):
        beta = np.array([0, 25, 30, 35, 50, np.nan])
        weight = steepness_weight(np.tan(np.radians(beta)))
        expected_30 = ((np.tan(np.radians(30)) - np.tan(np.radians(25))) /
                       (np.tan(np.radians(35)) - np.tan(np.radians(25))))
        self.assertTrue(np.allclose(weight[:2], [0, 0]))
        self.assertAlmostEqual(weight[2], expected_30)
        self.assertTrue(np.allclose(weight[3:5], [1, 1]))
        self.assertTrue(np.isnan(weight[5]))

    def test_closed_vector_distance_center_predicate(self):
        affine = Affine(1, 0, -101.5, 0, -1, 5.5)
        shape = (1, 213)
        x, y = center_coordinates(shape, affine)
        self.assertEqual((x[0, 0], x[0, -1], y[0, 0]), (-101, 111, 5))
        inside, proximity = vector_masks([box(0, 0, 10, 10)], shape, affine)
        at = lambda coordinate: int(coordinate + 101)
        self.assertFalse(proximity[0, at(-101)])
        self.assertTrue(proximity[0, at(-100)])
        self.assertTrue(proximity[0, at(-99)])
        self.assertFalse(proximity[0, at(0)])
        self.assertTrue(inside[0, at(0)] and inside[0, at(5)] and inside[0, at(10)])
        self.assertTrue(proximity[0, at(110)])
        self.assertFalse(proximity[0, at(111)])
        diagonal = 100 / np.sqrt(2)
        corner_affine = Affine(1, 0, -diagonal - 0.5, 0, -1e-6,
                               -diagonal + 0.5e-6)
        _, corner_proximity = vector_masks([box(0, 0, 10, 10)], (2, 1), corner_affine)
        self.assertTrue(corner_proximity[0, 0])
        self.assertFalse(corner_proximity[1, 0])

    def test_weighted_area_and_phase_grid(self):
        weight = np.array([[0.25, 0.5, 0.75], [1, 0, 0.5]])
        report = np.ones(weight.shape, dtype=bool)
        mask = np.array([[1, 1, 0], [1, 1, 1]], dtype=bool)
        complete = np.array([[1, 1, 1], [1, 0, 1]], dtype=bool)
        support, weighted_cells, area = integrate(weight, report, mask, complete, 30)
        self.assertEqual((int(support.sum()), weighted_cells, area), (4, 2.25, 2025))
        for dx, dy in PHASES.values():
            _, transform = phase_grid((-31, -46, 68, 77), dx, dy)
            self.assertEqual((transform.c % 30, (transform.f % 30)), (dx, dy))

    def test_comparisons_have_no_pass_label_and_handle_zero(self):
        variants = [*PHASES, "r90"]
        records = pd.DataFrame([dict(region="00", stratum="glacier_proximity", variant=v,
                                     equivalent_steep_area_m2=a)
                                for v, a in zip(variants, [100, 110, 90, 100, 80])])
        hard = pd.DataFrame([dict(region="00", stratum="glacier_contact", departure_90m=0.3)])
        compared, diagnostics = comparisons(records, hard)
        self.assertAlmostEqual(diagnostics.iloc[0].phase_cv, np.std([100, 110, 90, 100]) / 100)
        self.assertEqual(diagnostics.iloc[0].departure_90m, 0.2)
        self.assertFalse(any("pass" in column for column in (*compared.columns, *diagnostics.columns)))
        zero = records.assign(equivalent_steep_area_m2=0)
        zero_records, zero_diagnostics = comparisons(zero, hard)
        self.assertTrue((zero_records.fractional_departure == 0).all())
        self.assertEqual(zero_diagnostics.iloc[0].structural_zero, "yes")
        zero_30_positive_90 = zero.copy()
        zero_30_positive_90.loc[zero_30_positive_90.variant == "r90",
                                "equivalent_steep_area_m2"] = 1
        edge_records, edge_diagnostics = comparisons(zero_30_positive_90, hard)
        self.assertTrue(edge_records.fractional_departure.isna().all())
        self.assertTrue(np.isnan(edge_diagnostics.iloc[0].phase_cv))

    def test_program_has_no_forbidden_input_path(self):
        for path in ("scripts/scale_explicit_steep_area.py",
                     "notebooks/scale_explicit_steep_area.ipynb"):
            text = Path(path).read_text()
            for forbidden in ("data/candidate", "data/catalog", "data/event", "data/audit",
                              "data/reanalysis"):
                self.assertNotIn(forbidden, text)

    @unittest.skipUnless(Path("data/scale_explicit_steep_area/diagnostics.csv").exists(),
                         "development artifact has not been executed")
    def test_development_artifact_schema(self):
        long = pd.read_csv("data/scale_explicit_steep_area/equivalent_area_long.csv",
                           dtype={"region": str})
        diagnostics = pd.read_csv("data/scale_explicit_steep_area/diagnostics.csv",
                                  dtype={"region": str})
        self.assertEqual((len(long), len(diagnostics)), (30, 6))
        self.assertEqual(set(long.variant), {*PHASES, "r90"})
        self.assertEqual(set(long.stratum), {"glacier_proximity", "permafrost"})
        self.assertFalse(any("pass" in column for column in (*long.columns, *diagnostics.columns)))
        self.assertEqual(list(long.columns), "region,region_name,south,west,window_key,window_sha256,variant,spacing_m,phase_x_m,phase_y_m,support_radius_m,ramp_lower_deg,ramp_upper_deg,report_cell_count,support_disk_cell_count,complete_support_cell_count,stratum,mask_definition,stratum_center_count,integration_cell_count,weighted_cell_sum,equivalent_steep_area_m2,reference_equivalent_area_m2,area_ratio,fractional_departure,structural_zero".split(","))
        self.assertEqual(list(diagnostics.columns), "region,stratum,reference_equivalent_area_m2,area_90m_m2,departure_90m,phase_mean_area_m2,phase_cv,structural_zero,zero_reference_positive_variant,hard_threshold_departure_90m,reference_departure_bound,reference_phase_cv_bound,interpretation".split(","))
        self.assertFalse(long.duplicated(["region", "stratum", "variant"]).any())
        self.assertEqual(set(zip(long.support_radius_m, long.ramp_lower_deg, long.ramp_upper_deg)), {(300, 25, 35)})
        self.assertEqual(set(zip(long.variant, long.spacing_m, long.phase_x_m, long.phase_y_m, long.support_disk_cell_count)), {("p00", 30, 0, 0, 317), ("p10", 30, 15, 0, 317), ("p01", 30, 0, 15, 317), ("p11", 30, 15, 15, 317), ("r90", 90, 0, 0, 37)})
        self.assertTrue(((long.integration_cell_count <= long.stratum_center_count) & (long.integration_cell_count <= long.complete_support_cell_count) & (long.complete_support_cell_count <= long.report_cell_count)).all())
        self.assertTrue(np.isfinite(long[["weighted_cell_sum", "equivalent_steep_area_m2", "area_ratio", "fractional_departure"]]).all().all() and (long[["weighted_cell_sum", "equivalent_steep_area_m2", "area_ratio", "fractional_departure"]] >= 0).all().all())
        np.testing.assert_allclose(long.equivalent_steep_area_m2, long.weighted_cell_sum * long.spacing_m**2)
        for observed, expected in ((long.area_ratio, long.equivalent_steep_area_m2 / long.reference_equivalent_area_m2), (long.fractional_departure, abs(long.equivalent_steep_area_m2 / long.reference_equivalent_area_m2 - 1))): np.testing.assert_allclose(observed, expected)
        hard = pd.read_csv("data/area_convergence/decisions.csv", dtype={"region": str})
        for row in diagnostics.itertuples(index=False):
            group = long[(long.region == row.region) & (long.stratum == row.stratum)].set_index("variant")
            phases = group.loc[list(PHASES), "equivalent_steep_area_m2"].to_numpy()
            self.assertAlmostEqual(row.departure_90m, abs(group.at["r90", "equivalent_steep_area_m2"] / group.at["p00", "equivalent_steep_area_m2"] - 1))
            self.assertAlmostEqual(row.phase_cv, np.std(phases) / np.mean(phases))
            hard_stratum = "glacier_contact" if row.stratum == "glacier_proximity" else row.stratum
            self.assertAlmostEqual(row.hard_threshold_departure_90m, hard[(hard.region == row.region) & (hard.stratum == hard_stratum)].departure_90m.iloc[0])
        for path in ("data/scale_explicit_steep_area/equivalent_area_long.csv", "data/scale_explicit_steep_area/diagnostics.csv"):
            self.assertTrue(Path(path).read_bytes().endswith(b"\n") and b"\r" not in Path(path).read_bytes())

    @unittest.skipUnless(Path("data/scale_explicit_steep_area/freeze_manifest.json").exists(), "final freeze pending")
    def test_final_freeze_manifest(self):
        manifest = json.loads(Path("data/scale_explicit_steep_area/freeze_manifest.json").read_text())
        self.assertLessEqual(manifest["code_budget"]["total_lines"], 400)
        for path, item in manifest["files"].items():
            raw = (subprocess.check_output(["git", "show", f'{manifest["artifact_commit"]}:{path}'])
                   if item["snapshot_at_artifact_commit"] else Path(path).read_bytes())
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (item["bytes"], item["sha256"]))


if __name__ == "__main__":
    unittest.main()

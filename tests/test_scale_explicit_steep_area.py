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

    def test_program_has_no_forbidden_input_path(self):
        text = Path("scripts/scale_explicit_steep_area.py").read_text()
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


if __name__ == "__main__":
    unittest.main()

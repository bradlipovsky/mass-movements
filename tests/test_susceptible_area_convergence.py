import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from shapely import box

from scripts.denominator_pilot import burn, slope_degrees
from scripts.susceptible_area_convergence import (
    PHASES,
    comparisons,
    eligible_windows,
    local_crs,
    phase_grid,
    rank_regions,
    window_geometry,
)


class SusceptibleAreaConvergenceTests(unittest.TestCase):
    def test_registered_region_and_prefixed_window_selectors(self):
        regions = ["02", "03", "04", "06", "07", "08", "09", "10",
                   "12", "14", "15", "16", "17", "18"]
        ranked = rank_regions(regions)
        self.assertEqual([row[1] for row in ranked[:3]], ["07", "08", "03"])
        frozen = pd.read_csv("data/area_convergence/region_selection.csv", dtype={"region": str})
        self.assertEqual(frozen.sort_values("selection_rank").region.tolist(),
                         [row[1] for row in ranked])
        rows = ([{"cenlat": 1.2, "cenlon": 181.2, "area_km2": 0.1}] * 10 +
                [{"cenlat": 2.2, "cenlon": -177.8, "area_km2": 0.2}] * 10)
        eligible = eligible_windows(rows, "03")
        keys = {row[1] for row in eligible}
        self.assertEqual(keys, {"rgi7.0|03|south=+01|west=-179",
                                "rgi7.0|03|south=+02|west=-178"})
        for digest, key, *_ in eligible:
            expected = hashlib.sha256(
                f"susceptible-area-heldout-window-v1|{key}".encode()).hexdigest()
            self.assertEqual(digest, expected)

    def test_phase_grids_cover_bounds_and_preserve_lattice_residues(self):
        bounds = (-31, -46, 68, 77)
        for _, (dx, dy) in PHASES.items():
            shape, affine = phase_grid(bounds, dx, dy, 3 if (dx, dy) == (0, 0) else 1)
            lower_y = affine.f - 30 * shape[0]
            self.assertLessEqual(affine.c, bounds[0])
            self.assertLessEqual(lower_y, bounds[1])
            self.assertGreaterEqual(affine.c + 30 * shape[1], bounds[2])
            self.assertGreaterEqual(affine.f, bounds[3])
            self.assertEqual((affine.c % 30, lower_y % 30), (dx, dy))
        shape, _ = phase_grid(bounds, multiple=3)
        self.assertEqual((shape[0] % 3, shape[1] % 3), (0, 0))

    def test_planar_slope_and_area_are_translation_invariant(self):
        for dx, dy in PHASES.values():
            affine = Affine(30, 0, -30 + dx, 0, -30, 150 + dy)
            yy, xx = np.indices((6, 6))
            x = affine.c + (xx + 0.5) * 30
            y = affine.f - (yy + 0.5) * 30
            z = 2 * x - y
            slope = slope_degrees(z, 30)
            self.assertTrue(np.allclose(slope[1:-1, 1:-1], np.degrees(np.arctan(np.sqrt(5)))))
            self.assertEqual(int(burn([box(7, 7, 127, 127)], z.shape, affine).sum()), 16)
        area30 = burn([box(7, 7, 187, 187)], (8, 8), Affine(30, 0, -30, 0, -30, 210)).sum() * 30**2
        area90 = burn([box(7, 7, 187, 187)], (4, 4), Affine(90, 0, -90, 0, -90, 270)).sum() * 90**2
        self.assertEqual(area30, area90)

    def test_decision_math_and_zero_rules(self):
        def frame(values):
            rows = []
            for variant, area in zip((*PHASES, "r90"), values):
                rows.append(dict(region="00", stratum="glacier_contact", slope_deg=30,
                                 contact_m=100, pzi_min=np.nan, variant=variant,
                                 susceptible_area_m2=area))
            return pd.DataFrame(rows)
        records, decision = comparisons(frame([100, 100, 110, 90, 80]))
        self.assertAlmostEqual(decision.iloc[0].phase_cv, np.std([100, 100, 110, 90]) / 100)
        self.assertEqual((decision.iloc[0].resolution_pass, decision.iloc[0].phase_pass),
                         ("yes", "yes"))
        self.assertEqual(records.loc[records.variant == "p00", "area_ratio"].iloc[0], 1)
        zero, zero_decision = comparisons(frame([0, 0, 0, 0, 0]))
        self.assertTrue(zero.area_ratio.isna().all())
        self.assertTrue((zero.fractional_departure == 0).all())
        self.assertEqual((zero_decision.iloc[0].structural_zero,
                          zero_decision.iloc[0].window_pass), ("yes", "yes"))
        _, failure = comparisons(frame([0, 1, 0, 0, 0]))
        self.assertEqual((failure.iloc[0].zero_reference_positive_variant,
                          failure.iloc[0].window_pass), ("yes", "no"))

    def test_frozen_sources_and_artifacts_match_registered_dimensions(self):
        manifest = json.loads(Path("data/area_convergence/source_manifest.json").read_text())
        remote = manifest["remote_objects"] + manifest["range_objects"]
        self.assertEqual(len({item["id"] for item in remote}), len(remote))
        self.assertEqual(set(manifest["access_terms"]), {"Copernicus DEM", "Gruber PZI", "RGI"})
        self.assertEqual(manifest["access_terms"]["Gruber PZI"]["attribution_party"],
                         "World Glacier Monitoring Service (WGMS)")
        self.assertEqual(set(manifest["staging"]["unavailable_dem_tiles"]),
                         {"dem_07_N76_00_E018_00", "dem_07_N76_00_E019_00"})
        listed = {item["path"] for item in manifest["local_objects"]}
        actual = {str(path) for path in Path("data/area_convergence/source").iterdir()
                  if path.is_file()}
        self.assertEqual(listed, actual)
        for item in manifest["local_objects"]:
            self.assertEqual(hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest(),
                             item["sha256"])
        windows = pd.read_csv("data/area_convergence/windows.csv", dtype={"region": str})
        for row in windows.itertuples(index=False):
            _, projected = window_geometry(row.south, row.west, local_crs(row.south, row.west))
            for variant, (dx, dy) in PHASES.items():
                with rasterio.open(f"data/area_convergence/source/dem_{row.region}_{variant}_30m.tif") as ds:
                    expected = phase_grid(projected.buffer(1000).bounds, dx, dy,
                                          3 if variant == "p00" else 1)
                    self.assertEqual((ds.shape, ds.transform), expected)
        areas = pd.read_csv("data/area_convergence/area_long.csv", dtype={"region": str})
        decisions = pd.read_csv("data/area_convergence/decisions.csv", dtype={"region": str})
        self.assertEqual((len(areas), len(decisions)), (225, 6))
        keys = ["region", "stratum", "variant", "slope_deg", "contact_m", "pzi_min"]
        self.assertFalse(areas.duplicated(keys).any())
        self.assertEqual(set(areas.variant), {*PHASES, "r90"})
        self.assertTrue((decisions.phase_pass == "yes").all())
        self.assertTrue((decisions.stratum_pass == "no").all())
        freeze = json.loads(Path("data/area_convergence/freeze_manifest.json").read_text())
        self.assertLessEqual(freeze["registered_code_budget"]["total_lines"], 420)
        for file_name, item in freeze["files"].items():
            self.assertEqual(hashlib.sha256(Path(file_name).read_bytes()).hexdigest(),
                             item["sha256"])

    def test_program_contains_no_forbidden_input(self):
        for path in (Path("scripts/susceptible_area_convergence.py"),
                     Path("notebooks/susceptible_area_convergence.ipynb")):
            text = path.read_text()
            for forbidden in ("candidates.csv", "event_audit", "data/reanalysis"):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()

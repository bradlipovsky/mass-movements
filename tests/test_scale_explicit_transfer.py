import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import pandas as pd

from scripts.scale_explicit_transfer import (
    ESTIMATOR,
    ESTIMATOR_SHA256,
    attach_decisions,
    transfer_layers,
)
from scripts.scale_explicit_transfer_source import WINDOWS, dem_sources, tile_name
from scripts.scale_explicit_transfer_selection import (
    REGIONS,
    SOURCE,
    UNOPENED,
    attribute_rows,
    selection_tables,
)
from scripts.susceptible_area_convergence import eligible_windows, rank_regions


class ScaleExplicitTransferSelectionTests(unittest.TestCase):
    def test_frozen_region_ranking(self):
        ranking = rank_regions(UNOPENED)
        self.assertEqual([row[1] for row in ranking[:4]], ["10", "18", "15", "04"])
        expected = {
            "10": "5b16eb47c0f2b54bea77eabd0dea16b33b9bdd8a9783f0c5049511d56a08cf9e",
            "18": "639be755f4b9273620eb69e3d29225955514d050c7b77f3564f5086fe65c4f60",
            "15": "69d3cfbe87ae15f42742f7a7fbd17c3b1d7b446bc522bee3793df72d0556719f",
            "04": "73ee9d1d5eecc4ea0cf63fe6fae52e0b8148ed6e5e463cb1e0da65d01e20bb47",
        }
        self.assertEqual({region: digest for digest, region, _ in ranking if region in REGIONS},
                         expected)

    def test_registered_eligibility_and_digest_prefix(self):
        rows = [dict(cenlon="180.2", cenlat="-0.1", area_km2="0.1") for _ in range(10)]
        selected = eligible_windows(rows, "10")
        self.assertEqual(len(selected), 1)
        digest, key, south, west, count, area = selected[0]
        self.assertEqual((key, south, west, count, area),
                         ("rgi7.0|10|south=-01|west=-180", -1, -180, 10, 1.0))
        self.assertEqual(digest, hashlib.sha256(
            f"susceptible-area-heldout-window-v1|{key}".encode()).hexdigest())
        with self.assertRaises(ValueError):
            eligible_windows(rows[:9], "10")

    def test_attribute_tables_have_fixed_region_and_selector_fields(self):
        for region, (_, attribute_name) in REGIONS.items():
            rows = attribute_rows(SOURCE / attribute_name)
            self.assertGreaterEqual(len(rows), 10)
            self.assertEqual({row["o1region"] for row in rows}, {region})
            self.assertTrue(all(row["cenlon"] and row["cenlat"] and row["area_km2"]
                                for row in rows))

    def test_selector_has_no_terrain_or_case_input(self):
        text = Path("scripts/scale_explicit_transfer_selection.py").read_text().lower()
        for forbidden in ("candidate", "catalog", "event", "audit", "reanalysis", "pzi",
                          "dem_", "deformation", "damage", "consequence"):
            self.assertNotIn(forbidden, text)

    @unittest.skipUnless(Path("data/scale_explicit_transfer/windows.csv").exists(),
                         "inventory-only selection has not been executed")
    def test_complete_selection_artifacts(self):
        eligible, selected = selection_tables()
        saved = pd.read_csv("data/scale_explicit_transfer/eligible_windows.csv",
                            dtype={"region": str})
        windows = pd.read_csv("data/scale_explicit_transfer/windows.csv", dtype={"region": str})
        pd.testing.assert_frame_equal(saved, eligible, check_exact=False, rtol=0, atol=1e-12)
        pd.testing.assert_frame_equal(windows, selected, check_exact=False, rtol=0, atol=1e-12)
        self.assertEqual(list(windows.region), list(REGIONS))
        self.assertTrue((windows.window_rank == 1).all())
        self.assertFalse(saved.duplicated(["region", "south", "west"]).any())

    def test_selection_manifest_seals_preterrain_boundary(self):
        manifest = json.loads(Path(
            "data/scale_explicit_transfer/selection_manifest.json").read_text())
        self.assertFalse(manifest["preterrain_boundary"]["dem_accessed"])
        self.assertFalse(manifest["preterrain_boundary"]["pzi_accessed"])
        self.assertEqual(manifest["selection"]["eligible_window_count"], 199)
        self.assertEqual(len(manifest["selection"]["windows"]), 4)
        for name, expected in manifest["artifacts"].items():
            raw = subprocess.check_output(
                ["git", "show", f"ad64acdc80611d443bfa46c941de1ff241d9b5c3:{name}"])
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                             (expected["size_bytes"], expected["sha256"]))

    def test_registered_estimator_and_source_replay(self):
        self.assertEqual(hashlib.sha256(ESTIMATOR.read_bytes()).hexdigest(),
                         ESTIMATOR_SHA256)
        self.assertEqual(tile_name(-45, -79),
                         "Copernicus_DSM_COG_10_S45_00_W079_00_DEM")
        self.assertEqual({region: len(dem_sources(south, west))
                          for region, (south, west) in WINDOWS.items()},
                         {"10": 9, "18": 8, "15": 9, "04": 9})
        replay = pd.read_csv("data/scale_explicit_transfer/source_replay.csv",
                             dtype={"region": str})
        self.assertEqual((len(replay), set(replay.layer)),
                         (20, {"p00", "p10", "p01", "p11", "pzi"}))
        self.assertTrue((replay.value_sha256 == replay.replay_value_sha256).all())
        self.assertTrue(replay.replay_affine_equal.all())
        self.assertTrue((replay.replay_max_abs_difference == 0).all())

    def test_source_manifest_and_coverage_are_complete(self):
        manifest = json.loads(Path(
            "data/scale_explicit_transfer/source/source_manifest.json").read_text())
        self.assertEqual(len(manifest["dem_objects"]), 36)
        self.assertEqual(manifest["unavailable_dem_tiles"], ["dem_18_S45_E172"])
        self.assertEqual(len(manifest["pzi_range_objects"]), 4)
        for name, expected in manifest["files"].items():
            raw = Path(name).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                             (expected["bytes"], expected["sha256"]))
        coverage = pd.read_csv("data/scale_explicit_transfer/source_coverage.csv",
                               dtype={"region": str})
        self.assertEqual((len(coverage), set(coverage.region), set(coverage.variant)),
                         (20, set(WINDOWS), {"p00", "p10", "p01", "p11", "r90"}))
        for column in ("dem_finite_center_count", "pzi_finite_center_count",
                       "glacier_predicate_coverage_count",
                       "pzi_outside_glacier_coverage_count"):
            self.assertTrue((coverage[column] <= coverage.report_cell_count).all())

    def test_transfer_grid_anchor_and_registered_decisions(self):
        z, affine, report, glacier, pzi, spacing, _ = transfer_layers("10", 65, 145, "r90")
        self.assertEqual((z.shape, report.shape, glacier.shape, pzi.shape, spacing),
                         (report.shape, report.shape, report.shape, report.shape, 90))
        self.assertEqual((affine.a, affine.e), (90, -90))
        variants = ["p00", "p10", "p01", "p11", "r90"]
        records = pd.DataFrame([
            dict(region="00", stratum=stratum, variant=variant,
                 equivalent_steep_area_m2=value)
            for stratum, values in (("glacier_proximity", [100, 105, 95, 100, 90]),
                                    ("permafrost", [0, 0, 0, 0, 0]))
            for variant, value in zip(variants, values)])
        attached, decisions = attach_decisions(records)
        passing = decisions[decisions.stratum == "glacier_proximity"].iloc[0]
        zero = decisions[decisions.stratum == "permafrost"].iloc[0]
        self.assertAlmostEqual(passing.departure_90m, 0.1)
        self.assertAlmostEqual(passing.phase_cv, pd.Series([100, 105, 95, 100]).std(ddof=0) / 100)
        self.assertEqual((passing.window_pass, zero.structural_zero,
                          zero.usable_transfer, zero.window_pass), ("yes", "yes", "no", "no"))
        self.assertTrue(attached[attached.stratum == "permafrost"].area_ratio.isna().all())

    def test_transfer_code_has_no_forbidden_input(self):
        text = Path("scripts/scale_explicit_transfer.py").read_text().lower()
        for forbidden in ("data/candidate", "data/catalog", "data/event", "data/audit",
                          "data/reanalysis", "deformation", "damage", "consequence"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()

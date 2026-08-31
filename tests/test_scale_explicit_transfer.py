import hashlib
import json
import unittest
from pathlib import Path

import pandas as pd

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
            artifact = Path(name)
            self.assertEqual(artifact.stat().st_size, expected["size_bytes"])
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),
                             expected["sha256"])


if __name__ == "__main__":
    unittest.main()

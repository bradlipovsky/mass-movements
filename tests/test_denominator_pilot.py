import hashlib
import json
import math
import subprocess
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from pyproj import CRS, Transformer
from shapely import box
from scripts.denominator_pilot import (
    aggregate_3x3,
    burn,
    component_rows,
    contact_distance,
    local_crs,
    pzi_classes,
    select_window,
    slope_degrees,
    summarize,
    volume_fields,
    WINDOWS,
)
class DenominatorPilotTests(unittest.TestCase):
    def test_selector_uses_registered_eligibility_and_longitude_wrap(self):
        rows = []
        for _ in range(10):
            rows.append({"cenlat": 58.2, "cenlon": 205.2, "area_km2": 0.1})
            rows.append({"cenlat": 59.2, "cenlon": -153.8, "area_km2": 0.2})
        rows.append({"cenlat": 57.2, "cenlon": -156.8, "area_km2": 99})
        digest, south, west, count, area = select_window(rows, "01")
        candidates = {
            "rgi7.0|01|south=+58|west=-155": (58, -155, 1.0),
            "rgi7.0|01|south=+59|west=-154": (59, -154, 2.0),
        }
        key = min(candidates, key=lambda value: __import__("hashlib").sha256(value.encode()).hexdigest())
        self.assertEqual((south, west, count), (*candidates[key][:2], 10))
        self.assertAlmostEqual(area, candidates[key][2])
        self.assertEqual(len(digest), 64)
    def test_selector_rejects_no_eligible_cell(self):
        with self.assertRaises(ValueError):
            select_window([{"cenlat": 1, "cenlon": 2, "area_km2": 5}], "01")
    def test_planar_slope_and_nodata_support(self):
        yy, xx = np.indices((12, 12))
        z = 90 * xx - 120 * yy + 10.0
        slope = slope_degrees(z, 30)
        self.assertTrue(np.allclose(slope[1:-1, 1:-1], np.degrees(np.arctan(5))))
        self.assertTrue(np.isnan(slope[[0, -1]]).all())
        z[3, 3] = np.nan
        slope = slope_degrees(z, 30)
        self.assertTrue(np.isnan(slope[3, 2:5]).all())
        self.assertTrue(np.isnan(slope[2:5, 3]).all())
        self.assertEqual(np.nanmax(slope_degrees(np.ones((4, 4)), 30)), 0)
        z[3, 3] = 90 * 3 - 120 * 3 + 10.0
        for values, spacing, pixels in ((slope_degrees(z, 30), 30, 100),
                                        (slope_degrees(aggregate_3x3(z), 90), 90, 4)):
            rows = component_rows(values >= 60, np.isfinite(values), spacing, {})
            self.assertEqual((len(rows), rows[0]["area_m2"]), (1, pixels * spacing**2))
    def test_strict_three_by_three_aggregation(self):
        z = np.arange(36, dtype=float).reshape(6, 6)
        expected = np.array([[7, 10], [25, 28]], dtype=float)
        self.assertTrue(np.array_equal(aggregate_3x3(z), expected))
        z[0, 0] = np.nan
        self.assertTrue(np.isnan(aggregate_3x3(z)[0, 0]))
        with self.assertRaises(ValueError):
            aggregate_3x3(np.ones((4, 3)))
    def test_pixel_center_rasterization(self):
        affine = Affine(1, 0, 0, 0, -1, 2)
        mask = burn([box(0, 1, 1, 2)], (2, 2), affine)
        self.assertTrue(np.array_equal(mask, [[True, False], [False, False]]))
    def test_contact_distance_and_four_neighbor_objects(self):
        glacier = np.zeros((5, 5), dtype=bool)
        glacier[2, 2] = True
        distance = contact_distance(glacier, 30)
        self.assertEqual(distance[2, 3], 0)
        self.assertGreater(distance[3, 3], 0)
        mask = np.zeros((5, 5), dtype=bool)
        mask[1, 1] = mask[2, 2] = True
        rows = component_rows(mask, np.ones_like(mask), 30, {})
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["edge_truncated"] == "no" for row in rows))
    def test_boundary_flag_and_inclusive_volume(self):
        mask = np.zeros((4, 4), dtype=bool)
        mask[0, 1] = True
        row = component_rows(mask, np.ones_like(mask), 10, {})[0]
        self.assertEqual(row["edge_truncated"], "yes")
        self.assertEqual(volume_fields(100_000)["eligible_d10"], "yes")
        self.assertEqual(volume_fields(99_999)["eligible_d10"], "no")
    def test_pzi_background_fringe_thresholds_and_nodata_are_distinct(self):
        pzi = np.array([np.nan, 0, 0.01, 0.099, 0.1, 0.5, 1])
        primary, sensitivity, fringe, background = pzi_classes(pzi)
        self.assertTrue(np.array_equal(primary, [0, 0, 0, 0, 1, 1, 1]))
        self.assertTrue(np.array_equal(sensitivity, [0, 0, 0, 0, 0, 1, 1]))
        self.assertTrue(np.array_equal(fringe, [0, 0, 1, 0, 0, 0, 0]))
        self.assertTrue(np.array_equal(background, [0, 1, 0, 0, 0, 0, 0]))
    def test_local_equal_area_projection_round_trip(self):
        crs = local_crs(58, -155)
        forward = Transformer.from_crs(4326, crs, always_xy=True)
        reverse = Transformer.from_crs(crs, 4326, always_xy=True)
        x, y = forward.transform(-154.5, 58.5)
        lon, lat = reverse.transform(x, y)
        self.assertAlmostEqual(lon, -154.5, places=8)
        self.assertAlmostEqual(lat, 58.5, places=8)
    def test_summary_separates_all_and_contained(self):
        objects = pd.DataFrame([
            dict(region="01", region_name="Alaska", stratum="glacier", resolution_m=0,
                 slope_deg="", contact_m="", pzi_min="", edge_truncated="no", area_m2=10,
                 eligible_d10="no", eligible_d30="no", eligible_d100="yes"),
            dict(region="01", region_name="Alaska", stratum="glacier", resolution_m=0,
                 slope_deg="", contact_m="", pzi_min="", edge_truncated="yes", area_m2=20,
                 eligible_d10="no", eligible_d30="no", eligible_d100="yes"),
        ])
        result = summarize(objects).set_index("edge_scope")
        self.assertEqual(result.loc["all", "object_count"], 2)
        self.assertEqual(result.loc["contained", "area_m2"], 10)
    def test_analysis_code_has_no_case_or_climate_input(self):
        text = Path("scripts/denominator_pilot.py").read_text()
        for forbidden in ("candidates.csv", "event_audit", "data/reanalysis"):
            self.assertNotIn(forbidden, text)
    def test_artifacts_are_unique_and_match_source_manifest(self):
        manifest = json.loads(Path("data/denominator/source_manifest.json").read_text())
        self.assertEqual(set(manifest["access_terms"]),
                         {"Copernicus DEM", "Gruber PZI", "ITS_LIVE", "RGI"})
        self.assertTrue(all(item["terms"] for item in manifest["access_terms"].values()))
        remote = manifest["remote_objects"]
        self.assertEqual(len({item["id"] for item in remote}), len(remote))
        self.assertEqual({(item["product"], str(item["version"])) for item in remote},
                         {("RGI", "7.0"), ("Copernicus DEM", "GLO-30 2021"),
                          ("Gruber PZI", "2012"), ("Gruber PZI", "2017 rights record"), ("ITS_LIVE", "2")})
        listed = {item["path"] for item in manifest["local_objects"]}
        actual = {str(path) for path in Path("data/denominator/source").iterdir() if path.is_file()}
        self.assertEqual(listed, actual)
        for item in manifest["local_objects"]:
            self.assertEqual(hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest(), item["sha256"])
        objects = pd.read_csv("data/denominator/objects.csv", dtype={"region": str}, low_memory=False)
        self.assertTrue((objects.loc[objects.stratum == "glacier", "itslive_status"] == "covered").all())
        keys = ["region", "stratum", "resolution_m", "slope_deg", "contact_m", "pzi_min", "object_id"]
        self.assertFalse(objects.duplicated(keys).any())
        windows = pd.read_csv("data/denominator/windows.csv", dtype={"region": str})
        self.assertEqual(dict(zip(windows.region, windows.selector_sha256)),
                         {region: values[3] for region, values in WINDOWS.items()})
        self.assertTrue((windows.filter(regex="valid_fraction").to_numpy() == 1).all())
        eligible = pd.read_csv("data/denominator/eligible_windows.csv", dtype={"region": str})
        self.assertEqual(eligible.groupby("region").digest.min().to_dict(),
                         {region: values[3] for region, values in WINDOWS.items()})
        for region, row in windows.set_index("region").iterrows():
            with rasterio.open(f"data/denominator/source/dem_{region}_30m.tif") as dataset:
                self.assertEqual(CRS.from_wkt(dataset.crs.to_wkt()), CRS.from_wkt(row.laea_wkt))
                self.assertEqual((dataset.height, dataset.width),
                                 (row.grid_height_30m, row.grid_width_30m))
                self.assertEqual((dataset.transform.c % 30, dataset.transform.f % 30), (0, 0))
        review = pd.read_csv("data/denominator/validation_review.csv", dtype={"region": str})
        self.assertEqual(len(review), 45)
        self.assertTrue((review.status == "agree").all() and
                        review.filter(regex="_ok$").to_numpy().all())
        notebook = Path("notebooks/denominator_pilot.ipynb").read_text()
        for forbidden in ("candidates.csv", "event_audit", "data/reanalysis"):
            self.assertNotIn(forbidden, notebook)
        freeze = json.loads(Path("data/denominator/freeze_manifest.json").read_text())
        for file_name, item in freeze["files"].items():
            content = Path(file_name).read_bytes()
            downstream = file_name.startswith("latex/") or file_name == "tests/test_denominator_pilot.py"
            if downstream and hashlib.sha256(content).hexdigest() != item["sha256"]:
                content = subprocess.check_output(
                    ["git", "show", f"{freeze['implementation_commit']}:{file_name}"])
            self.assertEqual(hashlib.sha256(content).hexdigest(), item["sha256"])
if __name__ == "__main__":
    unittest.main()

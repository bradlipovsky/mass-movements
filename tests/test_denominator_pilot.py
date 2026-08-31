import math
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from affine import Affine
from pyproj import Transformer
from shapely import box

from scripts.denominator_pilot import (
    aggregate_3x3,
    burn,
    component_rows,
    contact_distance,
    local_crs,
    select_window,
    slope_degrees,
    summarize,
    volume_fields,
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
        yy, xx = np.indices((7, 8))
        z = 3 * xx - 4 * yy + 10.0
        slope = slope_degrees(z, 1)
        self.assertTrue(np.allclose(slope[1:-1, 1:-1], np.degrees(np.arctan(5))))
        self.assertTrue(np.isnan(slope[[0, -1]]).all())
        z[3, 3] = np.nan
        slope = slope_degrees(z, 1)
        self.assertTrue(np.isnan(slope[3, 2:5]).all())
        self.assertTrue(np.isnan(slope[2:5, 3]).all())

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


if __name__ == "__main__":
    unittest.main()

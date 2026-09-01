import json, unittest
from pathlib import Path
import pandas as pd
from pyproj import Transformer
from shapely import box
from scripts.glacier_proximity_object_relevance import (DEPENDENCY_GUARD_M, EXPECTED, FRAME, ISSUE23_SHA,
    PROXIMITY_GUARD_M, ROOT, dependency_region, digest, local_crs, tile_footprint)

class RelevanceTests(unittest.TestCase):
    def test_frozen_dimensions_and_issue23_identity(self):
        frame=pd.read_csv(FRAME); expected=pd.read_csv(EXPECTED)
        self.assertEqual((len(frame),len(expected),expected.instance.value_counts().to_dict()),(1826,32868,{"glo30":16434,"glo90":16434}))
        self.assertEqual(digest(ROOT/"data/global_dem_support/final_manifest.json"),ISSUE23_SHA)
    def test_continuous_ring_excludes_glacier_interior(self):
        report, glacier=box(0,0,1000,1000),box(400,400,600,600)
        proximity, dependency=dependency_region(report,glacier)
        self.assertFalse(proximity.contains(glacier.centroid)); self.assertTrue(proximity.contains(box(600,450,650,550).centroid))
        self.assertTrue(dependency.contains(box(0,0,1000,1000).centroid))
    def test_guards_dominate_registered_distances(self):
        self.assertGreater(PROXIMITY_GUARD_M,100); self.assertGreater(DEPENDENCY_GUARD_M,1000)
    def test_empty_proximity_is_explicit(self):
        proximity, dependency=dependency_region(box(0,0,1,1),box(-1,-1,2,2))
        self.assertTrue(proximity.is_empty and dependency.is_empty)
    def test_tile_boundary_contact_is_relevant(self):
        _, dependency=dependency_region(box(0,0,10,10),box(4,4,6,6))
        self.assertTrue(box(0,0,1,1).intersects(dependency))
    def test_antimeridian_tiles_project_near_each_other(self):
        crs=local_crs(70,179); a=tile_footprint(70,179,crs,179.5); b=tile_footprint(70,-180,crs,179.5)
        self.assertLess(a.distance(b),1e-4); self.assertGreater(a.area,0); self.assertGreater(b.area,0)
    def test_geometry_is_product_independent(self):
        expected=pd.read_csv(EXPECTED); keys=["cell_key","role","latitude","longitude"]
        a=expected[expected.instance.eq("glo30")][keys].reset_index(drop=True); b=expected[expected.instance.eq("glo90")][keys].reset_index(drop=True)
        pd.testing.assert_frame_equal(a,b)
    def test_source_contains_no_forbidden_data_access(self):
        source=(ROOT/"scripts/glacier_proximity_object_relevance.py").read_text()
        for token in ["rasterio","PZI.flt","data/geographic_total/","sample.csv","http://","https://"]: self.assertNotIn(token,source)
    def test_line_budget(self):
        source=(ROOT/"scripts/glacier_proximity_object_relevance.py").read_text().splitlines()
        tests=Path(__file__).read_text().splitlines()
        self.assertLessEqual(len(source)+len(tests),300)

if __name__ == "__main__": unittest.main()

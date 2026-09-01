import unittest
from pathlib import Path
import pandas as pd
from shapely import Point, Polygon, box
from scripts.glacier_proximity_object_relevance import (EXPECTED, FRAME, ISSUE23, ISSUE23_SHA, PRE, PRE_FILES, QUAD_SEGS, ROOT, SCREEN_M,
    cell_table, dependency_region, digest, group_table, join_tables, local_crs, projected_union, report_geometries, tile_footprint, validate_file_set, verify_manifest)
class RelevanceTests(unittest.TestCase):
    def test_frozen_dimensions_and_issue23_identity(self):
        frame, expected = pd.read_csv(FRAME), pd.read_csv(EXPECTED)
        self.assertEqual((len(frame), len(expected)), (1826, 32868))
        self.assertTrue(expected.groupby(["cell_key", "instance"]).size().eq(9).all())
        self.assertEqual(digest(ISSUE23), ISSUE23_SHA)
    def test_canonical_manifest_and_exact_set_are_mandatory(self):
        verify_manifest(PRE, "pre_geometry")
        with self.assertRaises(ValueError):
            verify_manifest(Path("/tmp/fabricated.json"), "pre_geometry")
        with self.assertRaises(ValueError):
            validate_file_set({"files": {}}, "pre_geometry")
        self.assertEqual(len(PRE_FILES), 9)
    def test_polygonal_screen_contains_exact_one_kilometre_circle(self):
        intended = Point(0, 0).buffer(1000, quad_segs=256)
        implemented = Point(0, 0).buffer(SCREEN_M, quad_segs=QUAD_SEGS)
        self.assertTrue(intended.difference(implemented).is_empty)
    def test_continuous_ring_excludes_glacier_interior(self):
        report, glacier = box(0, 0, 1000, 1000), box(400, 400, 600, 600)
        proximity, screen = dependency_region(report, glacier)
        self.assertFalse(proximity.contains(glacier.centroid))
        self.assertTrue(proximity.contains(Point(650, 500)))
        self.assertTrue(screen.contains(report.centroid))
    def test_empty_proximity_is_explicit(self):
        proximity, screen = dependency_region(box(0, 0, 1, 1), box(-1, -1, 2, 2))
        self.assertTrue(proximity.is_empty and screen.is_empty)
    def test_antimeridian_envelope_and_tiles_are_local(self):
        crs, _, _, envelope = report_geometries(70, 179)
        east = tile_footprint(70, 179, crs, 179.5)
        west = tile_footprint(70, -180, crs, 179.5)
        self.assertLess(east.distance(west), 1e-4)
        self.assertLess(envelope.bounds[2] - envelope.bounds[0], 3)
    def test_projection_repair_is_identified_and_bounded(self):
        invalid = Polygon([(0, 0), (3, 0), (1, 2), (2, -1), (0, 2), (0, 0)])
        if invalid.area == 0:
            self.skipTest("synthetic invalid polygon has zero signed area")
        with self.assertRaises(ValueError):
            projected_union([("test-id", invalid)], local_crs(0, 0), 0, "test-cell")
    def test_join_state_and_group_conservation(self):
        expected = pd.read_csv(EXPECTED, dtype={"dominant_region": str})
        spatial = expected.drop_duplicates(["cell_key", "role", "latitude", "longitude"])
        screen = spatial[["cell_key", "south", "west", "dominant_region", "role", "latitude", "longitude"]].copy()
        screen["proximity_applicable"], screen["screen_relevant"] = True, True
        inventory = expected[["instance", "object_id"]].drop_duplicates()
        objects = join_tables(expected, screen, inventory)
        cells = cell_table(objects); groups = group_table(cells)
        self.assertEqual((len(objects), len(cells), len(groups)), (32868, 3652, 68))
        self.assertTrue(cells.cell_state.eq("all_relevant_objects_listed").all())
    def test_absent_states_are_distinct(self):
        expected = pd.read_csv(EXPECTED, dtype={"dominant_region": str})
        spatial = expected.drop_duplicates(["cell_key", "role", "latitude", "longitude"])
        screen = spatial[["cell_key", "south", "west", "dominant_region", "role", "latitude", "longitude"]].copy()
        screen["proximity_applicable"], screen["screen_relevant"] = True, False
        inventory = expected[["instance", "object_id"]].drop_duplicates().iloc[1:]
        objects = join_tables(expected, screen, inventory)
        self.assertIn("absent_outside_conservative_screen", set(objects.state))
        screen.loc[screen.index[0], "screen_relevant"] = True
        self.assertIn("absent_relevance_unresolved", set(join_tables(expected, screen, inventory).state))
    def test_source_has_no_forbidden_access(self):
        source = (ROOT / "scripts/glacier_proximity_object_relevance.py").read_text()
        for token in ["rasterio", "PZI.flt", "data/geographic_total/", "sample.csv", "http://", "https://"]:
            self.assertNotIn(token, source)
    def test_line_budget(self):
        source = (ROOT / "scripts/glacier_proximity_object_relevance.py").read_text().splitlines()
        tests = Path(__file__).read_text().splitlines()
        self.assertLessEqual(len(source) + len(tests), 300)
if __name__ == "__main__": unittest.main()

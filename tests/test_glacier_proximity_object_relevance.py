import json, unittest; from pathlib import Path; import fiona, pandas as pd
from shapely import Point, Polygon, box, dwithin, force_2d, from_geojson, hausdorff_distance
from scripts.glacier_proximity_object_relevance import (EXPECTED, FRAME, ISSUE23, ISSUE23_SHA, PRE, PRE_FILES, QUAD_SEGS, ROOT, SCREEN_M,
    cell_table, dependency_region, digest, group_table, join_tables, local_crs, project_outline, repair_projected, report_geometries, tile_footprint, validate_file_set, verify_manifest)
class RelevanceTests(unittest.TestCase):
    def test_frozen_dimensions_and_issue23_identity(self):
        frame, expected = pd.read_csv(FRAME), pd.read_csv(EXPECTED)
        self.assertEqual((len(frame), len(expected)), (1826, 32868)); self.assertTrue(expected.groupby(["cell_key", "instance"]).size().eq(9).all()); self.assertEqual(digest(ISSUE23), ISSUE23_SHA)
    def test_canonical_manifest_and_exact_set_are_mandatory(self):
        verify_manifest(PRE, "pre_geometry"); self.assertEqual(len(PRE_FILES), 8)
        with self.assertRaises(ValueError): verify_manifest(Path("/tmp/fabricated.json"), "pre_geometry")
        with self.assertRaises(ValueError): validate_file_set({"files": {}}, "pre_geometry")
    def test_polygonal_screen_contains_exact_one_kilometre_circle(self):
        intended = Point(0, 0).buffer(100, quad_segs=256); implemented = Point(0, 0).buffer(101, quad_segs=QUAD_SEGS)
        self.assertTrue(intended.difference(implemented).is_empty); self.assertTrue(dwithin(Point(1001, 0), Point(0, 0), SCREEN_M)); self.assertFalse(dwithin(Point(1001.001, 0), Point(0, 0), SCREEN_M))
    def test_continuous_ring_excludes_glacier_interior(self):
        report, glacier = box(0, 0, 1000, 1000), box(400, 400, 600, 600); proximity = dependency_region(report, glacier)
        self.assertFalse(proximity.contains(glacier.centroid)); self.assertTrue(proximity.contains(Point(650, 500)))
    def test_empty_proximity_is_explicit(self): self.assertTrue(dependency_region(box(0, 0, 1, 1), box(-1, -1, 2, 2)).is_empty)
    def test_antimeridian_envelope_and_tiles_are_local(self):
        crs, _, _, envelope = report_geometries(70, 179); east = tile_footprint(70, 179, crs, 179.5); west = tile_footprint(70, -180, crs, 179.5)
        self.assertLess(east.distance(west), 1e-4); self.assertLess(envelope.bounds[2] - envelope.bounds[0], 3)
    def test_projection_repair_is_identified_and_bounded(self):
        invalid = Polygon([(0,0),(3,0),(3,3),(1.5,3),(1.5,1),(1.500000001,1),(0,3),(0,0)]); fixed, record = repair_projected(invalid, "test-id", "test-cell", local_crs(0,0)); self.assertTrue(fixed.is_valid); self.assertEqual((record["rgi_id"], record["cell_key"]), ("test-id", "test-cell")); self.assertLessEqual(record["relative_area_change"], 1e-7)
    def test_all_failed_projection_classes_regression(self):
        cases = [("03_arctic_canada_north", {"03101": [(78,-90)], "03110": [(78,-90)], "03766": [(80,x) for x in range(-74,-70)] + [(81,-72)]}), ("05_greenland_periphery", {"17411": [(80,-16)], "17462": [(80,-22),(80,-21)]})]
        for region, identities in cases:
            archive = ROOT / f"data/geographic_sample/source_raw/rgi/RGI2000-v7.0-G-{region}.zip"
            with fiona.open(f"zip://{archive}!RGI2000-v7.0-G-{region}.shp") as source: features = {x["properties"]["rgi_id"].split("-")[-1]: x for x in source if x["properties"]["rgi_id"].split("-")[-1] in identities}
            for identity, cells in identities.items():
                geographic = force_2d(from_geojson(json.dumps(dict(features[identity]["geometry"]))))
                for south, west in cells:
                    dense, projected = project_outline(geographic, local_crs(south, west), west); refined, check = project_outline(geographic, local_crs(south, west), west, .0005)
                    if identity == "03766": self.assertTrue(projected.is_valid and check.is_valid); self.assertLess(hausdorff_distance(projected.boundary, check.boundary), .1); continue
                    fixed, record = repair_projected(projected, identity, "cell", local_crs(south, west), geographic, dense); check = check if check.is_valid else repair_projected(check, identity, "cell", local_crs(south, west), geographic, refined)[0]
                    self.assertTrue(fixed.is_valid); self.assertLess(record["absolute_area_change_m2"], .1); self.assertLess(record["boundary_hausdorff_distance_m"], .02); self.assertLess(hausdorff_distance(fixed.boundary, check.boundary), .1)
                    if identity == "03101": self.assertEqual((record["source_holes"], record["segmentized_wgs_holes"], record["fixed_output_components"]), (1,0,3))
    def test_join_state_and_group_conservation(self):
        expected = pd.read_csv(EXPECTED, dtype={"dominant_region": str}); spatial = expected.drop_duplicates(["cell_key", "role", "latitude", "longitude"])
        screen = spatial[["cell_key", "south", "west", "dominant_region", "role", "latitude", "longitude"]].copy()
        screen["proximity_applicable"], screen["screen_relevant"] = True, True
        inventory = expected[["instance", "object_id"]].drop_duplicates(); objects = join_tables(expected, screen, inventory); cells = cell_table(objects); groups = group_table(cells)
        self.assertEqual((len(objects), len(cells), len(groups)), (32868, 3652, 68)); self.assertTrue(cells.cell_state.eq("no_absent_object_intersects_conservative_screen").all())
    def test_absent_states_are_distinct(self):
        expected = pd.read_csv(EXPECTED, dtype={"dominant_region": str}); spatial = expected.drop_duplicates(["cell_key", "role", "latitude", "longitude"])
        screen = spatial[["cell_key", "south", "west", "dominant_region", "role", "latitude", "longitude"]].copy()
        screen["proximity_applicable"], screen["screen_relevant"] = True, False
        inventory = expected[["instance", "object_id"]].drop_duplicates().iloc[1:]; objects = join_tables(expected, screen, inventory)
        self.assertIn("absent_outside_conservative_screen", set(objects.state))
        screen.loc[screen.index[0], "screen_relevant"] = True
        self.assertIn("absent_relevance_unresolved", set(join_tables(expected, screen, inventory).state))
    def test_source_has_no_forbidden_access(self): source = (ROOT / "scripts/glacier_proximity_object_relevance.py").read_text(); [self.assertNotIn(token, source) for token in ["rasterio", "PZI.flt", "data/geographic_total/", "sample.csv", "http://", "https://"]]
    def test_line_budget(self):
        source = (ROOT / "scripts/glacier_proximity_object_relevance.py").read_text().splitlines(); tests = Path(__file__).read_text().splitlines()
        self.assertLessEqual(len(source) + len(tests), 300)

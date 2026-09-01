import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shapely import GeometryCollection, LineString, Polygon, box, union_all

from scripts.geographic_sample import (allocate, build, cell_key, clips_by_cell, polygon_area_m2,
                                       polygonal_only, repair_geometry, unwrap)


class TestGeographicSample(unittest.TestCase):
    def test_cell_key_is_literal_and_padded(self):
        self.assertEqual(cell_key(-6, 7), "rgi7.0|global|south=-006|west=+0007")
        self.assertEqual(cell_key(89, -180), "rgi7.0|global|south=+089|west=-0180")

    def test_boundary_touch_has_no_positive_clip(self):
        touching = box(0, 0, 1, 1)
        keys = {(south, west) for south, west, _, _ in clips_by_cell(touching)}
        self.assertEqual(keys, {(0, 0)})

    def test_zero_area_contact_is_removed_from_collection(self):
        mixed = GeometryCollection([box(0, 0, 1, 1), LineString([(1, 0), (2, 0)])])
        polygonal = polygonal_only(mixed)
        self.assertEqual(polygonal.geom_type, "Polygon")
        self.assertEqual(polygonal.area, 1)

    def test_antimeridian_ownership(self):
        crossing = Polygon([(179.8, 10.2), (-179.8, 10.2), (-179.8, 10.8), (179.8, 10.8)])
        clips = list(clips_by_cell(crossing))
        self.assertEqual({(south, west) for south, west, _, _ in clips}, {(10, 179), (10, -180)})
        self.assertTrue(all(changed for _, _, _, changed in clips))
        self.assertTrue(all(polygon_area_m2(geometry) > 0 for _, _, geometry, _ in clips))

    def test_unwrap_is_reversible_about_reporting_cells(self):
        crossing = Polygon([(179.8, 0), (-179.8, 0), (-179.8, 1), (179.8, 1)])
        eastern = unwrap(crossing, 179.5)
        western = unwrap(eastern, -179.5)
        self.assertLess(eastern.bounds[2] - eastern.bounds[0], 1)
        self.assertLess(western.bounds[2] - western.bounds[0], 1)

    def test_unwrap_preserves_coordinates_when_branch_is_unchanged(self):
        ordinary = box(43.228407, 43.009076, 43.244284, 43.02878)
        self.assertIs(unwrap(ordinary, 43.5), ordinary)

    def test_union_area_not_sum_of_overlaps(self):
        first, second = box(0, 0, 0.75, 1), box(0.25, 0, 1, 1)
        union_area = polygon_area_m2(union_all([first, second]))
        self.assertLess(union_area, polygon_area_m2(first) + polygon_area_m2(second))
        self.assertGreater(union_area, polygon_area_m2(first))

    def test_geodesic_cells_have_unequal_area(self):
        equator = polygon_area_m2(box(0, 0, 1, 1))
        high_latitude = polygon_area_m2(box(0, 80, 1, 81))
        self.assertGreater(equator, 5 * high_latitude)

    def test_valid_geometry_is_not_repaired_and_large_change_stops(self):
        valid = box(0, 0, 1, 1)
        unchanged, record = repair_geometry(valid, "valid", "01")
        self.assertIs(unchanged, valid)
        self.assertIsNone(record)
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
        with self.assertRaisesRegex(ValueError, "repair area changed"):
            repair_geometry(bowtie, "invalid", "01")

    def test_duplicate_id_stops_builder(self):
        archives = [Path(f"RGI2000-v7.0-G-{i:02d}_test.zip") for i in range(1, 20)]
        archive_dir = MagicMock()
        archive_dir.glob.return_value = archives
        manifest = {"archives": [{"members": [{"name": f"region_{i:02d}.shp"}]}
                                  for i in range(1, 20)]}

        class Collection:
            crs = MagicMock(to_epsg=lambda: 4326)

            def __init__(self, region):
                self.features = [] if int(region) > 2 else [{"properties": {"rgi_id": "duplicate",
                    "o1region": region}, "geometry": {"type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}]

            def __enter__(self): return self
            def __exit__(self, *_): return None
            def __iter__(self): return iter(self.features)

        open_collection = lambda uri: Collection(uri.split("-G-")[1][:2])
        with tempfile.TemporaryDirectory() as temporary, \
             patch("scripts.geographic_sample.source_manifest", return_value=manifest), \
             patch("scripts.geographic_sample.fiona.open", side_effect=open_collection):
            with self.assertRaisesRegex(ValueError, "duplicate RGI ID"):
                build(archive_dir, Path(temporary))

    def test_fixed_allocation_and_census_limit(self):
        sizes = {"01": 100, "02": 25, "03": 3, "20": 0}
        draw = allocate(sizes, total=20)
        self.assertEqual(sum(draw.values()), 20)
        self.assertEqual(draw["03"], 3)
        self.assertEqual(draw["20"], 0)
        self.assertGreaterEqual(draw["01"], 4)
        self.assertGreaterEqual(draw["02"], 4)
        self.assertEqual(allocate({"01": 2, "02": 3}, total=96), {"01": 2, "02": 3})

    def test_allocation_tie_breaks_by_region_code(self):
        self.assertEqual(allocate({"01": 10, "02": 10}, total=9), {"01": 5, "02": 4})

    def test_frozen_outputs_reconstruct_when_present(self):
        root = Path("data/geographic_sample")
        manifest = root / "pre_randomization_manifest.json"
        if not manifest.exists():
            self.skipTest("frame has not been generated")
        import json
        frozen = json.loads(manifest.read_text())
        for name, identity in frozen["artifacts"].items():
            raw = (root / name).read_bytes()
            self.assertEqual(len(raw), identity["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), identity["sha256"])
        for name, identity in frozen["implementation"].items():
            raw = Path(name).read_bytes()
            self.assertEqual(len(raw), identity["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), identity["sha256"])
        with open(root / "frame.csv", newline="") as source:
            frame = list(csv.DictReader(source))
        with open(root / "region_contributions.csv", newline="") as source:
            contributions = list(csv.DictReader(source))
        with open(root / "region_allocations.csv", newline="") as source:
            allocations = list(csv.DictReader(source))
        self.assertEqual(len(frame), frozen["population_cells"])
        self.assertEqual(sum(int(row["sample_cells"]) for row in allocations), frozen["sample_cells"])
        self.assertEqual(sum(int(row["population_cells"]) for row in allocations), len(frame))
        self.assertTrue(all(float(row["inclusion_probability"]) > 0 for row in frame))
        self.assertEqual(len({row["cell_key"] for row in frame}), len(frame))
        by_cell = {}
        for row in contributions:
            by_cell.setdefault(row["cell_key"], []).append(row)
        cross_region = [row for row in frame if len(by_cell[row["cell_key"]]) > 1]
        self.assertTrue(cross_region)
        for row in cross_region:
            expected = min(by_cell[row["cell_key"]],
                           key=lambda item: (-float(item["region_union_intersection_area_km2"]), item["region"]))
            self.assertEqual(row["dominant_region"], expected["region"])


if __name__ == "__main__":
    unittest.main()

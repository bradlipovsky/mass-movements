import hashlib, importlib.util, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock

from shapely import MultiPolygon, Polygon, box

SPEC = importlib.util.spec_from_file_location(
    "glacier_spatial_freeze", Path(__file__).parents[1] / "scripts/glacier_spatial_freeze.py")
spatial = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(spatial)

class GlacierSpatialFreezeTests(unittest.TestCase):
    def test_cell_centers_include_touching_candidates(self):
        self.assertEqual(spatial.centers_between(.125, .375, -180, 180), [0.0, .25, .5])
        self.assertEqual(spatial.centers_between(89.9, 90, -90, 90), [90.0])

    def test_geodesic_cells_partition_polygon_and_normalize(self):
        geometry = box(-.2, -.1, .3, .4)
        rows, check = spatial.geometry_weights("RGI2000-v7.0-G-13-00001", geometry)
        self.assertEqual({float(row["longitude"]) for row in rows}, {0, .25, 359.75})
        self.assertAlmostEqual(sum(float(row["weight"]) for row in rows), 1, places=14)
        tiled = sum(float(row["intersection_area_m2"]) for row in rows)
        self.assertLess(abs(tiled / spatial.geodesic_area(geometry) - 1), 1e-5)
        self.assertLess(float(check["planar_relative_closure_error"]), 1e-12)
        self.assertAlmostEqual(float(check["weight_sum"]), 1)

    def test_boundary_touch_has_zero_area(self):
        rows, _ = spatial.geometry_weights("RGI2000-v7.0-G-13-00001", box(.125, 0, .2, .1))
        self.assertEqual({float(row["longitude"]) for row in rows}, {.25})

    def test_holes_multipart_and_polar_cells_normalize(self):
        hole = Polygon([(-.2, -.2), (.2, -.2), (.2, .2), (-.2, .2)],
                       [[(-.05, -.05), (-.05, .05), (.05, .05), (.05, -.05)]])
        multipart = MultiPolygon([hole, box(.3, 89.9, .4, 90)])
        rows, check = spatial.geometry_weights("RGI2000-v7.0-G-13-00001", multipart)
        self.assertAlmostEqual(sum(float(row["weight"]) for row in rows), 1, places=12)
        self.assertTrue(any(float(row["latitude"]) == 90 for row in rows))

    def test_antimeridian_multipart_uses_continuous_branch(self):
        geometry = MultiPolygon([box(179.8, 0, 180, .1), box(-180, 0, -179.8, .1)])
        unwrapped = spatial.unwrap_geometry(geometry)
        self.assertLess(unwrapped.bounds[2] - unwrapped.bounds[0], 1)
        self.assertTrue(unwrapped.is_valid)
        rows, _ = spatial.geometry_weights("RGI2000-v7.0-G-01-00001", unwrapped)
        self.assertEqual({float(row["longitude"]) for row in rows}, {179.75, 180, 180.25})

    def test_incomplete_cell_partition_is_rejected(self):
        with mock.patch.object(spatial, "centers_between", return_value=[0]):
            with self.assertRaisesRegex(ValueError, "do not partition"):
                spatial.geometry_weights("RGI2000-v7.0-G-13-00001", box(-.2, -.2, .3, .3))

    def test_nonfinite_intersection_is_rejected(self):
        with mock.patch.object(spatial, "geodesic_area", return_value=float("nan")):
            with self.assertRaisesRegex(ValueError, "nonfinite"):
                spatial.geometry_weights("RGI2000-v7.0-G-13-00001", box(0, 0, .1, .1))

    def test_shared_cells_merge_transitively(self):
        cases = {"a": "ra", "b": "rb", "c": "rc"}
        controls = {"a": [], "b": [], "c": []}; clusters = {"a": "a", "b": "b", "c": "c"}
        weights = [dict(rgi_id="ra", latitude="0", longitude="0"),
                   dict(rgi_id="rb", latitude="0", longitude="0"),
                   dict(rgi_id="rb", latitude="1", longitude="1"),
                   dict(rgi_id="rc", latitude="1", longitude="1")]
        ledger, edges = spatial.dependence_tables(cases, controls, clusters, weights)
        self.assertEqual({row["final_cluster"] for row in ledger}, {"a"})
        self.assertEqual({(row["left_initial_cluster"], row["right_initial_cluster"])
                          for row in edges}, {("a", "b"), ("b", "c")})

    def test_archive_inventory_reads_central_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "RGI70G_rgi13.zip"
            with zipfile.ZipFile(path, "w") as archive: archive.writestr("one.tif", b"opaque")
            md5 = hashlib.md5(path.read_bytes()).hexdigest()
            record = {"region": 13, "filename": path.name, "bytes": path.stat().st_size, "md5": md5}
            old = spatial.ICEBOOST_RAW
            try:
                spatial.ICEBOOST_RAW = root
                rows, paths = spatial.archive_inventory({"archives": [record]})
            finally: spatial.ICEBOOST_RAW = old
            self.assertEqual((len(rows), rows[0]["member"], paths), (1, "one.tif", [path]))
            self.assertEqual(rows[0]["member_bytes"], 6)

    def test_archive_inventory_rejects_unsafe_member(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "RGI70G_rgi13.zip"
            with zipfile.ZipFile(path, "w") as archive: archive.writestr("../one.tif", b"opaque")
            record = {"region": 13, "filename": path.name, "bytes": path.stat().st_size,
                      "md5": hashlib.md5(path.read_bytes()).hexdigest()}
            old = spatial.ICEBOOST_RAW; spatial.ICEBOOST_RAW = root
            try:
                with self.assertRaisesRegex(ValueError, "unsafe"): spatial.archive_inventory({"archives": [record]})
            finally: spatial.ICEBOOST_RAW = old

    def test_bad_archive_size_fails_before_zip_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "RGI70G_rgi13.zip"; path.write_bytes(b"not a zip")
            record = {"region": 13, "filename": path.name, "bytes": path.stat().st_size + 1,
                      "md5": hashlib.md5(path.read_bytes()).hexdigest()}
            old = spatial.ICEBOOST_RAW; spatial.ICEBOOST_RAW = root
            try:
                with mock.patch.object(spatial.zipfile, "ZipFile") as parser:
                    with self.assertRaisesRegex(ValueError, "archive drift"):
                        spatial.archive_inventory({"archives": [record]})
                    parser.assert_not_called()
            finally: spatial.ICEBOOST_RAW = old

    def test_freeze_refuses_existing_target_before_access(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "spatial_freeze_manifest.json").write_text("{}")
            with self.assertRaises(FileExistsError): spatial.freeze(directory)

if __name__ == "__main__": unittest.main()

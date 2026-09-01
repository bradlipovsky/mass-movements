import hashlib, io, json, tempfile, unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch
import pandas as pd
from scripts.global_dem_support import (HASHES, INSTANCES, KEY, expected_rows, fetch_inventory,
                                        inventory_url, normalize_longitude, parse_listing, stem, support_tables,
                                        verify_inputs, verify_manifest)
class Response:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return self.body
def listing(keys, truncated=False, token=None):
    contents = "".join(f"<Contents><Key>{key}</Key><LastModified>2021-01-01T00:00:00Z</LastModified><ETag>&quot;abc&quot;</ETag><Size>12</Size></Contents>" for key in keys)
    next_token = f"<NextContinuationToken>{token}</NextContinuationToken>" if token else ""
    return f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>{str(truncated).lower()}</IsTruncated>{contents}{next_token}</ListBucketResult>'.encode()
class GlobalDemSupportTests(unittest.TestCase):
    def test_frozen_inputs_and_expected_population(self):
        verify_inputs()
        for name, expected in HASHES.items():
            self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(), expected)
        rows = pd.DataFrame(expected_rows())
        self.assertEqual((len(rows), set(rows.instance)), (1826 * 2 * 9, set(INSTANCES)))
        sizes = rows.groupby(["cell_key", "instance"]).agg(n=("object_id", "nunique"),
                                                            core=("role", lambda x: (x == "core").sum()))
        self.assertTrue(((sizes.n == 9) & (sizes.core == 1)).all())
    def test_identity_format_and_antimeridian(self):
        self.assertEqual(normalize_longitude(180), -180)
        self.assertEqual(stem("glo30", -6, 7), "Copernicus_DSM_COG_10_S06_00_E007_00_DEM")
        self.assertEqual(stem("glo90", 8, 180), "Copernicus_DSM_COG_30_N08_00_W180_00_DEM")
        key = "Copernicus_DSM_COG_30_N08_00_W180_00_DEM/Copernicus_DSM_COG_30_N08_00_W180_00_DEM.tif"
        self.assertTrue(KEY.fullmatch(key))
    def test_listing_parser_is_exact_and_instance_specific(self):
        body = b'''<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>false</IsTruncated><Contents><Key>Copernicus_DSM_COG_30_N08_00_W180_00_DEM/Copernicus_DSM_COG_30_N08_00_W180_00_DEM.tif</Key><LastModified>2021-01-01T00:00:00Z</LastModified><ETag>"abc"</ETag><Size>12</Size></Contents><Contents><Key>Copernicus_DSM_COG_30_N08_00_W180_00_DEM/AUX.tif</Key><LastModified>2021-01-01T00:00:00Z</LastModified><ETag>"def"</ETag><Size>3</Size></Contents></ListBucketResult>'''
        rows, truncated, token = parse_listing(body, "glo90")
        self.assertEqual((len(rows), rows[0]["bytes"], rows[0]["etag"], truncated, token), (1, 12, "abc", False, None))
        self.assertEqual(parse_listing(body, "glo30")[0], [])
        for malformed in (b"<foo/>", b"<ListBucketResult/>"):
            with self.assertRaises(ValueError): parse_listing(malformed, "glo90")
    def test_pagination_retains_pages_and_rejects_duplicates(self):
        one = "Copernicus_DSM_COG_30_N08_00_W180_00_DEM/Copernicus_DSM_COG_30_N08_00_W180_00_DEM.tif"
        two = "Copernicus_DSM_COG_30_N09_00_W180_00_DEM/Copernicus_DSM_COG_30_N09_00_W180_00_DEM.tif"
        with tempfile.TemporaryDirectory() as temporary, patch("scripts.global_dem_support.OUTPUT", Path(temporary)):
            with patch("scripts.global_dem_support.urlopen", side_effect=[Response(listing([one], True, "next")), Response(listing([two]))]):
                rows, pages = fetch_inventory("glo90")
            self.assertEqual((len(rows), len(pages), pages[-1]["parse_status"]), (2, 2, "ok"))
            self.assertTrue((Path(temporary) / "source_raw/glo90/page_0002.xml").exists())
            self.assertEqual(len(json.loads((Path(temporary) / "source_raw/glo90/pages.json").read_text())), 2)
            with patch("scripts.global_dem_support.urlopen", side_effect=[Response(listing([one], True, "again")), Response(listing([one]))]):
                with self.assertRaisesRegex(ValueError, "duplicate"): fetch_inventory("glo90")
            with patch("scripts.global_dem_support.urlopen", return_value=Response(listing([one, one]))):
                with self.assertRaisesRegex(ValueError, "duplicate"): fetch_inventory("glo90")
    def test_malformed_page_and_repeated_token_are_durable_stops(self):
        with tempfile.TemporaryDirectory() as temporary, patch("scripts.global_dem_support.OUTPUT", Path(temporary)):
            with patch("scripts.global_dem_support.urlopen", return_value=Response(b"<foo/>")):
                with self.assertRaises(ValueError): fetch_inventory("glo30")
            raw = Path(temporary) / "source_raw/glo30"
            self.assertEqual(json.loads((raw / "pages.json").read_text())[0]["parse_status"], "error")
            self.assertEqual((raw / "page_0001.xml").read_bytes(), b"<foo/>")
            with patch("scripts.global_dem_support.urlopen", return_value=Response(listing([], True))):
                with self.assertRaisesRegex(ValueError, "continuation"): fetch_inventory("glo30")
            with patch("scripts.global_dem_support.urlopen", side_effect=[Response(listing([], True, "same")), Response(listing([], True, "same"))]):
                with self.assertRaisesRegex(ValueError, "continuation"): fetch_inventory("glo30")
            failure = HTTPError("https://example.invalid", 404, "missing", {}, io.BytesIO(b"denied"))
            with patch("scripts.global_dem_support.urlopen", side_effect=failure):
                with self.assertRaisesRegex(ValueError, "404"): fetch_inventory("glo30")
            self.assertEqual((raw / "page_0001.xml").read_bytes(), b"denied")
            self.assertEqual(json.loads((raw / "pages.json").read_text())[0]["parse_status"], "http_error")

    def test_listing_url_cannot_address_an_object(self):
        for instance in INSTANCES:
            url = inventory_url(instance, "opaque token")
            self.assertIn("list-type=2", url); self.assertIn("max-keys=1000", url)
            self.assertNotIn(".tif", url); self.assertNotIn("range", url.lower())

    def test_manifest_path_and_structure_are_mandatory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"; path.write_text('{"status":"pre_inventory_access","files":{}}')
            with patch("scripts.global_dem_support.MANIFEST", path):
                with self.assertRaisesRegex(ValueError, "invalid pre-access"): verify_manifest(path)

    def test_support_counts_and_selected_annotation_do_not_filter(self):
        expected = pd.DataFrame([
            {"cell_key": "a", "south": 0, "west": 0, "dominant_region": "01", "instance": "glo90", "role": role,
             "object_id": object_id, "key": object_id + "/" + object_id + ".tif", "latitude": 0, "longitude": 0}
            for role, object_id in (("core", "core"), ("halo", "halo"))])
        inventory = pd.DataFrame([{"instance": "glo90", "object_id": "core"}])
        with patch("scripts.global_dem_support.pd.read_csv", return_value=pd.DataFrame({"cell_key": ["not-a"]})):
            cells, groups = support_tables(expected, inventory)
        self.assertEqual((len(cells), cells.iloc[0].required_object_count, cells.iloc[0].present_object_count,
                          cells.iloc[0].core_object_present, cells.iloc[0].full_halo_object_support),
                         (1, 2, 1, True, False))
        self.assertEqual(groups.population_cells.sum(), 2)
        empty, _ = support_tables(expected, pd.DataFrame())
        self.assertEqual((empty.present_object_count.sum(), empty.core_object_present.any()), (0, False))

    def test_source_has_no_raster_payload_reader(self):
        source = Path("scripts/global_dem_support.py").read_text()
        for forbidden in ("rasterio", "xarray", "gdal", "numpy", "requests.get"):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__": unittest.main()

import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import numpy as np
from affine import Affine
from scripts import native_glo90_transfer as analysis
from scripts import native_glo90_transfer_source as source
class NativeGLO90TransferTests(unittest.TestCase):
    def test_frozen_windows_and_request_population(self):
        windows = source.rows(source.WINDOWS); expected = source.expected_records()
        self.assertEqual([x["region"] for x in windows], ["03", "07", "08", "04", "10", "15", "18"])
        self.assertEqual((len(expected), len({x["object_id"] for x in expected})), (63, 63))
        self.assertEqual((expected[0]["object_id"], expected[-1]["object_id"]), ("Copernicus_DSM_COG_30_N80_00_W086_00_DEM", "Copernicus_DSM_COG_30_S43_00_E172_00_DEM"))
    def test_key_format_and_longitude_normalization(self):
        self.assertEqual(source.normalize_longitude(180), -180); self.assertEqual(source.object_id(-4, 180), "Copernicus_DSM_COG_30_S04_00_W180_00_DEM")
        self.assertTrue(all(x["key"] == f'{x["object_id"]}/{x["object_id"]}.tif' for x in source.expected_records()))
    def test_preaccess_manifest_binds_contract_and_implementation(self):
        source.verify_preaccess(source.PRE, source.digest(source.PRE)); manifest = json.loads(source.PRE.read_text())
        with self.assertRaises(ValueError): source.verify_preaccess(source.PRE, "0" * 64)
        for name in ("scripts/denominator_pilot.py", "scripts/scale_explicit_steep_area.py", "scripts/scale_explicit_transfer.py", "scripts/susceptible_area_convergence.py"): self.assertIn(name, manifest["files"])
        self.assertEqual(manifest["environment"], source.environment()); self.assertEqual(manifest["schemas"], json.loads(source.SCHEMAS.read_text()))
    def test_native_phase_affines_are_half_pixel_translations(self):
        base = Affine(90, 0, 30, 0, -90, 900); self.assertEqual(analysis.phase_affine(base, "n00"), base)
        self.assertEqual((analysis.phase_affine(base, "nx45").c, analysis.phase_affine(base, "ny45").f), (75, 945)); self.assertEqual((analysis.phase_affine(base, "nxy45").c, analysis.phase_affine(base, "nxy45").f), (75, 945))
    def test_departure_and_schema_rules(self):
        self.assertEqual((analysis.departure(100, 80), analysis.departure(0, 0)), (0.2, 0.0)); self.assertTrue(pd.isna(analysis.departure(0, 1)))
        schemas = json.loads(source.SCHEMAS.read_text()); self.assertEqual((schemas["equivalent_area_long"]["rows"], schemas["comparisons"]["rows"]), (56, 14))
        self.assertIn({"name": "support_status", "dtype": "string"}, schemas["equivalent_area_long"]["columns"])
        report = np.array([[True, True]]); inside = np.array([[False, False]]); target = support = np.array([[True, False]])
        self.assertFalse(analysis.support_is_complete("permafrost", report, inside, np.array([[0.2, np.nan]]), target, support)); self.assertTrue(analysis.support_is_complete("glacier_proximity", report, inside, np.array([[np.nan, np.nan]]), target, support))
    def test_raw_manifest_verification_closes_every_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / "data/native_glo90_transfer"; rawdir = out / "source_raw"; rawdir.mkdir(parents=True)
            expected = out / "expected_sources.csv"; expected.write_text(source.EXPECTED.read_text()); records = source.rows(expected)
            for item in records:
                body = item["object_id"].encode(); path = rawdir / f'{item["object_id"]}.tif'; path.write_bytes(body)
                item.update(retrieved_utc="x", http_status=200, path=f'source_raw/{path.name}', bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), etag="", last_modified="", content_type="image/tiff", content_length=str(len(body)))
            ledger = out / "source_ledger.csv"; source.write_rows(ledger, records); schemas = out / "output_schemas.json"; schemas.write_text(source.SCHEMAS.read_text())
            pre = out / "preaccess_manifest.json"; pre.write_text(json.dumps({"status":"pre_native_glo90_access_v2","issue":27,"request_rows":63,"environment":analysis.environment(),"schemas":json.loads(schemas.read_text()),"files":{}}))
            files = {str(ledger.relative_to(root)): {"bytes":ledger.stat().st_size,"sha256":analysis.digest(ledger)}}
            files.update({str(path.relative_to(root)): {"bytes":path.stat().st_size,"sha256":analysis.digest(path)} for path in rawdir.iterdir()})
            raw = out / "raw_source_manifest.json"; raw.write_text(json.dumps({"status":"raw_native_glo90_sources_sealed_unopened_v2","preaccess_manifest_sha256":analysis.digest(pre),"expected_sources_sha256":analysis.digest(expected),"responses":63,"http_status_counts":{"200":63,"404":0},"files":files}))
            with patch.multiple(analysis, ROOT=root, OUT=out, PRE=pre, RAW=raw, SCHEMAS=schemas, EXPECTED=expected, LEDGER=ledger):
                analysis.verify_raw(raw, analysis.digest(raw)); data = json.loads(raw.read_text()); data["files"]["unlisted.tif"] = {"bytes":0,"sha256":"0"}; raw.write_text(json.dumps(data))
                with self.assertRaises(ValueError): analysis.verify_raw(raw, analysis.digest(raw))
    def test_ledger_rejects_reordering_and_retained_failure(self):
        expected = [{key: str(value) for key, value in item.items()} for item in source.expected_records()]; records = [dict(expected[0], http_status=200, path=f'source_raw/{expected[0]["object_id"]}.tif')]
        source.validate_ledger(records, expected); records[0]["http_status"] = 500
        with self.assertRaises(ValueError): source.validate_ledger(records, expected)
        records[0]["http_status"] = 200; records[0]["region"] = "99"
        with self.assertRaises(ValueError): source.validate_ledger(records, expected)
    def test_access_and_analysis_actions_are_separate(self):
        acquire = Path(source.__file__).read_text(); calculate = Path(analysis.__file__).read_text(); self.assertNotIn("import rasterio", acquire); self.assertNotIn("urlopen", calculate)
        for text in (acquire, calculate):
            for forbidden in ("sample.csv", "event_catalog", "era5", "hazard_map"): self.assertNotIn(forbidden, text)
    def test_registered_line_budget(self):
        paths = [Path(source.__file__), Path(analysis.__file__), Path(__file__)]; self.assertLessEqual(sum(len(path.read_text().splitlines()) for path in paths), 320)

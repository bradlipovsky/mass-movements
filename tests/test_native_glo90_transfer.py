import json, unittest
from pathlib import Path
import pandas as pd
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
        self.assertEqual(source.normalize_longitude(180), -180)
        self.assertEqual(source.object_id(-4, 180), "Copernicus_DSM_COG_30_S04_00_W180_00_DEM")
        self.assertTrue(all(x["key"] == f'{x["object_id"]}/{x["object_id"]}.tif' for x in source.expected_records()))
    def test_preaccess_manifest_binds_every_input(self):
        source.verify_preaccess(source.PRE)
        self.assertEqual(json.loads(source.PRE.read_text())["schemas"], {"equivalent_area_long_rows": 56, "comparison_rows": 14})
    def test_native_phase_affines_are_half_pixel_translations(self):
        base = Affine(90, 0, 30, 0, -90, 900)
        self.assertEqual(analysis.phase_affine(base, "n00"), base)
        self.assertEqual((analysis.phase_affine(base, "nx45").c, analysis.phase_affine(base, "ny45").f), (75, 945))
        self.assertEqual((analysis.phase_affine(base, "nxy45").c, analysis.phase_affine(base, "nxy45").f), (75, 945))
    def test_departure_rules(self):
        self.assertEqual((analysis.departure(100, 80), analysis.departure(0, 0)), (0.2, 0.0))
        self.assertTrue(pd.isna(analysis.departure(0, 1)))
    def test_access_and_analysis_actions_are_separate(self):
        acquire = Path(source.__file__).read_text(); calculate = Path(analysis.__file__).read_text()
        self.assertNotIn("import rasterio", acquire); self.assertNotIn("urlopen", calculate)
        for text in (acquire, calculate):
            for forbidden in ("sample.csv", "event_catalog", "era5", "hazard_map"): self.assertNotIn(forbidden, text)
    def test_registered_line_budget(self):
        paths = [Path(source.__file__), Path(analysis.__file__), Path(__file__)]
        self.assertLessEqual(sum(len(path.read_text().splitlines()) for path in paths), 320)
    def test_outputs_conserve_registered_dimensions_when_present(self):
        if not (source.OUT / "equivalent_area_long.csv").exists(): return
        long = pd.read_csv(source.OUT / "equivalent_area_long.csv", dtype={"region": str}); comparisons = pd.read_csv(source.OUT / "comparisons.csv", dtype={"region": str})
        self.assertEqual((len(long), len(comparisons)), (56, 14)); self.assertTrue(long.groupby(["region", "phase"]).size().eq(2).all())
        self.assertTrue(comparisons.interpretation.eq("exposed_window_native_source_development_no_pass_label").all())

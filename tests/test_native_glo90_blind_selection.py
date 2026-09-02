import hashlib, hmac, tempfile, unittest
from pathlib import Path
import pandas as pd
from scripts import native_glo90_blind_selection as selection

class BlindSelectionTests(unittest.TestCase):
    def test_exact_candidate_population(self):
        table = selection.candidates()
        self.assertEqual((len(table), table.dominant_region.nunique()), (1335, 18))
        self.assertEqual(table.groupby("dominant_region").size().tolist(), selection.REGION_COUNTS)
        self.assertFalse(table.cell_key.isin(pd.read_csv("data/geographic_sample/sample.csv").cell_key).any())
        exposed = set()
        for name in ["data/denominator/windows.csv", "data/native_glo90_transfer/windows.csv"]:
            item = pd.read_csv(name); exposed.update(zip(item.south, item.west))
        self.assertFalse(pd.Series(list(zip(table.south, table.west))).isin(exposed).any())

    def test_candidate_file_and_manifest_are_exact(self):
        expected = selection.candidates()
        retained = pd.read_csv(selection.CANDIDATES, dtype={"dominant_region": str})
        pd.testing.assert_frame_equal(retained, expected)
        selection.verify_preselection()

    def test_hmac_ranking_is_deterministic_and_region_balanced(self):
        table = selection.candidates(); key = bytes(range(64)); candidate_sha = "ab" * 32
        table["digest"] = table.cell_key.map(
            lambda value: hmac.new(key, f"{candidate_sha}|{value}".encode(), hashlib.sha256).hexdigest())
        ranked = table.sort_values(["dominant_region", "digest", "cell_key"], kind="stable")
        chosen = ranked.groupby("dominant_region").head(1)
        self.assertEqual((len(chosen), chosen.dominant_region.tolist()),
                         (18, [f"{number:02d}" for number in range(1, 19)]))

    def test_deployed_beacon_serialization_and_rejections(self):
        zero = "00" * 64
        pulse = {"uri": "https://example.invalid/chain/2/pulse/1", "version": "2.0", "cipherSuite": 0,
                 "period": 60000, "certificateId": zero, "chainIndex": 2, "pulseIndex": 1,
                 "timeStamp": selection.TARGET_TIME, "localRandomValue": zero,
                 "external": {"sourceId": zero, "statusCode": 0, "value": zero},
                 "listValues": [{"type": name, "value": zero}
                                for name in ["previous", "hour", "day", "month", "year"]],
                 "precommitmentValue": zero, "statusCode": 0}
        message = selection.pulse_message(pulse)
        self.assertEqual(len(message), 790)
        self.assertEqual(message[:4], (len(pulse["uri"])).to_bytes(4, "big"))
        pulse["listValues"].pop()
        with self.assertRaisesRegex(ValueError, "skip-list"):
            selection.pulse_message(pulse)

    def test_no_outcome_or_network_dependency(self):
        source = Path(selection.__file__).read_text()
        for forbidden in ["rasterio", "requests", "urllib", "event_audit", "audited_reanalysis", "pzi.tif"]:
            self.assertNotIn(forbidden, source.lower())

if __name__ == "__main__":
    unittest.main()

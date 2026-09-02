import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest import mock
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
        selection.verify_preselection(selection.digest(selection.PRESELECTION))

    def test_manifest_requires_exact_approval_and_closed_fields(self):
        with self.assertRaisesRegex(ValueError, "unapproved"):
            selection.verify_preselection("00" * 32)
        frozen = json.loads(selection.PRESELECTION.read_text())
        frozen["files"].pop(next(iter(frozen["files"])))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"; path.write_text(json.dumps(frozen))
            with mock.patch.object(selection, "PRESELECTION", path), self.assertRaisesRegex(ValueError, "contract"):
                selection.verify_preselection(selection.digest(path))

    def test_hmac_ranking_is_deterministic_and_region_balanced(self):
        table = selection.candidates(); key = bytes(range(64)); candidate_sha = "ab" * 32
        ranked = selection.rank_candidates(table, key, candidate_sha)
        chosen = ranked[ranked.selected == "yes"]
        self.assertEqual((len(ranked), len(chosen), ranked.random_digest.is_unique, chosen.dominant_region.tolist()),
                         (1335, 18, True, [f"{number:02d}" for number in range(1, 19)]))
        self.assertEqual(ranked.columns.tolist(),
                         [*table.columns, "random_digest", "region_rank", "selected", "inclusion_probability"])
        self.assertEqual((ranked.groupby("dominant_region").region_rank.min() == 1).all(), True)
        self.assertEqual((ranked.inclusion_probability == 1 / ranked.eligible_region_cells).all(), True)

    def test_retained_historical_pulse_verifies_end_to_end(self):
        root = Path("data/geographic_sample/beacon")
        current = json.loads((root / "pulse.json").read_text())["pulse"]
        previous = json.loads((root / "previous_pulse.json").read_text())["pulse"]
        certificate = (root / "certificate.pem").read_bytes()
        selection.verify_certificate(certificate)
        selection.verify_signature(previous, certificate)
        selection.verify_signature(current, certificate)
        selection.verify_links(current, previous)
        self.assertEqual(hashlib.sha512(selection.pulse_message(current) +
                         bytes.fromhex(current["signatureValue"])).hexdigest().upper(), current["outputValue"])
        altered = dict(current); altered["outputValue"] = "00" * 64
        with self.assertRaisesRegex(ValueError, "output"):
            selection.verify_signature(altered, certificate)

    def test_failure_dominates_joint_indeterminacy(self):
        self.assertEqual(selection.overall_status(["PASS"] * 36), "PASS")
        self.assertEqual(selection.overall_status(["PASS"] * 35 + ["INDETERMINATE"]), "INDETERMINATE")
        self.assertEqual(selection.overall_status(["PASS"] * 34 + ["INDETERMINATE", "FAIL"]), "FAIL")
        with self.assertRaisesRegex(ValueError, "population"):
            selection.overall_status(["PASS"] * 35)

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
        pulse["certificateId"] = selection.NIST_CERTIFICATE_ID
        pulse["uri"] = f"https://beacon.nist.gov/beacon/2.0/chain/2/pulse/{pulse['pulseIndex']}"
        selection.verify_identity(pulse, selection.TARGET_TIME)
        with self.assertRaisesRegex(ValueError, "certificate"):
            selection.verify_certificate(b"not a NIST certificate")
        pulse["uri"] = "https://example.invalid/forged"
        with self.assertRaisesRegex(ValueError, "identity"):
            selection.verify_identity(pulse, selection.TARGET_TIME)
        pulse["listValues"].pop()
        with self.assertRaisesRegex(ValueError, "skip-list"):
            selection.pulse_message(pulse)

    def test_no_outcome_or_network_dependency(self):
        source = Path(selection.__file__).read_text()
        for forbidden in ["rasterio", "requests", "urllib", "event_audit", "audited_reanalysis", "pzi.tif"]:
            self.assertNotIn(forbidden, source.lower())

if __name__ == "__main__":
    unittest.main()

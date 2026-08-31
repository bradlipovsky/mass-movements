import csv, hashlib, hmac, tempfile, unittest
from pathlib import Path
from scripts.geographic_select import order_frame

class GeographicSelectTests(unittest.TestCase):
    def test_registered_hmac_order_and_probabilities(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frame.csv"
            fields = ["cell_key", "dominant_region", "stratum_population_cells", "stratum_sample_cells"]
            with open(path, "w", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n"); writer.writeheader()
                writer.writerows([{"cell_key": f"cell-{i}", "dominant_region": "01",
                                   "stratum_population_cells": 3, "stratum_sample_cells": 2} for i in range(3)])
            output = "ab" * 64
            rows = order_frame(path, output)
            frame_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            expected = sorted(hmac.new(bytes.fromhex(output), f"{frame_hash}|cell-{i}".encode(),
                                       hashlib.sha256).hexdigest() for i in range(3))
            self.assertEqual([row["random_digest"] for row in rows], expected)
            self.assertEqual([row["selected"] for row in rows], ["yes", "yes", "no"])
            self.assertTrue(all(row["same_stratum_pair_probability"] == "0.333333333333" for row in rows))
    def test_invalid_beacon_value_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frame.csv"; path.write_text("cell_key,dominant_region\n")
            with self.assertRaises(ValueError): order_frame(path, "00")
if __name__ == "__main__":
    unittest.main()

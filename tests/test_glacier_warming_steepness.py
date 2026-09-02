import csv
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "glacier_warming_steepness",
    Path(__file__).parents[1] / "scripts" / "glacier_warming_steepness.py")
gws = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(gws)
class GlacierWarmingSteepnessTests(unittest.TestCase):
    def row(self, **changes):
        row = dict(rgi_id="RGI2000-v7.0-G-13-00001", o1region="13",
                   o2region="13-02", glims_id="G000000E00000N",
                   src_date="2000-01-01T00:00:00", cenlon="0", cenlat="0",
                   area_km2="1", conn_lvl="0", surge_type="0", term_type="0",
                   zmed_m="4000", aspect_sec="1", dem_source="COPDEM30")
        row.update(changes); return row
    def test_case_rule_is_frozen(self):
        screened = gws.screened_cases()
        primary = gws.primary_cases()
        self.assertEqual(len(screened), 14)
        self.assertEqual(len(primary), 10)
        self.assertEqual(gws.frozen_dependence_clusters()["aru-1-2016"], "site-aru")
        self.assertEqual({row["initial_failure"] for row in screened}, {"glacier_detachment", "glacier_collapse"})
        self.assertEqual({row["threshold_quantity"] for row in primary}, {"initial_volume"})
    def test_grid_spacing_and_outcome_omission(self):
        row = self.row(area_km2="4", slope_deg="89")
        result = gws.frame_row(row)
        self.assertAlmostEqual(float(result["rgi_grid_spacing_m"]), 38)
        self.assertNotIn("slope_deg", result)
        self.assertEqual(set(result), set(gws.FRAME_COLUMNS))
    def test_aspect_wrap_and_missing(self):
        self.assertTrue(gws.aspect_matches("1", "8"))
        self.assertTrue(gws.aspect_matches("4", "5"))
        self.assertFalse(gws.aspect_matches("1", "3"))
        self.assertFalse(gws.aspect_matches("9", "1"))
    def test_matching_relaxation(self):
        case = self.row()
        adjacent = self.row(rgi_id="x", aspect_sec="8")
        wrong_aspect = self.row(rgi_id="y", aspect_sec="4")
        wrong_subregion = self.row(rgi_id="z", o2region="13-03")
        self.assertTrue(gws.eligible_background(case, adjacent, 1))
        self.assertFalse(gws.eligible_background(case, wrong_aspect, 1))
        self.assertTrue(gws.eligible_background(case, wrong_aspect, 2))
        self.assertFalse(gws.eligible_background(case, wrong_subregion, 2))
        self.assertTrue(gws.eligible_background(case, wrong_subregion, 3))
    def test_matching_calipers(self):
        case = self.row()
        self.assertTrue(gws.eligible_background(case, self.row(area_km2="0.25"), 1))
        self.assertTrue(gws.eligible_background(case, self.row(area_km2="4"), 1))
        self.assertFalse(gws.eligible_background(case, self.row(area_km2="4.01"), 1))
        self.assertFalse(gws.eligible_background(case, self.row(zmed_m="4501"), 1))
        self.assertFalse(gws.eligible_background(case, self.row(conn_lvl="1"), 1))
        self.assertFalse(gws.eligible_background(case, self.row(zmed_m=""), 1))
        self.assertFalse(gws.eligible_background(case, self.row(area_km2=""), 1))
    def test_review_closure_requires_two_independent_decisions(self):
        base = dict(candidate_id="case", reviewer_1="one", reviewer_2="two",
                    reviewer_1_decision="agree", reviewer_2_decision="agree",
                    review_state="agree")
        gws.require_review_closure([base])
        with self.assertRaises(ValueError):
            gws.require_review_closure([{**base, "reviewer_2": "one"}])
        with self.assertRaises(ValueError):
            gws.require_review_closure([{**base, "reviewer_2_decision": "disagree"}])
    def test_independent_clusters_cannot_share_controls(self):
        cases = ["flat-creek-2013", "tinguiririca-2007"]
        frame = {f"case-{i}": self.row(rgi_id=f"case-{i}") for i in range(2)}
        for i in range(45):
            frame[f"control-{i:02}"] = self.row(rgi_id=f"control-{i:02}")
        assertions = [dict(candidate_id=case, rgi_id=f"case-{i}", proposed_status="proposed_unique",
            review_state="agree", dependence_cluster=f"cluster-{i}") for i, case in enumerate(cases)]
        _, selected, summary = gws.build_matches(frame, assertions)
        left = {row["rgi_id"] for row in selected if row["candidate_id"] == cases[0]}
        right = {row["rgi_id"] for row in selected if row["candidate_id"] == cases[1]}
        self.assertEqual((len(left), len(right)), (20, 20))
        self.assertFalse(left & right)
        self.assertEqual({value[0] for value in summary.values()}, {"matched"})
        assertions[1]["dependence_cluster"] = "cluster-0"
        _, shared, _ = gws.build_matches(frame, assertions)
        shared_sets = [{row["rgi_id"] for row in shared if row["candidate_id"] == case} for case in cases]
        self.assertTrue(shared_sets[0] & shared_sets[1])
        tiny = {key: value for key, value in frame.items() if key.startswith("case") or key < "control-10"}
        pools, selected, summary = gws.build_matches(tiny, assertions[:1])
        self.assertEqual((len(pools), len(selected), next(iter(summary.values()))[0]), (11, 0, "unmatched"))
        original = gws.digest
        try:
            gws.digest = lambda *_: "collision"; pools, _, _ = gws.build_matches(tiny, assertions[:1])
            self.assertEqual([row["rgi_id"] for row in pools], sorted(row["rgi_id"] for row in pools))
        finally: gws.digest = original
    def test_digest_is_stable_and_case_specific(self):
        self.assertEqual(gws.digest("case", "glacier"),
                         "4d62e4b2938f68d5cfcb96eb55edd34ae96c7f9dbd8595202fc02aee3387f07f")
        self.assertNotEqual(gws.digest("case", "glacier"),
                            gws.digest("other", "glacier"))
    def test_glims_index_omits_blank_identifiers(self):
        frame = {"a": self.row(rgi_id="a", glims_id=""), "b": self.row(rgi_id="b", glims_id="G")}
        self.assertEqual(gws.index_glims(frame), {"G": ["b"]})
    def test_attribute_member_rejects_ambiguity(self):
        record = {"region": "01", "members": [
            {"name": "one-attributes.csv"}, {"name": "two-attributes.csv"}]}
        with self.assertRaises(ValueError):
            gws.attribute_member(record)


if __name__ == "__main__":
    unittest.main()

import importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "glacier_matching_freeze", Path(__file__).parents[1] / "scripts" / "glacier_matching_freeze.py")
gmf = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(gmf)

class GlacierMatchingFreezeTests(unittest.TestCase):
    def frame_row(self, rgi_id, glims_id="G", src_date="2000-01-01T00:00:00"):
        return {"rgi_id": rgi_id, "glims_id": glims_id, "src_date": src_date}
    def assertion(self, case, rgi_id, cluster):
        return {"candidate_id": case, "proposed_status": "proposed_unique", "rgi_id": rgi_id,
                "glims_id": "G" + rgi_id, "evidence_source": "source",
                "evidence_locator": "locator", "mapping_method": "method",
                "dependence_cluster": cluster, "review_state": "agree"}
    def packet(self, assertion, same=None):
        return {"candidate_id": assertion["candidate_id"],
            "proposed_status": assertion["proposed_status"], "rgi_id": assertion["rgi_id"],
            "glims_id": assertion["glims_id"], "same_glims_rgi_ids": same or assertion["rgi_id"],
            "rgi_src_date": "2000-01-01T00:00:00", "distance_km": "", "overlap_fraction": "",
            "lineage_members": assertion["rgi_id"], "evidence_source": assertion["evidence_source"],
            "evidence_locator": assertion["evidence_locator"], "mapping_method": assertion["mapping_method"]}
    def pool(self, case, ids, selected=()):
        ranked = sorted((gmf.gate.digest(case, value), value) for value in ids)
        return [{"candidate_id": case, "rgi_id": value, "selected": value in selected,
                 "matching_level": 1, "pool_size": len(ids), "digest": digest, "rank": rank}
                for rank, (digest, value) in enumerate(ranked, 1)]
    def test_text_digest_is_order_invariant(self):
        self.assertEqual(gmf.text_digest(["b\n", "a\n"]), gmf.text_digest(["a\n", "b\n"]))
    def test_review_packet_validation(self):
        assertion = self.assertion("case", "r1", "cluster")
        frame = {"r1": self.frame_row("r1", "Gr1"), "blank": self.frame_row("blank", "")}
        packet = self.packet(assertion)
        self.assertEqual(gmf.validate_review_rows(frame, [assertion], [packet])["case"], packet)
        with self.assertRaises(ValueError):
            gmf.validate_review_rows(frame, [assertion], [{**packet, "rgi_src_date": "wrong"}])
    def test_replay_prevents_cross_cluster_reuse_and_counts_availability(self):
        assertions = [self.assertion("a", "ca", "one"), self.assertion("b", "cb", "two")]
        left_ids = ["r%02d" % i for i in range(30)]; right_ids = ["r%02d" % i for i in range(10, 50)]
        left_base = self.pool("a", left_ids); left_selected = {row["rgi_id"] for row in left_base[:20]}
        left = self.pool("a", left_ids, left_selected)
        right_base = self.pool("b", right_ids)
        right_available = [row for row in right_base if row["rgi_id"] not in left_selected]
        right_selected = {row["rgi_id"] for row in right_available[:20]}
        right = self.pool("b", right_ids, right_selected)
        pools = left + right
        selected = [row for row in pools if row["selected"]]
        replay, claimed = gmf.replay_selection(pools, selected, assertions, {"a", "b"})
        self.assertEqual((replay["a"]["available_pool_size"], replay["b"]["available_pool_size"]),
                         (30, len(right_available)))
        self.assertEqual(len(claimed), 40)
        bad_ids = {row["rgi_id"] for row in right_base[:20]}
        bad = self.pool("b", right_ids, bad_ids)
        with self.assertRaises(ValueError):
            gmf.replay_selection(left + bad, [row for row in left + bad if row["selected"]],
                                 assertions, {"a", "b"})
    def test_replay_allows_same_cluster_reuse(self):
        assertions = [self.assertion("a", "ca", "same"), self.assertion("b", "cb", "same")]
        ids = ["r%02d" % i for i in range(20)]
        pools = self.pool("a", ids, set(ids)) + self.pool("b", ids, set(ids))
        replay, claimed = gmf.replay_selection(pools, pools, assertions, {"a", "b"})
        self.assertEqual((len(replay), len(claimed)), (2, 20))
    def test_replay_keeps_unmatched_admitted_case(self):
        assertion = self.assertion("a", "ca", "one")
        pool = self.pool("a", ["r%02d" % i for i in range(19)])
        replay, claimed = gmf.replay_selection(pool, [], [assertion], {"a"})
        self.assertEqual(replay["a"], {"available_pool_size": 19, "selected_count": 0})
        self.assertEqual(claimed, {})
    def test_partial_shared_cluster_is_not_fully_matched(self):
        assertions = [self.assertion("a", "ca", "same"), self.assertion("b", "cb", "same")]
        self.assertEqual(gmf.fully_matched_clusters(assertions, {"a", "b"}, {"a"}), set())
        self.assertEqual(gmf.fully_matched_clusters(assertions, {"a", "b"}, {"a", "b"}), {"same"})
    def test_replay_rejects_wrong_rank_flags_and_selected_metadata(self):
        assertion = self.assertion("a", "ca", "one")
        base = self.pool("a", ["r%02d" % i for i in range(21)])
        wrong_ids = {row["rgi_id"] for row in base[1:21]}
        wrong = self.pool("a", [row["rgi_id"] for row in base], wrong_ids)
        with self.assertRaisesRegex(ValueError, "first available"):
            gmf.replay_selection(wrong, [row for row in wrong if row["selected"]],
                                 [assertion], {"a"})
        correct_ids = {row["rgi_id"] for row in base[:20]}
        correct = self.pool("a", [row["rgi_id"] for row in base], correct_ids)
        altered = [{**row, "matching_level": 2} for row in correct if row["selected"]]
        with self.assertRaisesRegex(ValueError, "exactly copy"):
            gmf.replay_selection(correct, altered, [assertion], {"a"})
        invalid = [{**row, "selected": 0} if not row["selected"] else row for row in correct]
        with self.assertRaisesRegex(ValueError, "invalid selected flag"):
            gmf.replay_selection(invalid, [row for row in correct if row["selected"]],
                                 [assertion], {"a"})
    def test_output_status_distinguishes_review_and_inventory_exclusions(self):
        cases = {name: {"date_start": "2000-01-01", "initial_failure": "glacier_collapse",
                        "threshold_quantity": "initial_volume"}
                 for name in ("reviewed-out", "eqip-sermia-2014", "dykhtau-2023")}
        assertions = [
            {**self.assertion("reviewed-out", "r1", "one"), "review_state": "excluded"},
            {**self.assertion("eqip-sermia-2014", "", "two"), "proposed_status": "no_rgi_object",
             "glims_id": ""},
            {**self.assertion("dykhtau-2023", "", "three"), "proposed_status": "unresolved",
             "glims_id": ""},
        ]
        packet = {row["candidate_id"]: {"same_glims_rgi_ids": ""} for row in assertions}
        with mock.patch.object(gmf.gate, "primary_cases",
                               return_value=[{"candidate_id": name} for name in cases]):
            _, statuses, _ = gmf.output_rows({}, cases, assertions, {}, {}, packet)
        by_id = {row["candidate_id"]: row for row in statuses}
        self.assertEqual(by_id["reviewed-out"]["crosswalk_status"], "review_excluded")
        self.assertEqual(by_id["eqip-sermia-2014"]["crosswalk_status"], "no_rgi_object")
        self.assertEqual(by_id["dykhtau-2023"]["crosswalk_status"], "unresolved")
    def test_sealed_input_hash_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); frame = root / "rgi_matching_frame"; frame.mkdir()
            manifest = root / "frame_manifest.json"
            manifest.write_text(json.dumps({"status": "outcome-blind RGI 7 matching frame; slope and climate omitted",
                                            "frozen_inputs": gmf.gate.FROZEN}))
            packet = root / "packet.csv"; packet.write_text("x\n")
            assertions = root / "assertions.csv"; assertions.write_text("x\n")
            with mock.patch.object(gmf, "git_output", return_value=""), \
                 mock.patch.object(gmf.subprocess, "call", return_value=0), \
                 mock.patch.object(gmf.gate, "ASSERTIONS", assertions), \
                 mock.patch.object(gmf.gate, "sha256", return_value="wrong"):
                with self.assertRaisesRegex(ValueError, "unapproved frame manifest"):
                    gmf.require_sealed_inputs(frame, packet)
    def test_approved_manifest_digest_fails_before_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "preaccess_manifest.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "approved digest"):
                gmf.verify_manifest(directory, approved_sha256="0" * 64)
    def test_freeze_refuses_existing_target_before_access(self):
        with self.assertRaises(RuntimeError): gmf.gate.preaccess(Path("missing"))
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "preaccess_manifest.json").write_text("{}")
            with self.assertRaises(FileExistsError):
                gmf.freeze(frame_dir=Path(directory, "missing"), output_dir=directory)

if __name__ == "__main__":
    unittest.main()

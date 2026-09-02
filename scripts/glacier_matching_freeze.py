#!/usr/bin/env python3
"""Seal reviewed glacier links and deterministic matched backgrounds."""
import csv, hashlib, json, os, platform, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import glacier_warming_steepness as gate
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "glacier_warming_steepness"
PACKET = OUT / "crosswalk_review_packet.csv"
PROGRAM = Path(__file__).resolve()
TESTS = ROOT / "tests" / "test_glacier_matching_freeze.py"
REQUIREMENTS = ROOT / "requirements-glacier-matching-freeze.txt"
FRAME_COMMIT = "4a3e02e4db3994487f229750a8b4d8e1f2b474ca"
FRAME_MANIFEST_SHA256 = "f642c90727995b64328d333a17942ce051eb18040cba3851d48dfb0905fc2254"
PACKET_SHA256 = "66a2a502a7120908966d11fdf2b2cab19eca9f28103f085f0f84a64eae55769b"
ASSERTION_COMMIT = "6783b10625dbd000e5e36dd7cf36b3719c0ce3b6"
ASSERTION_SHA256 = "d4c0637851b9ed9cf4f21168566c21134f1dfa0857428c43a5fabaafd0b1ab27"
DECISION_CAP = "DESCRIPTIVE_ONLY; at most seven initial clusters before ERA5-cell merging"
FIELDS = {
    "case_frame.csv": ["candidate_id", "date_start", "initial_failure", "threshold_quantity", "index_year", "primary_case"],
    "case_glacier_status.csv": ["candidate_id", "crosswalk_status", "rgi_id", "glims_id", "same_glims_rgi_ids", "dependence_cluster", "review_state", "match_status"],
    "matching_summary.csv": ["candidate_id", "primary_case", "crosswalk_status", "match_status", "matching_level", "pool_size", "available_pool_size", "selected_count"],
    "matching_pools.csv": ["candidate_id", "matching_level", "pool_size", "rgi_id", "digest", "rank", "selected"],
    "selected_backgrounds.csv": ["candidate_id", "matching_level", "pool_size", "rgi_id", "digest", "rank", "selected"],
}
TARGET_NAMES = tuple(FIELDS) + ("preaccess_manifest.json",)
LOCK = OUT / ".matching-freeze.lock"
MANIFEST_FIELDS = {
    "status", "registration_url", "git_commit", "python", "platform", "cases",
    "primary_cases", "reviewed_unique_primary_cases", "matched_primary_cases",
    "initial_clusters", "matched_initial_clusters", "decision_cap",
    "final_cluster_merge", "pool_rows", "selected_background_rows",
    "cross_cluster_control_reuse", "primary_id_sha256", "selected_pair_sha256",
    "per_case", "inputs", "outputs",
}
def text_digest(lines):
    return hashlib.sha256("".join(sorted(lines)).encode()).hexdigest()
def read_csv(path):
    with open(path, newline="") as stream:
        return list(csv.DictReader(stream))
def matching_records(rows):
    return [tuple(str(row[field]) for field in FIELDS["matching_pools.csv"]) for row in rows]
def fully_matched_clusters(assertions, reviewed, matched):
    clusters = {row["dependence_cluster"] for row in assertions if row["candidate_id"] in reviewed}
    return {cluster for cluster in clusters if all(row["candidate_id"] in matched for row in assertions
            if row["candidate_id"] in reviewed and row["dependence_cluster"] == cluster)}
def git_output(*args):
    return subprocess.check_output(["git"] + list(args), cwd=str(ROOT),
                                   universal_newlines=True).strip()
def require_sealed_inputs(frame_dir, packet_path):
    if git_output("status", "--porcelain"):
        raise ValueError("matching freeze requires a clean worktree")
    for commit in (FRAME_COMMIT, ASSERTION_COMMIT):
        if subprocess.call(["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                           cwd=str(ROOT)) != 0:
            raise ValueError(f"required ancestor is absent: {commit}")
    frame_manifest = Path(frame_dir).parent / "frame_manifest.json"
    if gate.sha256(frame_manifest) != FRAME_MANIFEST_SHA256:
        raise ValueError("unapproved frame manifest")
    if gate.sha256(packet_path) != PACKET_SHA256 or gate.sha256(gate.ASSERTIONS) != ASSERTION_SHA256:
        raise ValueError("unapproved packet or assertion table")
    metadata = json.loads(frame_manifest.read_text())
    if (metadata["status"] != "outcome-blind RGI 7 matching frame; slope and climate omitted"
            or metadata["frozen_inputs"] != gate.FROZEN):
        raise ValueError("frame manifest semantics drift")
def bound_inputs(frame_dir, packet_path):
    amendments = [ROOT / "protocol" / f"glacier-warming-steepness-amendment-{i}.md"
                  for i in (1, 2, 3)]
    partitions = [Path(frame_dir) / f"{region}.csv" for region in sorted(gate.EXPECTED_COUNTS)]
    direct = [ROOT / name for name in gate.FROZEN]
    paths = [gate.ASSERTIONS, packet_path, Path(frame_dir).parent / "frame_manifest.json",
             gate.PROTOCOL, gate.SCHEMAS, gate.REQUIREMENTS, gate.TESTS, Path(gate.__file__),
             PROGRAM, TESTS, REQUIREMENTS, ROOT / "data" / "event_audit" / "sources.csv"]
    return sorted(set(paths + amendments + partitions + direct), key=lambda path: str(path))
def validate_review_rows(frame, assertions, packet_rows):
    if len(packet_rows) != len(assertions) or len({row["candidate_id"] for row in packet_rows}) != len(assertions):
        raise ValueError("review packet does not contain one unique row per assertion")
    packet = {row["candidate_id"]: row for row in packet_rows}
    glims = gate.index_glims(frame)
    for assertion in assertions:
        row = packet[assertion["candidate_id"]]
        expected_same = "|".join(sorted(glims.get(assertion["glims_id"], [])))
        expected_date = frame.get(assertion["rgi_id"], {}).get("src_date", "")
        expected_lineage = (assertion["rgi_id"]
                            if assertion["proposed_status"] == "proposed_unique" else "")
        pairs = (("proposed_status", assertion["proposed_status"]),
                 ("rgi_id", assertion["rgi_id"]), ("glims_id", assertion["glims_id"]),
                 ("same_glims_rgi_ids", expected_same), ("rgi_src_date", expected_date),
                 ("lineage_members", expected_lineage),
                 ("evidence_source", assertion["evidence_source"]),
                 ("evidence_locator", assertion["evidence_locator"]),
                 ("mapping_method", assertion["mapping_method"]))
        for field, expected in pairs:
            if row[field] != expected:
                raise ValueError(f"review packet drift {assertion['candidate_id']}: {field}")
    return packet
def replay_selection(pools, selected, assertions, admitted_ids=None):
    links = {row["candidate_id"]: row for row in assertions}
    if len(links) != len(assertions):
        raise ValueError("duplicate assertion case")
    if admitted_ids is None:
        primary_ids = {row["candidate_id"] for row in gate.primary_cases()}
        admitted_ids = {row["candidate_id"] for row in assertions
                        if row["candidate_id"] in primary_ids and row["review_state"] == "agree"
                        and row["proposed_status"] == "proposed_unique"}
    if not set(admitted_ids) <= set(links):
        raise ValueError("unknown admitted case")
    admitted = sorted(admitted_ids, key=lambda case: (links[case]["dependence_cluster"], case))
    if len({(row["candidate_id"], row["rgi_id"]) for row in pools}) != len(pools):
        raise ValueError("duplicate matching-pool key")
    if len({(row["candidate_id"], row["rgi_id"]) for row in selected}) != len(selected):
        raise ValueError("duplicate selected-background key")
    if {row["candidate_id"] for row in pools} - set(admitted):
        raise ValueError("matching pool contains an unadmitted case")
    if any(not (type(row["selected"]) is bool or
                type(row["selected"]) is str and row["selected"] in ("True", "False"))
           for row in pools + selected):
        raise ValueError("invalid selected flag")
    pool_by_pair = {(row["candidate_id"], row["rgi_id"]): row for row in pools}
    for row in selected:
        pair = (row["candidate_id"], row["rgi_id"])
        if pair not in pool_by_pair or row != pool_by_pair[pair] or row["selected"] not in (True, "True"):
            raise ValueError("selected table does not exactly copy selected pool rows")
    selected_pairs = {(row["candidate_id"], row["rgi_id"]) for row in selected}
    claimed, result = {}, {}
    for case in admitted:
        cluster = links[case]["dependence_cluster"]
        case_pool = sorted((row for row in pools if row["candidate_id"] == case),
                           key=lambda row: (int(row["rank"]), row["rgi_id"]))
        if case_pool:
            if [int(row["rank"]) for row in case_pool] != list(range(1, len(case_pool) + 1)):
                raise ValueError(f"noncontiguous pool ranks: {case}")
            if (len({row["matching_level"] for row in case_pool}) != 1
                    or int(case_pool[0]["matching_level"]) not in (1, 2, 3) or any(
                    int(row["pool_size"]) != len(case_pool) for row in case_pool)):
                raise ValueError(f"pool metadata drift: {case}")
            if any(row["digest"] != gate.digest(case, row["rgi_id"]) for row in case_pool):
                raise ValueError(f"pool digest drift: {case}")
            expected_order = sorted(case_pool, key=lambda row: (row["digest"], row["rgi_id"]))
            if [row["rgi_id"] for row in case_pool] != [row["rgi_id"] for row in expected_order]:
                raise ValueError(f"pool hash ordering drift: {case}")
        available_rows = [row for row in case_pool
                          if claimed.get(row["rgi_id"]) in (None, cluster)]
        expected = {(case, row["rgi_id"]) for row in available_rows[:20]}
        if len(available_rows) < 20:
            expected = set()
        observed = {(case, row["rgi_id"]) for row in selected if row["candidate_id"] == case}
        pool_flags = {(case, row["rgi_id"]) for row in case_pool
                      if row["selected"] is True or row["selected"] == "True"}
        if observed != expected or pool_flags != expected:
            raise ValueError(f"selected rows do not equal first available ranks: {case}")
        case_selected = [row for row in case_pool if (case, row["rgi_id"]) in observed]
        for row in case_selected:
            owner = claimed.get(row["rgi_id"])
            if owner not in (None, cluster):
                raise ValueError(f"cross-cluster control reuse: {row['rgi_id']}")
            claimed[row["rgi_id"]] = cluster
        result[case] = {"available_pool_size": len(available_rows),
                        "selected_count": len(case_selected)}
    if selected_pairs != {(case, row["rgi_id"]) for case in admitted
                          for row in pools if row["candidate_id"] == case
                          and (case, row["rgi_id"]) in selected_pairs}:
        raise ValueError("selected table contains an unadmitted or absent row")
    return result, claimed

def output_rows(frame, cases, assertions, summary, replay, packet):
    primary_ids = {row["candidate_id"] for row in gate.primary_cases()}
    case_rows, status_rows, summary_rows = [], [], []
    assertion_by_id = {row["candidate_id"]: row for row in assertions}
    for case in sorted(cases):
        source, link = cases[case], assertion_by_id[case]
        primary = case in primary_ids
        crosswalk = ("review_excluded" if link["review_state"] != "agree" else
                     "unique" if link["proposed_status"] == "proposed_unique" else link["proposed_status"])
        match = summary.get(case, ("not_primary" if not primary else "crosswalk_excluded", None, 0, 0))
        case_rows.append({"candidate_id": case, "date_start": source["date_start"],
            "initial_failure": source["initial_failure"], "threshold_quantity": source["threshold_quantity"],
            "index_year": int(source["date_start"][:4]), "primary_case": primary})
        status_rows.append({"candidate_id": case, "crosswalk_status": crosswalk,
            "rgi_id": link["rgi_id"], "glims_id": link["glims_id"],
            "same_glims_rgi_ids": packet[case]["same_glims_rgi_ids"],
            "dependence_cluster": link["dependence_cluster"], "review_state": link["review_state"],
            "match_status": match[0]})
        summary_rows.append({"candidate_id": case, "primary_case": primary,
            "crosswalk_status": crosswalk, "match_status": match[0], "matching_level": match[1],
            "pool_size": match[2], "available_pool_size": replay.get(case, {}).get("available_pool_size", 0),
            "selected_count": match[3]})
    return case_rows, status_rows, summary_rows

def verify_manifest(output_dir=OUT, approved_sha256=None):
    output_dir = Path(output_dir)
    manifest_path = output_dir / "preaccess_manifest.json"
    if approved_sha256 and gate.sha256(manifest_path) != approved_sha256:
        raise ValueError("preaccess manifest is not the approved digest")
    manifest = json.loads(manifest_path.read_text())
    if set(manifest) != MANIFEST_FIELDS:
        raise ValueError("preaccess manifest field drift")
    if manifest["status"] != "reviewed crosswalk and deterministic backgrounds; registered systematic outcomes unopened":
        raise ValueError("invalid preaccess status")
    if subprocess.call(["git", "merge-base", "--is-ancestor", manifest["git_commit"], "HEAD"],
                       cwd=str(ROOT)) != 0:
        raise ValueError("preaccess execution commit is not an ancestor")
    expected_inputs = {str(path.relative_to(ROOT))
                       for path in bound_inputs(OUT / "rgi_matching_frame", PACKET)}
    if set(manifest["inputs"]) != expected_inputs or set(manifest["outputs"]) != set(FIELDS):
        raise ValueError("preaccess manifest file-set drift")
    for name, record in manifest["inputs"].items():
        path = ROOT / name
        if path.stat().st_size != record["bytes"] or gate.sha256(path) != record["sha256"]:
            raise ValueError(f"bound input drift: {name}")
    for name, record in manifest["outputs"].items():
        path = output_dir / name
        with open(path, newline="") as stream:
            reader = csv.DictReader(stream); rows = list(reader)
        if (name not in FIELDS or reader.fieldnames != FIELDS[name]
                or path.stat().st_size != record["bytes"] or gate.sha256(path) != record["sha256"]
                or len(rows) != record["rows"]):
            raise ValueError(f"frozen output drift: {name}")
    pools, selected = read_csv(output_dir / "matching_pools.csv"), read_csv(output_dir / "selected_backgrounds.csv")
    assertions = read_csv(gate.ASSERTIONS)
    exact_pools, exact_selected, exact_summary = gate.build_matches(
        gate.load_frame(OUT / "rgi_matching_frame"), assertions)
    if matching_records(pools) != matching_records(exact_pools) or matching_records(
            selected) != matching_records(exact_selected):
        raise ValueError("matching tables are not the exact frozen-frame result")
    replay, claimed = replay_selection(pools, selected, assertions)
    matched = sum(row["selected_count"] == 20 for row in replay.values())
    summary_rows = read_csv(output_dir / "matching_summary.csv")
    primary_rows = [row for row in summary_rows if row["primary_case"] == "True"]
    if len(summary_rows) != 14 or len({row["candidate_id"] for row in summary_rows}) != 14:
        raise ValueError("matching summary does not contain 14 unique cases")
    expected_per_case = {row["candidate_id"]: {
        "match_status": row["match_status"],
        "matching_level": int(row["matching_level"]) if row["matching_level"] else None,
        "pool_size": int(row["pool_size"]),
        "available_pool_size": int(row["available_pool_size"]),
        "selected_count": int(row["selected_count"]),
    } for row in primary_rows}
    for case, counts in replay.items():
        exact = exact_summary[case]
        if (expected_per_case[case]["match_status"] != exact[0]
                or expected_per_case[case]["matching_level"] != exact[1]
                or expected_per_case[case]["pool_size"] != exact[2]
                or expected_per_case[case]["selected_count"] != exact[3]
                or expected_per_case[case]["available_pool_size"] != counts["available_pool_size"]
                or expected_per_case[case]["selected_count"] != counts["selected_count"]
                or expected_per_case[case]["match_status"] !=
                ("matched" if counts["selected_count"] == 20 else "unmatched")):
            raise ValueError(f"matching summary disagrees with replay: {case}")
    primary_ids = sorted(row["candidate_id"] for row in gate.primary_cases())
    if {row["candidate_id"] for row in primary_rows} != set(primary_ids):
        raise ValueError("matching summary primary case drift")
    reviewed_ids = {row["candidate_id"] for row in assertions
                    if row["candidate_id"] in set(primary_ids) and row["review_state"] == "agree"
                    and row["proposed_status"] == "proposed_unique"}
    initial_clusters = {row["dependence_cluster"] for row in assertions
                        if row["candidate_id"] in reviewed_ids}
    matched_ids = {case for case, counts in replay.items() if counts["selected_count"] == 20}
    matched_clusters = fully_matched_clusters(assertions, reviewed_ids, matched_ids)
    pair_digest = text_digest(row["candidate_id"] + "|" + row["rgi_id"] + "\n" for row in selected)
    if (manifest["cases"] != 14 or manifest["primary_cases"] != 10
            or manifest["reviewed_unique_primary_cases"] != len(reviewed_ids)
            or manifest["matched_primary_cases"] != matched
            or manifest["initial_clusters"] != len(initial_clusters)
            or manifest["matched_initial_clusters"] != len(matched_clusters)
            or manifest["decision_cap"] != DECISION_CAP
            or manifest["final_cluster_merge"] != "pending ERA5 weights"
            or manifest["pool_rows"] != len(pools)
            or manifest["selected_background_rows"] != 20 * matched
            or manifest["cross_cluster_control_reuse"] != 0
            or manifest["primary_id_sha256"] != text_digest(case + "\n" for case in primary_ids)
            or manifest["selected_pair_sha256"] != pair_digest
            or manifest["per_case"] != expected_per_case
            or len(claimed) > len(selected)):
        raise ValueError("preaccess semantic replay failed")
    return manifest

def _freeze_locked(frame_dir, output_dir):
    output_dir = Path(output_dir)
    existing = [name for name in TARGET_NAMES if (output_dir / name).exists()]
    if existing:
        raise FileExistsError(f"refusing to replace frozen targets: {existing}")
    frame = gate.load_frame(frame_dir)
    cases, assertions = gate.validate_assertions(frame)
    gate.require_review_closure(assertions)
    packet_path = output_dir / PACKET.name
    packet_rows = read_csv(packet_path)
    packet = validate_review_rows(frame, assertions, packet_rows)
    pools, selected, summary = gate.build_matches(frame, assertions)
    primary_ids = {row["candidate_id"] for row in gate.primary_cases()}
    reviewed_ids = {row["candidate_id"] for row in assertions
                    if row["candidate_id"] in primary_ids and row["review_state"] == "agree"
                    and row["proposed_status"] == "proposed_unique"}
    replay, claimed = replay_selection(pools, selected, assertions, reviewed_ids)
    case_rows, status_rows, summary_rows = output_rows(
        frame, cases, assertions, summary, replay, packet)
    tables = dict(zip(FIELDS, (case_rows, status_rows, summary_rows, pools, selected)))
    temporary = Path(tempfile.mkdtemp(prefix="matching-freeze-", dir=output_dir))
    published = []
    try:
        for name in FIELDS:
            gate.write_csv_atomic(temporary / name, FIELDS[name], tables[name])
        primary_ids = sorted(primary_ids)
        matched_ids = {case for case, row in replay.items() if row["selected_count"] == 20}
        initial_clusters = {row["dependence_cluster"] for row in assertions if row["candidate_id"] in reviewed_ids}
        matched_clusters = fully_matched_clusters(assertions, reviewed_ids, matched_ids)
        inputs = bound_inputs(frame_dir, packet_path)
        manifest = {"status": "reviewed crosswalk and deterministic backgrounds; registered systematic outcomes unopened",
            "registration_url": "https://github.com/bradlipovsky/mass-movements/issues/33",
            "git_commit": git_output("rev-parse", "HEAD"),
            "python": sys.version, "platform": platform.platform(), "cases": 14,
            "primary_cases": 10, "reviewed_unique_primary_cases": len(reviewed_ids),
            "matched_primary_cases": len(matched_ids), "initial_clusters": len(initial_clusters),
            "matched_initial_clusters": len(matched_clusters), "decision_cap": DECISION_CAP,
            "final_cluster_merge": "pending ERA5 weights",
            "pool_rows": len(pools), "selected_background_rows": len(selected),
            "cross_cluster_control_reuse": 0,
            "primary_id_sha256": text_digest(case + "\n" for case in primary_ids),
            "selected_pair_sha256": text_digest(
                row["candidate_id"] + "|" + row["rgi_id"] + "\n" for row in selected),
            "per_case": {row["candidate_id"]: {key: row[key] for key in
                ("match_status", "matching_level", "pool_size", "available_pool_size", "selected_count")}
                for row in summary_rows if row["primary_case"]},
            "inputs": {str(path.relative_to(ROOT)): {"bytes": path.stat().st_size,
                "sha256": gate.sha256(path)} for path in inputs},
            "outputs": {name: {"rows": len(tables[name]), "bytes": (temporary / name).stat().st_size,
                "sha256": gate.sha256(temporary / name)} for name in FIELDS}}
        gate.write_json_atomic(temporary / "preaccess_manifest.json", manifest)
        verify_manifest(temporary)
        existing = [name for name in TARGET_NAMES if (output_dir / name).exists()]
        if existing:
            raise FileExistsError(f"target appeared during freeze: {existing}")
        for name in TARGET_NAMES:
            os.link(str(temporary / name), str(output_dir / name))
            published.append(output_dir / name)
        result = verify_manifest(output_dir)
    except Exception:
        for path in published: path.unlink()
        shutil.rmtree(temporary, ignore_errors=True); raise
    shutil.rmtree(temporary)
    return result

def freeze(frame_dir=OUT / "rgi_matching_frame", output_dir=OUT):
    output_dir = Path(output_dir)
    existing = [name for name in TARGET_NAMES if (output_dir / name).exists()]
    if existing:
        raise FileExistsError(f"refusing to replace frozen targets: {existing}")
    packet_path = output_dir / PACKET.name
    require_sealed_inputs(frame_dir, packet_path)
    lock = output_dir / LOCK.name
    descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        return _freeze_locked(frame_dir, output_dir)
    finally:
        os.close(descriptor); lock.unlink()

def main():
    print(json.dumps(freeze(), indent=2, sort_keys=True))

if __name__ == "__main__":
    main()

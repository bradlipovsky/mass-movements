#!/usr/bin/env python3
"""Freeze the outcome-oblivious RGI frame, case links, and matched sets."""
import argparse, csv, hashlib, json, math, os, shutil, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "glacier_warming_steepness"
ASSERTIONS = OUT / "case_glacier_assertions.csv"
RGI_SOURCE = ROOT / "data" / "geographic_sample" / "source_raw" / "rgi"
RGI_MANIFEST = ROOT / "data" / "geographic_sample" / "source_manifest.json"
PROTOCOL = ROOT / "protocol" / "global-glacier-warming-steepness.md"
SCHEMAS = ROOT / "protocol" / "glacier_warming_steepness_output_schemas.json"
REQUIREMENTS = ROOT / "requirements-glacier-warming-steepness-gate.txt"
TESTS = ROOT / "tests" / "test_glacier_warming_steepness.py"

FROZEN = {
    "data/candidates.csv": "8b6b0f972180e26c326aaa0e6a501080843bd4b6e6674b07c5aa009340c8a249",
    "data/candidate_clusters.csv": "fd1545d60fe527e9881ec9169cf9ee93dc94eab1470595641695d1bcf089f309",
    "data/event_audit/manifest.json": "3263706361aeeb828ad33b318b1b19076e4448e2ff098a40af6110d6d34f317e",
    "data/geographic_sample/source_manifest.json": "6b411fc26af146c9dd0959490775e413aa97f57491cf6de6c91261e7e09e196b",
}
EXPECTED_COUNTS = {
    "01": 27509, "02": 18730, "03": 5216, "04": 11009, "05": 19994, "06": 568,
    "07": 1666, "08": 3410, "09": 1069, "10": 7155, "11": 4079, "12": 2275,
    "13": 75613, "14": 37562, "15": 18587, "16": 3695, "17": 30634, "18": 3018, "19": 2742,
}
FRAME_COLUMNS = [
    "rgi_id", "o1region", "o2region", "glims_id", "src_date", "cenlon", "cenlat",
    "area_km2", "conn_lvl", "zmed_m", "aspect_sec", "dem_source", "rgi_grid_spacing_m",
]
def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
def write_json_atomic(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, sort_keys=True); stream.write("\n")
    os.replace(temporary, path)
def write_csv_atomic(path, fields, rows):
    path = Path(path)
    with tempfile.NamedTemporaryFile("w", newline="", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    os.replace(temporary, path)
def require_frozen():
    for name, expected in FROZEN.items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"frozen input drift: {name}")
def screened_cases():
    require_frozen()
    with open(ROOT / "data" / "candidates.csv", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows = [row for row in rows if row["consensus_decision"] == "include"
            and row["analysis_role"] == "event_candidate"
            and row["initial_failure"] in ("glacier_detachment", "glacier_collapse")]
    rows.sort(key=lambda row: row["candidate_id"])
    if len(rows) != 14 or len({row["candidate_id"] for row in rows}) != 14:
        raise ValueError("screened case frame is not the frozen 14 rows")
    return rows
def primary_cases():
    rows = [row for row in screened_cases() if row["threshold_quantity"] == "initial_volume"]
    if len(rows) != 10:
        raise ValueError("primary case frame is not the frozen 10 volume-threshold rows")
    return rows
def frozen_dependence_clusters():
    result = {row["candidate_id"]: row["candidate_id"] for row in screened_cases()}
    with open(ROOT / "data" / "candidate_clusters.csv", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["cluster_type"] not in ("trigger_cluster", "site_group"):
                continue
            for candidate_id in set(row["candidate_ids"].split(";")) & set(result):
                if result[candidate_id] != candidate_id:
                    raise ValueError(f"overlapping frozen dependence groups: {candidate_id}")
                result[candidate_id] = row["cluster_id"]
    return result
def archive_records(source_dir=RGI_SOURCE):
    manifest = json.loads(RGI_MANIFEST.read_text())
    records = sorted(manifest["archives"], key=lambda row: row["region"])
    if [row["region"] for row in records] != sorted(EXPECTED_COUNTS):
        raise ValueError("RGI manifest regions differ")
    for record in records:
        path = Path(source_dir) / record["filename"]
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise ValueError(f"RGI archive drift: {path.name}")
        yield record, path
def attribute_member(record):
    expected = [row for row in record["members"]
                if row["name"].endswith("-attributes.csv") and "/" not in row["name"]]
    if len(expected) != 1:
        raise ValueError(f"attribute member ambiguity: {record['region']}")
    return expected[0]
def frame_row(row):
    area = float(row["area_km2"])
    if not area > 0:
        raise ValueError(f"nonpositive RGI area: {row['rgi_id']}")
    spacing = min(100.0, 14.0 * math.sqrt(area) + 10.0)
    values = {name: row[name] for name in FRAME_COLUMNS if name != "rgi_grid_spacing_m"}
    values["rgi_grid_spacing_m"] = f"{spacing:.8f}"
    return values
def build_frame(source_dir=RGI_SOURCE, output_dir=OUT):
    require_frozen()
    target = Path(output_dir) / "rgi_matching_frame"
    if target.exists():
        raise FileExistsError(f"refusing to replace {target}")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="rgi-frame-", dir=output_dir))
    ids = set()
    files = {}
    try:
        for record, archive in archive_records(source_dir):
            member = attribute_member(record)
            path = temporary / f"{record['region']}.csv"
            count = 0
            with zipfile.ZipFile(archive) as zf, zf.open(member["name"]) as raw, \
                    open(path, "w", newline="") as output:
                import io
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                writer = csv.DictWriter(output, fieldnames=FRAME_COLUMNS, lineterminator="\n")
                writer.writeheader()
                for source in reader:
                    row = frame_row(source)
                    if row["rgi_id"] in ids:
                        raise ValueError(f"duplicate RGI ID: {row['rgi_id']}")
                    if row["o1region"] != record["region"]:
                        raise ValueError(f"RGI region mismatch: {row['rgi_id']}")
                    ids.add(row["rgi_id"]); writer.writerow(row); count += 1
            if count != EXPECTED_COUNTS[record["region"]]:
                raise ValueError(f"RGI count mismatch: {record['region']}={count}")
            files[path.name] = {"rows": count, "bytes": path.stat().st_size,
                                "sha256": sha256(path)}
        if len(ids) != 274531:
            raise ValueError(f"global RGI count mismatch: {len(ids)}")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    manifest = {"status": "outcome-blind RGI 7 matching frame; slope and climate omitted",
                "rows": len(ids), "regional_counts": EXPECTED_COUNTS, "files": files,
                "frozen_inputs": FROZEN}
    path = Path(output_dir) / "frame_manifest.json"
    write_json_atomic(path, manifest)
    return manifest
def load_frame(frame_dir):
    frame_dir = Path(frame_dir)
    manifest_path = frame_dir.parent / "frame_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["rows"] != 274531 or manifest["regional_counts"] != EXPECTED_COUNTS:
        raise ValueError("invalid RGI frame manifest")
    rows = {}
    for region in sorted(EXPECTED_COUNTS):
        path = frame_dir / f"{region}.csv"
        record = manifest["files"][path.name]
        if (path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]
                or record["rows"] != EXPECTED_COUNTS[region]):
            raise ValueError(f"RGI frame partition drift: {region}")
        with open(path, newline="") as stream:
            for row in csv.DictReader(stream):
                rows[row["rgi_id"]] = row
    if len(rows) != 274531:
        raise ValueError("incomplete RGI frame")
    return rows
def validate_assertions(frame):
    cases = {row["candidate_id"]: row for row in screened_cases()}
    with open(ASSERTIONS, newline="") as stream:
        assertions = list(csv.DictReader(stream))
    if len(assertions) != 14 or {row["candidate_id"] for row in assertions} != set(cases):
        raise ValueError("crosswalk assertions do not conserve the 14 cases")
    with open(ROOT / "data" / "event_audit" / "sources.csv", newline="") as stream:
        source_ids = {row["source_id"] for row in csv.DictReader(stream)}
    frozen_clusters = frozen_dependence_clusters()
    for row in assertions:
        if row["dependence_cluster"] != frozen_clusters[row["candidate_id"]]:
            raise ValueError(f"dependence cluster drift: {row['candidate_id']}")
        status = row["proposed_status"]
        if status == "proposed_unique":
            if row["rgi_id"] not in frame:
                raise ValueError(f"unknown RGI link: {row['candidate_id']}")
            if frame[row["rgi_id"]]["glims_id"] != row["glims_id"]:
                raise ValueError(f"GLIMS mismatch: {row['candidate_id']}")
        elif status not in ("unresolved", "no_rgi_object") or row["rgi_id"]:
            raise ValueError(f"invalid crosswalk status: {row['candidate_id']}")
        if not row["evidence_source"] or not row["evidence_locator"]:
            raise ValueError(f"uncited crosswalk row: {row['candidate_id']}")
        for source_id in row["evidence_source"].split(";"):
            if source_id not in source_ids and not source_id.startswith("doi:"):
                raise ValueError(f"unregistered source {source_id}: {row['candidate_id']}")
        if row["review_state"] == "agree" and not (row["reviewer_1"] and row["reviewer_2"]):
            raise ValueError(f"unattributed agreement: {row['candidate_id']}")
    return cases, assertions
def require_review_closure(assertions):
    for row in assertions:
        decisions = (row["reviewer_1_decision"], row["reviewer_2_decision"])
        if not row["reviewer_1"] or not row["reviewer_2"] or row["reviewer_1"] == row["reviewer_2"]:
            raise ValueError(f"two distinct reviewers required: {row['candidate_id']}")
        if any(value not in ("agree", "disagree") for value in decisions):
            raise ValueError(f"review decision is not closed: {row['candidate_id']}")
        expected = "agree" if decisions == ("agree", "agree") else "excluded"
        if row["review_state"] != expected:
            raise ValueError(f"invalid adjudicated state: {row['candidate_id']}")
def aspect_matches(left, right):
    try:
        left, right = int(left), int(right)
    except (TypeError, ValueError):
        return False
    if left not in range(1, 9) or right not in range(1, 9):
        return False
    return min((left - right) % 8, (right - left) % 8) <= 1
def eligible_background(case, other, level):
    try:
        area_ratio = float(other["area_km2"]) / float(case["area_km2"])
        elevation_difference = abs(float(other["zmed_m"]) - float(case["zmed_m"]))
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    common = (bool(other["conn_lvl"]) and bool(case["conn_lvl"])
              and other["conn_lvl"] == case["conn_lvl"]
              and .25 <= area_ratio <= 4 and elevation_difference <= 500)
    if not common:
        return False
    if level == 1:
        return other["o2region"] == case["o2region"] and aspect_matches(
            case["aspect_sec"], other["aspect_sec"])
    if level == 2:
        return other["o2region"] == case["o2region"]
    if level == 3:
        return other["o1region"] == case["o1region"]
    raise ValueError(f"unknown matching level: {level}")
def digest(case_id, rgi_id):
    message = f"glacier-warming-steepness-v1|{case_id}|{rgi_id}".encode()
    return hashlib.sha256(message).hexdigest()
def index_glims(frame):
    result = {}
    for row in frame.values():
        if row["glims_id"]: result.setdefault(row["glims_id"], []).append(row["rgi_id"])
    return result
def review_packet(frame_dir, output_dir=OUT):
    frame = load_frame(frame_dir)
    _, assertions = validate_assertions(frame)
    by_glims = index_glims(frame)
    fields = ["candidate_id", "proposed_status", "rgi_id", "glims_id", "same_glims_rgi_ids", "rgi_src_date",
              "distance_km", "overlap_fraction", "lineage_members", "evidence_source", "evidence_locator", "mapping_method"]
    rows = [{**{name: row[name] for name in fields if name not in {"same_glims_rgi_ids", "rgi_src_date", "distance_km", "overlap_fraction", "lineage_members"}},
             "same_glims_rgi_ids": "|".join(sorted(by_glims.get(row["glims_id"], []))),
             "rgi_src_date": frame.get(row["rgi_id"], {}).get("src_date", ""),
             "distance_km": "", "overlap_fraction": "",
             "lineage_members": row["rgi_id"] if row["proposed_status"] == "proposed_unique" else ""}
            for row in sorted(assertions, key=lambda item: item["candidate_id"])]
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    write_csv_atomic(Path(output_dir) / "crosswalk_review_packet.csv", fields, rows)
    return {"rows": len(rows), "status": "outcome-blind crosswalk review packet"}
def build_matches(frame, assertions):
    primary_ids = {row["candidate_id"] for row in primary_cases()}
    admitted = [row for row in assertions if row["candidate_id"] in primary_ids
                and row["proposed_status"] == "proposed_unique"
                and row["review_state"] == "agree"]
    excluded = {row["rgi_id"] for row in assertions if row["rgi_id"]}
    pools, selected, summary = [], [], {}
    claimed_by = {}
    order = lambda row: (row["dependence_cluster"], row["candidate_id"])
    for assertion in sorted(admitted, key=order):
        case = frame[assertion["rgi_id"]]
        pool = []
        for level in (1, 2, 3):
            pool = [row for row in frame.values() if row["rgi_id"] not in excluded
                    and eligible_background(case, row, level)]
            if len(pool) >= 20:
                break
        ranked = sorted((digest(assertion["candidate_id"], row["rgi_id"]),
                         row["rgi_id"], row) for row in pool)
        chosen = []
        if len(pool) >= 20:
            for value, rgi_id, row in ranked:
                owner = claimed_by.get(rgi_id)
                if owner is None or owner == assertion["dependence_cluster"]:
                    chosen.append(rgi_id)
                    if len(chosen) == 20:
                        break
        complete = len(chosen) == 20
        chosen = set(chosen) if complete else set()
        for rank, (value, rgi_id, row) in enumerate(ranked, 1):
            is_selected = rgi_id in chosen
            record = {"candidate_id": assertion["candidate_id"], "matching_level": level,
                      "pool_size": len(pool), "rgi_id": row["rgi_id"], "digest": value,
                      "rank": rank, "selected": is_selected}
            pools.append(record)
            if is_selected:
                selected.append(record)
                claimed_by[rgi_id] = assertion["dependence_cluster"]
        summary[assertion["candidate_id"]] = (
            "matched" if complete else "unmatched", level, len(pool), len(chosen))
    return pools, selected, summary
def preaccess(frame_dir, output_dir=OUT):
    frame = load_frame(frame_dir)
    cases, assertions = validate_assertions(frame)
    require_review_closure(assertions)
    pools, selected, match_summary = build_matches(frame, assertions)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    primary_ids = {row["candidate_id"] for row in primary_cases()}
    case_frame_path = output_dir / "case_frame.csv"
    case_frame_fields = ["candidate_id", "date_start", "initial_failure",
                         "threshold_quantity", "index_year", "primary_case"]
    case_frame_rows = []
    for candidate_id in sorted(cases):
        source = cases[candidate_id]
        case_frame_rows.append({"candidate_id": candidate_id,
            "date_start": source["date_start"], "initial_failure": source["initial_failure"],
            "threshold_quantity": source["threshold_quantity"],
            "index_year": int(source["date_start"][:4]),
            "primary_case": candidate_id in primary_ids})
    write_csv_atomic(case_frame_path, case_frame_fields, case_frame_rows)
    status_path = output_dir / "case_glacier_status.csv"
    assertion_by_id = {row["candidate_id"]: row for row in assertions}
    status_fields = ["candidate_id", "crosswalk_status", "rgi_id", "glims_id",
                     "same_glims_rgi_ids", "dependence_cluster", "review_state", "match_status"]
    status_rows, summary_rows = [], []
    for candidate_id in sorted(cases):
        link = assertion_by_id[candidate_id]
        if link["review_state"] != "agree":
            status = "review_excluded"
        elif link["proposed_status"] == "proposed_unique":
            status = "unique"
        else:
            status = link["proposed_status"]
        glims_matches = sorted(row["rgi_id"] for row in frame.values()
                               if link["glims_id"] and row["glims_id"] == link["glims_id"])
        if candidate_id not in primary_ids:
            match = ("not_primary", None, 0, 0)
        elif status != "unique":
            match = ("crosswalk_excluded", None, 0, 0)
        else:
            match = match_summary.get(candidate_id, ("unmatched", None, 0, 0))
        status_rows.append({"candidate_id": candidate_id, "crosswalk_status": status,
            "rgi_id": link["rgi_id"], "glims_id": link["glims_id"],
            "same_glims_rgi_ids": "|".join(glims_matches),
            "dependence_cluster": link["dependence_cluster"],
            "review_state": link["review_state"], "match_status": match[0]})
        summary_rows.append({"candidate_id": candidate_id,
            "primary_case": candidate_id in primary_ids, "crosswalk_status": status,
            "match_status": match[0], "matching_level": match[1],
            "pool_size": match[2], "selected_count": match[3]})
    write_csv_atomic(status_path, status_fields, status_rows)
    summary_path = output_dir / "matching_summary.csv"
    write_csv_atomic(summary_path, ["candidate_id", "primary_case", "crosswalk_status",
        "match_status", "matching_level", "pool_size", "selected_count"], summary_rows)
    for name, rows in (("matching_pools.csv", pools), ("selected_backgrounds.csv", selected)):
        path = output_dir / name
        fields = ["candidate_id", "matching_level", "pool_size", "rgi_id", "digest",
                  "rank", "selected"]
        write_csv_atomic(path, fields, rows)
    bound = [ASSERTIONS, case_frame_path, status_path, summary_path,
             output_dir / "matching_pools.csv", output_dir / "selected_backgrounds.csv",
             PROTOCOL, SCHEMAS, Path(__file__), TESTS, REQUIREMENTS,
             Path(frame_dir).parent / "frame_manifest.json"]
    manifest = {"status": "pre-feature-access crosswalk and deterministic backgrounds",
                "cases": 14, "primary_cases": 10,
                "decision_cap": "DESCRIPTIVE_ONLY; at most seven trigger/site clusters",
                "admitted_primary_cases": sum(row["candidate_id"] in primary_ids
                    and row["review_state"] == "agree"
                    and row["proposed_status"] == "proposed_unique" for row in assertions),
                "selected_background_rows": len(selected),
                "files": {str(path.relative_to(ROOT)): {"bytes": path.stat().st_size,
                    "sha256": sha256(path)} for path in bound}}
    write_json_atomic(output_dir / "preaccess_manifest.json", manifest)
    return manifest
def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action")
    build = sub.add_parser("build-frame")
    build.add_argument("--source-dir", type=Path, default=RGI_SOURCE)
    build.add_argument("--output-dir", type=Path, default=OUT)
    packet = sub.add_parser("prepare-review")
    packet.add_argument("--frame-dir", type=Path, default=OUT / "rgi_matching_frame")
    packet.add_argument("--output-dir", type=Path, default=OUT)
    freeze = sub.add_parser("preaccess")
    freeze.add_argument("--frame-dir", type=Path, default=OUT / "rgi_matching_frame")
    freeze.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    if not args.action:
        parser.error("an action is required")
    result = (build_frame(args.source_dir, args.output_dir) if args.action == "build-frame" else
              review_packet(args.frame_dir, args.output_dir) if args.action == "prepare-review" else
              preaccess(args.frame_dir, args.output_dir))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

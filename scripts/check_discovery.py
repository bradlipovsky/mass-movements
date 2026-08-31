#!/usr/bin/env python3
"""Check discovery-frame reconciliation and dependence metadata."""

import csv
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUTOFF = datetime(2026, 8, 30)
SOURCE_CUTOFF = datetime(2026, 8, 31, 1, 15, 53)
PROVENANCE_FIELDS = [
    "provenance_id", "frame_id", "frame_record", "candidate_ids",
    "relationship", "notes",
]
CLUSTER_FIELDS = ["cluster_id", "cluster_type", "candidate_ids", "notes"]
MANIFEST_FIELDS = [
    "frame_id", "frame_record", "source_row", "source_identity", "date_text",
    "prefilter_evidence",
]


def read_csv(name, fields=None):
    with (ROOT / "data" / name).open(newline="") as stream:
        reader = csv.DictReader(stream)
        if fields and reader.fieldnames != fields:
            raise ValueError("{} has an invalid header".format(name))
        return list(reader)


def ids(value):
    return [item for item in value.split(";") if item]


def date(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("{} has invalid date {!r}".format(label, value))


candidates = read_csv("candidates.csv")
frames = read_csv("frame_screening.csv")
provenance = read_csv("candidate_provenance.csv", PROVENANCE_FIELDS)
clusters = read_csv("candidate_clusters.csv", CLUSTER_FIELDS)
searches = read_csv("discovery_searches.csv")
manifest = read_csv("source_frames/frame_qualifiers.csv", MANIFEST_FIELDS)

candidate_ids = {row["candidate_id"] for row in candidates}
frame_ids = {row["frame_id"] for row in frames}
if len(frame_ids) != len(frames):
    raise ValueError("frame_screening.csv has duplicate frame_id values")

integer_fields = [
    "published_cases", "downloaded_rows", "window_rows",
    "status_retained_window_rows", "numeric_threshold_rows",
]
expected = {}
for row in frames:
    for field in integer_fields:
        value = row[field]
        if not re.fullmatch(r"[0-9]+", value):
            raise ValueError("frame {} {} is not a nonnegative integer".format(
                row["frame_id"], field))
    expected[row["frame_id"]] = int(row["numeric_threshold_rows"])

provenance_ids = [row["provenance_id"] for row in provenance]
if len(set(provenance_ids)) != len(provenance_ids):
    raise ValueError("candidate_provenance.csv has duplicate provenance_id values")
frame_records = []
observed = Counter()
for row in provenance:
    label = "provenance {}".format(row["provenance_id"])
    if row["frame_id"] not in frame_ids:
        raise ValueError("{} has unknown frame".format(label))
    frame_records.append((row["frame_id"], row["frame_record"]))
    linked = ids(row["candidate_ids"])
    if not linked or set(linked) - candidate_ids:
        raise ValueError("{} has missing or unknown candidate IDs".format(label))
    relation = "one_to_one" if len(linked) == 1 else "one_to_many"
    if row["relationship"] != relation:
        raise ValueError("{} has inconsistent relationship".format(label))
    observed[row["frame_id"]] += 1
if len(set(frame_records)) != len(frame_records):
    raise ValueError("candidate_provenance.csv repeats a frame record")
if dict(observed) != expected:
    raise ValueError("frame reconciliation {} does not equal {}".format(
        dict(observed), expected))
manifest_records = [(row["frame_id"], row["frame_record"]) for row in manifest]
if len(set(manifest_records)) != len(manifest_records):
    raise ValueError("frame_qualifiers.csv repeats a source record")
if set(manifest_records) != set(frame_records):
    raise ValueError("provenance does not exactly match the qualifier manifest")
for row in manifest:
    if not row["source_row"].isdigit() or not row["prefilter_evidence"]:
        raise ValueError("manifest record {} lacks its source locator or evidence".format(
            row["frame_record"]))

source_hashes = {
    "pangaea_ltt_979839.tsv":
        "c3fe591a5fffa9b1124dd50c401092c99f953512e5428064251fff2f1e78ad57",
    "hma_rock_ice_10458200.xlsx":
        "96361f7490d9684d874f6a38273050fbe654e1f1dd11ac078ed66679d3c94151",
}
for name, expected_hash in source_hashes.items():
    digest = hashlib.sha256((ROOT / "data" / "source_frames" / name).read_bytes()).hexdigest()
    if digest != expected_hash:
        raise ValueError("immutable source frame {} has changed".format(name))
pangaea_lines = (ROOT / "data" / "source_frames" /
                  "pangaea_ltt_979839.tsv").read_text().splitlines()
for row in manifest:
    if row["frame_id"] == "pangaea_ltt":
        source_record = pangaea_lines[int(row["source_row"]) - 1].split("\t")[0]
        if source_record != row["frame_record"]:
            raise ValueError("PANGAEA manifest locator does not match source bytes")

cluster_ids = [row["cluster_id"] for row in clusters]
if len(set(cluster_ids)) != len(cluster_ids):
    raise ValueError("candidate_clusters.csv has duplicate cluster_id values")
cluster_sets = []
for row in clusters:
    label = "cluster {}".format(row["cluster_id"])
    if row["cluster_type"] not in {
            "site_group", "trigger_cluster", "cascade_cluster", "tsunami_cluster"}:
        raise ValueError("{} has unknown cluster type".format(label))
    linked = ids(row["candidate_ids"])
    if len(linked) < 2 or len(set(linked)) != len(linked) or set(linked) - candidate_ids:
        raise ValueError("{} must link at least two known candidates".format(label))
    cluster_sets.append(frozenset(linked))

event_groups = {}
for row in candidates:
    event_groups.setdefault(row["event_group_id"], set()).add(row["candidate_id"])
for group, linked in event_groups.items():
    if len(linked) > 1 and frozenset(linked) not in cluster_sets:
        raise ValueError("multi-candidate event group {} lacks a cluster".format(group))

for row in searches:
    executed = datetime.strptime(row["executed_utc"], "%Y-%m-%dT%H:%M:%SZ")
    if executed > SOURCE_CUTOFF:
        raise ValueError("search {} is after the source cutoff".format(row["search_id"]))
    if row["resource"] == "multi_resource_web_search" and \
            "results 1-10 per query" not in row["result_scope"]:
        raise ValueError("search {} lacks per-query result bounds".format(row["search_id"]))

transcript = (ROOT / "protocol" / "discovery-search-transcript.md").read_text()
queries = []
inside = False
for line in transcript.splitlines():
    if line.startswith("```"):
        inside = not inside
    elif inside and line.strip():
        queries.append(line.strip())
exposure = re.compile(r"\b(climate|warming|permafrost|deglaciation|retreat)\b", re.I)
if not queries or any(exposure.search(query) for query in queries):
    raise ValueError("search transcript is empty or contains a causal exposure query")

allowed_reasons = {
    "include": {"eligible"},
    "exclude": {"outside_window", "outside_setting", "excluded_process",
                "below_threshold", "duplicate"},
    "uncertain": {"primary_source_pending", "threshold_not_documented",
                  "taxonomy_pending", "time_not_documented",
                  "location_not_documented", "source_inaccessible",
                  "setting_pending"},
}
source_types = {
    "Dohmen2025Data", "Zhong2024Data", "Svennevig2024", "glacier_search",
    "rock_search", "web_search", "primary_followup",
}
for row in candidates:
    label = "candidate {}".format(row["candidate_id"])
    if row["discovery_source"] not in source_types:
        raise ValueError("{} has uncontrolled discovery source".format(label))
    for prefix in ("screen_1", "screen_2", "consensus"):
        decision = row[prefix + "_decision"]
        reason = row[prefix + "_reason"]
        if reason not in allowed_reasons[decision]:
            raise ValueError("{} has incoherent {} decision and reason".format(
                label, prefix))
    screens = {row["screen_1_decision"], row["screen_2_decision"]}
    if row["consensus_decision"] not in screens:
        raise ValueError("{} consensus is unsupported by either screen".format(label))
    if len(screens) > 1 and not re.search(
            r"\b(consensus|resolv|rule|source|reconstruction)\b", row["notes"], re.I):
        raise ValueError("{} does not document disagreement resolution".format(label))

    start = date(row["date_start"], label)
    end = date(row["date_end"], label) if row["date_end"] else start
    precision = row["date_precision"]
    if precision in {"second", "minute", "day"} and (end - start).days > 1:
        raise ValueError("{} interval conflicts with {} precision".format(label, precision))
    if precision == "month" and (start.year, start.month) != (end.year, end.month):
        raise ValueError("{} crosses months despite month precision".format(label))
    if precision == "year" and start.year != end.year:
        raise ValueError("{} crosses years despite year precision".format(label))
    if row["consensus_decision"] == "include" and end > CUTOFF:
        raise ValueError("{} extends beyond the occurrence cutoff".format(label))

print("discovery valid: {} frame records reconciled; {} dependence clusters".format(
    len(provenance), len(clusters)))

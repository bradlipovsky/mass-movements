"""Validate catalog structure, types, provenance, and analysis invariants."""

import csv
import math
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

EVENT_FIELDS = [
    "event_id", "event_name", "status", "event_group_id", "analysis_role",
    "date_utc", "date_end_utc", "date_precision", "date_source_key",
    "date_source_locator", "latitude_deg", "longitude_deg",
    "coordinate_precision", "coordinate_source_key",
    "coordinate_source_locator", "location", "setting", "initial_failure",
    "downstream_sequence", "source_keys", "identity_notes",
]
MEASUREMENT_FIELDS = [
    "measurement_id", "event_id", "quantity", "value", "lower_bound",
    "upper_bound", "unit", "value_relation", "uncertainty",
    "uncertainty_type", "confidence_level", "observation_period", "scenario",
    "evidence_kind", "source_key", "source_locator", "notes",
]
CLAIM_FIELDS = [
    "claim_id", "event_id", "claim_scope", "evidence_kind",
    "evidence_strength", "claim", "source_key", "source_locator",
]
DISCOVERY_SEARCH_FIELDS = [
    "search_id", "executed_utc", "reviewer", "resource", "resource_url",
    "query", "date_start", "date_end", "result_scope", "climate_blind_check",
    "notes",
]
FRAME_FLOW_FIELDS = [
    "frame_id", "source_url", "published_cases", "downloaded_rows",
    "window_rows", "status_retained_window_rows", "numeric_threshold_rows",
    "notes",
]
CANDIDATE_FIELDS = [
    "candidate_id", "event_group_id", "event_name", "date_start", "date_end",
    "date_precision", "latitude_deg", "longitude_deg", "location", "country",
    "setting", "initial_failure", "threshold_quantity", "threshold_relation",
    "threshold_value", "threshold_lower_bound", "threshold_upper_bound",
    "threshold_unit", "discovery_source", "discovery_record",
    "primary_source_url", "primary_source_locator", "screen_1_reviewer",
    "screen_1_decision", "screen_1_reason", "screen_2_reviewer",
    "screen_2_decision", "screen_2_reason", "consensus_decision",
    "consensus_reason", "analysis_role", "trigger_time_eligible", "notes",
]

EVENT_STATUS = {"occurred", "inferred_occurred", "active_slope"}
ANALYSIS_ROLES = {"event_candidate", "dependent_episode", "prospective_case"}
DATE_PRECISION = {
    "reviewed_origin_time", "onset_interval", "approximate_minute",
    "approximate_two_pulse_interval", "minute", "not_applicable",
}
COORDINATE_PRECISION = {
    "satellite_estimate", "paper_rounded", "inferred_same_gully", "location_named"
}
STATUS_ROLE = {
    ("occurred", "event_candidate"),
    ("inferred_occurred", "dependent_episode"),
    ("active_slope", "prospective_case"),
}
SETTINGS = {"high_mountain", "fjord"}
VALUE_RELATIONS = {
    "equal", "approximate", "greater_than", "lower_limit", "upper_limit", "range",
    "not_documented",
}
MEASUREMENT_EVIDENCE = {
    "observation", "preliminary_observation", "reconstruction", "model_output"
}
CLAIM_EVIDENCE = MEASUREMENT_EVIDENCE | {"published_inference", "project_interpretation"}
UNCERTAINTY_TYPES = {
    "", "reported_unspecified", "one_standard_deviation", "standard_error",
    "confidence_interval", "conservative_error_sum", "parameterization_spread",
}
CLAIM_SCOPES = {
    "process_chain", "immediate_trigger", "climate_preconditioning",
    "precursor", "catalog_reconciliation",
}
EVIDENCE_STRENGTH = {"direct", "strong", "moderate", "weak", "unresolved"}
CANDIDATE_DATE_PRECISION = {
    "second", "minute", "day", "satellite_interval", "month", "year",
}
CANDIDATE_SETTINGS = {
    "high_mountain", "fjord", "alpine_lake", "proglacial_lagoon",
    "volcanic_island", "coastal_bay", "reservoir", "quarry", "ocean",
    "mine_lake",
}
CANDIDATE_FAILURES = {
    "rock_avalanche", "rockslide", "rock_ice_avalanche", "glacier_detachment",
    "glacier_collapse", "ice_rock_avalanche", "moraine_slide",
    "volcanic_flank_collapse", "soft_sediment_slide", "unresolved_rock_or_ice",
    "channel_bank_slide", "debris_flow",
}
THRESHOLDS = {"initial_volume": (1_000_000, "m3"),
              "travel_distance": (2_000, "m"),
              "tsunami_runup": (10, "m"),
              "not_documented": (None, "not_applicable")}
SCREEN_DECISIONS = {"include", "exclude", "uncertain"}
SCREEN_REASONS = {
    "eligible", "excluded_process", "outside_setting", "below_threshold",
    "threshold_not_documented", "time_not_documented", "location_not_documented",
    "duplicate", "primary_source_pending", "taxonomy_pending", "outside_window",
    "source_inaccessible", "setting_pending",
}
CANDIDATE_ROLES = {
    "event_candidate", "dependent_episode", "not_assigned", "not_applicable",
}
DECISION_ROLE = {
    "include": {"event_candidate", "dependent_episode"},
    "exclude": {"not_applicable"},
    "uncertain": {"not_assigned"},
}
DECISION_TRIGGER = {
    "include": {"yes", "no"},
    "exclude": {"not_applicable"},
    "uncertain": {"not_assigned"},
}


def read_csv(name, expected_fields):
    with (DATA / name).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != expected_fields:
            raise ValueError(
                f"{name} header differs from the required schema:\n"
                f"found {reader.fieldnames}\nexpected {expected_fields}"
            )
        rows = list(reader)
    if not rows:
        raise ValueError(f"{name} is empty")
    if any(None in row for row in rows):
        raise ValueError(f"{name} has a row with too many columns")
    if any(None in row.values() for row in rows):
        raise ValueError(f"{name} has a row with too few columns")
    for row_number, row in enumerate(rows, start=2):
        whitespace = [key for key, value in row.items() if value != value.strip()]
        if whitespace:
            raise ValueError(f"{name}:{row_number} has edge whitespace in {whitespace}")
    return rows


def require(row, fields, label):
    missing = [field for field in fields if not row[field]]
    if missing:
        raise ValueError(f"{label} is missing required fields {missing}")


def controlled(value, allowed, label):
    if value not in allowed:
        raise ValueError(f"{label} has invalid value {value!r}")


def number(value, label):
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{label} is not numeric: {value!r}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{label} is not finite: {value!r}")
    return parsed


def timestamp(value, label):
    if not value.endswith("Z"):
        raise ValueError(f"{label} must use an explicit UTC Z suffix")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ValueError(f"{label} is not an ISO-8601 timestamp: {value!r}") from error
    return parsed


def calendar_date(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError(f"{label} is not an ISO calendar date: {value!r}") from error


events = read_csv("events.csv", EVENT_FIELDS)
measurements = read_csv("measurements.csv", MEASUREMENT_FIELDS)
claims = read_csv("claims.csv", CLAIM_FIELDS)
discovery_searches = read_csv("discovery_searches.csv", DISCOVERY_SEARCH_FIELDS)
frame_flow = read_csv("frame_screening.csv", FRAME_FLOW_FIELDS)
candidates = read_csv("candidates.csv", CANDIDATE_FIELDS)

event_ids = [row["event_id"] for row in events]
if len(set(event_ids)) != len(event_ids):
    raise ValueError("events.csv has duplicate event_id values")
event_id_set = set(event_ids)

bibliography = (ROOT / "latex" / "references.bib").read_text(encoding="utf-8")
bibliography_keys = set(re.findall(r"@\w+\{([^,]+),", bibliography))
used_sources = set()
event_groups = {}

for row in events:
    label = f"event {row['event_id']}"
    require(
        row,
        ["event_id", "event_name", "status", "event_group_id", "analysis_role",
         "date_precision", "location", "setting", "initial_failure",
         "downstream_sequence", "source_keys", "identity_notes"],
        label,
    )
    controlled(row["status"], EVENT_STATUS, f"{label} status")
    controlled(row["analysis_role"], ANALYSIS_ROLES, f"{label} analysis_role")
    controlled(row["date_precision"], DATE_PRECISION, f"{label} date_precision")
    controlled(
        row["coordinate_precision"], COORDINATE_PRECISION,
        f"{label} coordinate_precision",
    )
    controlled(row["setting"], SETTINGS, f"{label} setting")
    if (row["status"], row["analysis_role"]) not in STATUS_ROLE:
        raise ValueError(f"{label} has an incoherent status and analysis_role")
    event_groups.setdefault(row["event_group_id"], set()).add(row["analysis_role"])

    dates = bool(row["date_utc"]), bool(row["date_end_utc"])
    coordinates = bool(row["latitude_deg"]), bool(row["longitude_deg"])
    if dates[1] and not dates[0]:
        raise ValueError(f"{label} has an end date without a start date")
    if coordinates[0] != coordinates[1]:
        raise ValueError(f"{label} must provide both latitude and longitude")
    if row["analysis_role"] != "prospective_case" and (not dates[0] or not coordinates[0]):
        raise ValueError(f"{label} requires an event time and coordinates")
    if dates[0]:
        require(row, ["date_source_key", "date_source_locator"], label)
        start = timestamp(row["date_utc"], f"{label} date_utc")
        if dates[1] and timestamp(row["date_end_utc"], f"{label} date_end_utc") < start:
            raise ValueError(f"{label} ends before it starts")
        used_sources.add(row["date_source_key"])
    if coordinates[0]:
        require(
            row,
            ["coordinate_precision", "coordinate_source_key", "coordinate_source_locator"],
            label,
        )
        latitude = number(row["latitude_deg"], f"{label} latitude")
        longitude = number(row["longitude_deg"], f"{label} longitude")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"{label} has coordinates outside valid bounds")
        used_sources.add(row["coordinate_source_key"])
    keys = {key for key in row["source_keys"].split(";") if key}
    if not keys:
        raise ValueError(f"{label} has no source keys")
    used_sources.update(keys)

for group, roles in event_groups.items():
    if "dependent_episode" in roles and "event_candidate" not in roles:
        raise ValueError(f"event group {group} has a dependent episode without a candidate")

measurement_ids = [row["measurement_id"] for row in measurements]
if len(set(measurement_ids)) != len(measurement_ids):
    raise ValueError("measurements.csv has duplicate measurement_id values")

for row in measurements:
    label = f"measurement {row['measurement_id']}"
    require(
        row,
        ["measurement_id", "event_id", "quantity", "unit", "value_relation",
         "evidence_kind", "source_key", "source_locator"],
        label,
    )
    if row["event_id"] not in event_id_set:
        raise ValueError(f"{label} refers to unknown event {row['event_id']}")
    controlled(row["value_relation"], VALUE_RELATIONS, f"{label} value_relation")
    controlled(row["evidence_kind"], MEASUREMENT_EVIDENCE, f"{label} evidence_kind")
    controlled(row["uncertainty_type"], UNCERTAINTY_TYPES, f"{label} uncertainty_type")
    used_sources.add(row["source_key"])

    numeric = {}
    for field in ("value", "lower_bound", "upper_bound", "uncertainty"):
        if row[field]:
            numeric[field] = number(row[field], f"{label} {field}")
    if numeric.get("uncertainty", 0) < 0:
        raise ValueError(f"{label} has a negative uncertainty")
    if bool(row["uncertainty"]) != bool(row["uncertainty_type"]):
        raise ValueError(f"{label} must pair uncertainty with uncertainty_type")
    if row["confidence_level"] and row["uncertainty_type"] != "confidence_interval":
        raise ValueError(f"{label} gives confidence_level without confidence_interval")
    if row["uncertainty_type"] == "confidence_interval" and not row["confidence_level"]:
        raise ValueError(f"{label} gives a confidence_interval without confidence_level")
    if row["confidence_level"]:
        level = number(row["confidence_level"], f"{label} confidence_level")
        if not 0 < level < 1:
            raise ValueError(f"{label} confidence_level must be between zero and one")
    if row["observation_period"] and not re.fullmatch(r"\d{4}-\d{4}", row["observation_period"]):
        raise ValueError(f"{label} has an invalid observation_period")

    relation = row["value_relation"]
    present = {field for field in ("value", "lower_bound", "upper_bound") if row[field]}
    required_shape = {
        "equal": {"value"},
        "approximate": {"value"},
        "greater_than": {"lower_bound"},
        "lower_limit": {"lower_bound"},
        "upper_limit": {"upper_bound"},
        "range": {"lower_bound", "upper_bound"},
        "not_documented": set(),
    }[relation]
    if present != required_shape:
        raise ValueError(
            f"{label} relation {relation!r} requires {sorted(required_shape)}, "
            f"found {sorted(present)}"
        )
    if relation == "range" and numeric["lower_bound"] > numeric["upper_bound"]:
        raise ValueError(f"{label} has a reversed range")

claim_ids = [row["claim_id"] for row in claims]
if len(set(claim_ids)) != len(claim_ids):
    raise ValueError("claims.csv has duplicate claim_id values")

coverage = {event_id: set() for event_id in event_ids}
for row in claims:
    label = f"claim {row['claim_id']}"
    require(row, CLAIM_FIELDS, label)
    if row["event_id"] not in event_id_set:
        raise ValueError(f"{label} refers to unknown event {row['event_id']}")
    controlled(row["claim_scope"], CLAIM_SCOPES, f"{label} claim_scope")
    controlled(row["evidence_kind"], CLAIM_EVIDENCE, f"{label} evidence_kind")
    controlled(row["evidence_strength"], EVIDENCE_STRENGTH, f"{label} evidence_strength")
    coverage[row["event_id"]].add(row["claim_scope"])
    used_sources.add(row["source_key"])

required_claim_scopes = {"process_chain", "immediate_trigger", "climate_preconditioning"}
for event_id, scopes in coverage.items():
    missing = required_claim_scopes - scopes
    if missing:
        raise ValueError(f"event {event_id} is missing claim scopes {sorted(missing)}")

unknown_sources = used_sources - bibliography_keys
if unknown_sources:
    raise ValueError(f"unknown bibliography keys: {sorted(unknown_sources)}")

search_ids = [row["search_id"] for row in discovery_searches]
if len(set(search_ids)) != len(search_ids):
    raise ValueError("discovery_searches.csv has duplicate search_id values")
for row in discovery_searches:
    label = f"discovery search {row['search_id']}"
    require(row, DISCOVERY_SEARCH_FIELDS, label)
    timestamp(row["executed_utc"], f"{label} executed_utc")
    start = calendar_date(row["date_start"], f"{label} date_start")
    end = calendar_date(row["date_end"], f"{label} date_end")
    if end < start:
        raise ValueError(f"{label} date range is reversed")
    if not row["resource_url"].startswith("https://"):
        raise ValueError(f"{label} resource_url must use HTTPS")
    controlled(row["climate_blind_check"], {"pass"}, f"{label} climate_blind_check")
    banned = re.compile(r"\b(climate|warming|permafrost|deglaciation|retreat)\b", re.I)
    if banned.search(row["query"]):
        raise ValueError(f"{label} query contains a causal exposure term")

for row in frame_flow:
    label = f"frame {row['frame_id']}"
    require(row, FRAME_FLOW_FIELDS, label)
    if not row["source_url"].startswith("https://"):
        raise ValueError(f"{label} source_url must use HTTPS")
    counts = [int(number(row[field], f"{label} {field}")) for field in
              FRAME_FLOW_FIELDS[2:-1]]
    if counts[1:] != sorted(counts[1:], reverse=True):
        raise ValueError(f"{label} downloaded-frame counts must narrow monotonically")

candidate_ids = [row["candidate_id"] for row in candidates]
if len(set(candidate_ids)) != len(candidate_ids):
    raise ValueError("candidates.csv has duplicate candidate_id values")
candidate_groups = {}
for row in candidates:
    label = f"candidate {row['candidate_id']}"
    require(
        row,
        ["candidate_id", "event_group_id", "event_name", "date_start",
         "date_precision", "location", "country", "setting", "initial_failure",
         "threshold_quantity", "threshold_relation", "threshold_unit",
         "discovery_source", "discovery_record", "primary_source_url",
         "primary_source_locator", "screen_1_reviewer", "screen_1_decision",
         "screen_1_reason", "screen_2_reviewer", "screen_2_decision",
         "screen_2_reason", "consensus_decision", "consensus_reason",
         "analysis_role", "trigger_time_eligible", "notes"],
        label,
    )
    controlled(row["date_precision"], CANDIDATE_DATE_PRECISION,
               f"{label} date_precision")
    controlled(row["setting"], CANDIDATE_SETTINGS, f"{label} setting")
    controlled(row["initial_failure"], CANDIDATE_FAILURES,
               f"{label} initial_failure")
    controlled(row["threshold_quantity"], set(THRESHOLDS),
               f"{label} threshold_quantity")
    controlled(row["threshold_relation"], VALUE_RELATIONS,
               f"{label} threshold_relation")
    if (row["threshold_quantity"] == "not_documented") != (
            row["threshold_relation"] == "not_documented"):
        raise ValueError(f"{label} must pair undocumented quantity and relation")
    expected_threshold, expected_unit = THRESHOLDS[row["threshold_quantity"]]
    if row["threshold_unit"] != expected_unit:
        raise ValueError(f"{label} has unit inconsistent with its threshold")

    start = calendar_date(row["date_start"], f"{label} date_start")
    end = (calendar_date(row["date_end"], f"{label} date_end")
           if row["date_end"] else start)
    if end < start:
        raise ValueError(f"{label} date range is reversed")
    coordinates = bool(row["latitude_deg"]), bool(row["longitude_deg"])
    if coordinates[0] != coordinates[1]:
        raise ValueError(f"{label} must provide both latitude and longitude")
    if coordinates[0]:
        latitude = number(row["latitude_deg"], f"{label} latitude")
        longitude = number(row["longitude_deg"], f"{label} longitude")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"{label} has coordinates outside valid bounds")

    numeric = {}
    for field in ("threshold_value", "threshold_lower_bound", "threshold_upper_bound"):
        if row[field]:
            numeric[field] = number(row[field], f"{label} {field}")
    present = {field for field in numeric}
    required_shape = {
        "equal": {"threshold_value"},
        "approximate": {"threshold_value"},
        "greater_than": {"threshold_lower_bound"},
        "lower_limit": {"threshold_lower_bound"},
        "upper_limit": {"threshold_upper_bound"},
        "range": {"threshold_lower_bound", "threshold_upper_bound"},
        "not_documented": set(),
    }[row["threshold_relation"]]
    if present != required_shape:
        raise ValueError(
            f"{label} relation {row['threshold_relation']!r} requires "
            f"{sorted(required_shape)}, found {sorted(present)}"
        )
    if row["threshold_relation"] == "range" and (
            numeric["threshold_lower_bound"] > numeric["threshold_upper_bound"]):
        raise ValueError(f"{label} has a reversed threshold range")

    for prefix in ("screen_1", "screen_2"):
        controlled(row[f"{prefix}_decision"], SCREEN_DECISIONS,
                   f"{label} {prefix}_decision")
        controlled(row[f"{prefix}_reason"], SCREEN_REASONS,
                   f"{label} {prefix}_reason")
    if row["screen_1_reviewer"] == row["screen_2_reviewer"]:
        raise ValueError(f"{label} requires two differently named reviewers")
    controlled(row["consensus_decision"], SCREEN_DECISIONS,
               f"{label} consensus_decision")
    controlled(row["consensus_reason"], SCREEN_REASONS,
               f"{label} consensus_reason")
    controlled(row["analysis_role"], CANDIDATE_ROLES, f"{label} analysis_role")
    controlled(row["trigger_time_eligible"],
               {"yes", "no", "not_assigned", "not_applicable"},
               f"{label} trigger_time_eligible")
    decision = row["consensus_decision"]
    if row["analysis_role"] not in DECISION_ROLE[decision]:
        raise ValueError(f"{label} has a role inconsistent with its decision")
    if row["trigger_time_eligible"] not in DECISION_TRIGGER[decision]:
        raise ValueError(f"{label} has trigger eligibility inconsistent with its decision")
    if decision == "include":
        conservative_value = {
            "equal": numeric.get("threshold_value"),
            "approximate": numeric.get("threshold_value"),
            "greater_than": numeric.get("threshold_lower_bound"),
            "lower_limit": numeric.get("threshold_lower_bound"),
            "range": numeric.get("threshold_lower_bound"),
            "upper_limit": None,
            "not_documented": None,
        }[row["threshold_relation"]]
        if conservative_value is None or conservative_value < expected_threshold:
            raise ValueError(f"{label} does not conservatively pass its threshold")
        if not datetime(2000, 1, 1) <= start <= datetime(2026, 8, 30):
            raise ValueError(f"{label} is outside the registered occurrence window")
        if row["trigger_time_eligible"] == "yes" and row["date_precision"] in {
                "satellite_interval", "month", "year"}:
            raise ValueError(f"{label} is too imprecise for trigger-time analysis")
        if row["setting"] not in {"high_mountain", "fjord", "alpine_lake",
                                  "proglacial_lagoon"}:
            raise ValueError(f"{label} has an ineligible setting")
        if row["initial_failure"] not in {
                "rock_avalanche", "rockslide", "rock_ice_avalanche",
                "glacier_detachment", "glacier_collapse", "ice_rock_avalanche"}:
            raise ValueError(f"{label} has an ineligible material or process")
    if not row["primary_source_url"].startswith("https://"):
        raise ValueError(f"{label} primary_source_url must use HTTPS")
    candidate_groups.setdefault(row["event_group_id"], set()).add(row["analysis_role"])

for group, roles in candidate_groups.items():
    if "dependent_episode" in roles and "event_candidate" not in roles:
        raise ValueError(f"candidate group {group} has a dependent episode without a candidate")

role_counts = {
    role: sum(row["analysis_role"] == role for row in events)
    for role in sorted(ANALYSIS_ROLES)
}
print(
    f"catalog valid: {len(events)} records {role_counts}, "
    f"{len(measurements)} measurements, {len(claims)} claims, "
    f"{len(used_sources)} cited sources, {len(discovery_searches)} discovery searches, "
    f"{len(frame_flow)} enumerated frames, "
    f"{len(candidates)} screened candidates"
)

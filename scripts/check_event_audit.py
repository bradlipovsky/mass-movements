#!/usr/bin/env python3
"""Validate the registered source-coordinate and onset-time audit."""

import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "event_audit"
FREEZE = "35d392944fef43aeb4084e023bc1fa9470728fab"
AUDIT_PROTOCOL = "46ef8acac00348d6e09b07763eed16de93797670"
FILES = {
    "summary": DATA / "summary.csv",
    "coordinates": DATA / "coordinate_assertions.csv",
    "times": DATA / "time_assertions.csv",
    "sources": DATA / "sources.csv",
}
STATUSES = {"accepted", "conflict", "unresolved"}
REASONS = {
    "not_reported", "source_inaccessible", "geometry_ambiguous",
    "time_basis_unknown", "pulse_allocation_unknown",
    "conflicting_primary_sources",
}
GEOMETRY_ROLES = {
    "initiating_source", "source_area_centroid", "deposit", "impact",
    "named_feature", "regional", "unspecified", "not_reported",
}
ACCEPTED_GEOMETRIES = {"initiating_source", "source_area_centroid"}
METHODS = {
    "published_numeric", "authoritative_gazetteer", "figure_digitized",
    "not_available",
}
UNCERTAINTY = {"le_100_m", "le_1_km", "le_5_km", "gt_5_km_or_unknown"}
REVIEWS = {"pending", "agree", "disagree"}
TIME_BASES = {"utc", "civil_offset", "civil_zone", "trigger_origin", "unknown"}
PRECISIONS = {"second", "minute", "hour", "day", "range"}
SOURCE_TYPES = {"primary", "authoritative", "structured_inventory", "secondary"}
ACCESS_STATES = {"public", "metadata_only", "source_inaccessible"}


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_utc(value):
    if value.endswith("Z"):
        value = value[:-1]
    elif value.endswith("+00:00"):
        value = value[:-6]
    else:
        raise ValueError("timestamp must have an explicit UTC offset")
    return parse_local(value).replace(tzinfo=timezone.utc)


def parse_local(value):
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    raise ValueError("reported local bound must be a timezone-naive ISO timestamp")


def converted_utc(local_value, offset_minutes):
    return (parse_local(local_value) - timedelta(minutes=int(offset_minutes))).replace(tzinfo=timezone.utc)


def intervals_overlap(lower_a, upper_a, lower_b, upper_b):
    return max(parse_utc(lower_a), parse_utc(lower_b)) < min(parse_utc(upper_a), parse_utc(upper_b))


def uncertainty_class(metres):
    metres = float(metres)
    if metres <= 100:
        return "le_100_m"
    if metres <= 1000:
        return "le_1_km"
    if metres <= 5000:
        return "le_5_km"
    return "gt_5_km_or_unknown"


def selected_candidates():
    rows = read_csv(ROOT / "data" / "candidates.csv")
    return {
        row["candidate_id"]: row for row in rows
        if row["consensus_decision"] == "include"
        and row["trigger_time_eligible"] == "yes"
    }


def require_vocab(errors, row, field, allowed, label):
    if row[field] not in allowed:
        errors.append(f"{label}: invalid {field}={row[field]!r}")


def validate_rows():
    errors = []
    candidates = selected_candidates()
    summary = read_csv(FILES["summary"])
    coordinates = read_csv(FILES["coordinates"])
    times = read_csv(FILES["times"])
    sources = read_csv(FILES["sources"])
    if len(candidates) != 53:
        errors.append(f"frozen selector returned {len(candidates)}, expected 53")

    def unique(rows, field, label):
        values = [row[field] for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"duplicate {label}")
        return {row[field]: row for row in rows}

    summaries = unique(summary, "candidate_id", "summary candidate_id")
    coordinate_by_id = unique(coordinates, "assertion_id", "coordinate assertion_id")
    time_by_id = unique(times, "assertion_id", "time assertion_id")
    source_by_id = unique(sources, "source_id", "source_id")
    if set(summaries) != set(candidates):
        missing = sorted(set(candidates) - set(summaries))
        extra = sorted(set(summaries) - set(candidates))
        errors.append(f"summary key mismatch: missing={missing}, extra={extra}")

    original_fields = [
        "latitude_deg", "longitude_deg", "date_start", "date_end",
        "date_precision",
    ]
    for candidate_id, row in summaries.items():
        if candidate_id not in candidates:
            continue
        catalog = candidates[candidate_id]
        for field in original_fields:
            if row[f"original_{field}"] != catalog[field]:
                errors.append(f"{candidate_id}: original_{field} changed")
        for prefix in ("coordinate", "time"):
            require_vocab(errors, row, f"{prefix}_status", STATUSES, candidate_id)
            status = row[f"{prefix}_status"]
            reason = row[f"{prefix}_unresolved_reason"]
            if status == "accepted" and reason:
                errors.append(f"{candidate_id}: accepted {prefix} has unresolved reason")
            if status != "accepted" and reason not in REASONS:
                errors.append(f"{candidate_id}: {prefix} lacks controlled unresolved reason")
        if row["coordinate_status"] == "accepted":
            try:
                lat, lon = float(row["audited_latitude_deg"]), float(row["audited_longitude_deg"])
                if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                    raise ValueError
            except ValueError:
                errors.append(f"{candidate_id}: invalid accepted coordinate")
            require_vocab(errors, row, "coordinate_uncertainty_class", UNCERTAINTY, candidate_id)
            assertion = coordinate_by_id.get(row["coordinate_assertion_id"])
            if not assertion or assertion["review_state"] != "agree":
                errors.append(f"{candidate_id}: accepted coordinate lacks agreed assertion")
            elif assertion["geometry_role"] not in ACCEPTED_GEOMETRIES:
                errors.append(f"{candidate_id}: accepted coordinate has wrong geometry role")
            elif (
                float(row["audited_latitude_deg"]) != float(assertion["latitude_deg"])
                or float(row["audited_longitude_deg"]) != float(assertion["longitude_deg"])
                or row["coordinate_uncertainty_class"] != assertion["horizontal_uncertainty_class"]
            ):
                errors.append(f"{candidate_id}: coordinate summary does not match assertion")
        if row["time_status"] == "accepted":
            try:
                if parse_utc(row["onset_lower_utc"]) >= parse_utc(row["onset_upper_utc"]):
                    raise ValueError
            except ValueError:
                errors.append(f"{candidate_id}: invalid accepted UTC interval")
            assertion = time_by_id.get(row["time_assertion_id"])
            if not assertion or assertion["review_state"] != "agree":
                errors.append(f"{candidate_id}: accepted time lacks agreed assertion")
            elif (
                row["onset_lower_utc"] != assertion["onset_lower_utc"]
                or row["onset_upper_utc"] != assertion["onset_upper_utc"]
            ):
                errors.append(f"{candidate_id}: time summary does not match assertion")

    for row in coordinates:
        label = row["assertion_id"]
        if row["candidate_id"] not in candidates:
            errors.append(f"{label}: unknown candidate")
        require_vocab(errors, row, "geometry_role", GEOMETRY_ROLES, label)
        require_vocab(errors, row, "evidence_method", METHODS, label)
        require_vocab(errors, row, "horizontal_uncertainty_class", UNCERTAINTY, label)
        require_vocab(errors, row, "review_state", REVIEWS, label)
        if row["source_id"] not in source_by_id:
            errors.append(f"{label}: unknown source_id")
        unavailable = row["geometry_role"] == "not_reported" or row["evidence_method"] == "not_available"
        if unavailable:
            if (
                row["geometry_role"] != "not_reported"
                or row["evidence_method"] != "not_available"
                or row["latitude_deg"] or row["longitude_deg"]
                or row["horizontal_uncertainty_class"] != "gt_5_km_or_unknown"
            ):
                errors.append(f"{label}: unavailable coordinate is not encoded consistently")
        else:
            try:
                lat, lon = float(row["latitude_deg"]), float(row["longitude_deg"])
                if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                    raise ValueError
            except ValueError:
                errors.append(f"{label}: invalid coordinate")
        if row["horizontal_uncertainty_m"]:
            try:
                if float(row["horizontal_uncertainty_m"]) < 0:
                    raise ValueError
                if uncertainty_class(row["horizontal_uncertainty_m"]) != row["horizontal_uncertainty_class"]:
                    errors.append(f"{label}: numeric uncertainty disagrees with class")
            except ValueError:
                errors.append(f"{label}: invalid horizontal uncertainty")
        if not row["source_locator"]:
            errors.append(f"{label}: missing exact source locator")
        if row["review_state"] == "agree" and (
            not row["verifier"] or row["verifier"] == row["extractor"]
        ):
            errors.append(f"{label}: agreement is not independently verified")

    for row in times:
        label = row["assertion_id"]
        if row["candidate_id"] not in candidates:
            errors.append(f"{label}: unknown candidate")
        require_vocab(errors, row, "time_basis", TIME_BASES, label)
        require_vocab(errors, row, "precision", PRECISIONS, label)
        require_vocab(errors, row, "review_state", REVIEWS, label)
        if row["source_id"] not in source_by_id:
            errors.append(f"{label}: unknown source_id")
        conversion_fields = [
            "reported_lower", "reported_upper", "utc_offset_lower_minutes",
            "utc_offset_upper_minutes", "onset_lower_utc", "onset_upper_utc",
        ]
        if row["time_basis"] == "unknown":
            if any(row[field] for field in conversion_fields):
                errors.append(f"{label}: unknown time basis has invented conversion")
        else:
            try:
                lower, upper = parse_utc(row["onset_lower_utc"]), parse_utc(row["onset_upper_utc"])
                if lower >= upper:
                    raise ValueError
                expected_lower = converted_utc(row["reported_lower"], row["utc_offset_lower_minutes"])
                expected_upper = converted_utc(row["reported_upper"], row["utc_offset_upper_minutes"])
                if lower != expected_lower or upper != expected_upper:
                    errors.append(f"{label}: UTC conversion does not match recorded offset")
                duration = (upper - lower).total_seconds()
                fixed = {"second": 1, "minute": 60, "hour": 3600}
                if row["precision"] in fixed and duration != fixed[row["precision"]]:
                    errors.append(f"{label}: interval does not match stated precision")
            except (ValueError, TypeError):
                errors.append(f"{label}: invalid time interval or conversion")
        if row["review_state"] == "agree" and (
            not row["verifier"] or row["verifier"] == row["extractor"]
        ):
            errors.append(f"{label}: agreement is not independently verified")
        if not row["source_locator"]:
            errors.append(f"{label}: missing exact source locator")

    for row in sources:
        label = row["source_id"]
        require_vocab(errors, row, "source_type", SOURCE_TYPES, label)
        require_vocab(errors, row, "access_state", ACCESS_STATES, label)
        if row["access_state"] == "public" and not row["url"]:
            errors.append(f"{label}: public source lacks URL")
        if row["sha256"] and (len(row["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in row["sha256"])):
            errors.append(f"{label}: invalid sha256")
    return errors, summary, coordinates, times, sources


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(errors):
    path = DATA / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["discovery_freeze_commit"] != FREEZE:
        errors.append("manifest discovery freeze commit changed")
    if manifest["audit_protocol_commit"] != AUDIT_PROTOCOL:
        errors.append("manifest audit protocol commit changed")
    for name, file_path in FILES.items():
        expected = manifest.get("files", {}).get(str(file_path.relative_to(ROOT)))
        if expected != file_sha256(file_path):
            errors.append(f"manifest hash mismatch: {name}")
    for relative, expected in manifest.get("inputs", {}).items():
        if expected != file_sha256(ROOT / relative):
            errors.append(f"manifest input hash mismatch: {relative}")


def main():
    errors, summary, coordinates, times, sources = validate_rows()
    validate_manifest(errors)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    accepted_coordinates = sum(row["coordinate_status"] == "accepted" for row in summary)
    accepted_times = sum(row["time_status"] == "accepted" for row in summary)
    print(
        f"event audit valid: {len(summary)} events; "
        f"{accepted_coordinates} accepted coordinates, {accepted_times} accepted UTC intervals; "
        f"{len(coordinates)} coordinate and {len(times)} time assertions; {len(sources)} sources"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

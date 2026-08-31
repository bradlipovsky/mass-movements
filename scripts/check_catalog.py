"""Check catalog links and controlled vocabulary using the standard library."""

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read_csv(name):
    with (DATA / name).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"{name} is empty")
    if any(None in row for row in rows):
        raise ValueError(f"{name} has a row with too many columns")
    return rows


events = read_csv("events.csv")
measurements = read_csv("measurements.csv")
claims = read_csv("claims.csv")

event_ids = {row["event_id"] for row in events}
if len(event_ids) != len(events):
    raise ValueError("events.csv has duplicate event_id values")

bibliography = (ROOT / "latex" / "references.bib").read_text(encoding="utf-8")
source_keys = set(re.findall(r"@\w+\{([^,]+),", bibliography))

used_sources = set()
for event in events:
    keys = set(event["source_keys"].split(";"))
    used_sources.update(keys)

for table, rows in (("measurements", measurements), ("claims", claims)):
    ids = [row[f"{table[:-1]}_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{table}.csv has duplicate identifiers")
    for row in rows:
        if row["event_id"] not in event_ids:
            raise ValueError(f"{table}.csv refers to unknown event {row['event_id']}")
        used_sources.add(row["source_key"])

unknown_sources = used_sources - source_keys
if unknown_sources:
    raise ValueError(f"unknown bibliography keys: {sorted(unknown_sources)}")

allowed_strength = {"direct", "strong", "moderate", "weak", "unresolved"}
found_strength = {row["evidence_strength"] for row in claims}
if not found_strength <= allowed_strength:
    raise ValueError(f"unknown evidence strengths: {sorted(found_strength - allowed_strength)}")

print(
    f"catalog valid: {len(events)} events, {len(measurements)} measurements, "
    f"{len(claims)} claims, {len(used_sources)} cited sources"
)

#!/usr/bin/env python3
"""Audit Copernicus DEM object metadata without opening raster payloads."""
import argparse, csv, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/global_dem_support"
FRAME = ROOT / "data/geographic_sample/frame.csv"
SAMPLE = ROOT / "data/geographic_sample/sample.csv"
HASHES = {
    "data/geographic_sample/frame.csv": "482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879",
    "data/geographic_sample/sample.csv": "1e9164813893e285aeeeaa1a7833e16c87172cbe4d3357e245854ab13966613b",
}
INSTANCES = {
    "glo30": {"code": "10", "bucket": "copernicus-dem-30m"},
    "glo90": {"code": "30", "bucket": "copernicus-dem-90m"},
}
KEY = re.compile(r"^(Copernicus_DSM_COG_(10|30)_[NS]\d{2}_00_[EW]\d{3}_00_DEM)/\1\.tif$")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs():
    for name, expected in HASHES.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"frozen input differs: {name}")


def verify_manifest(path):
    verify_inputs()
    for name, expected in json.loads(Path(path).read_text())["files"].items():
        item = ROOT / name
        if (item.stat().st_size, digest(item)) != (expected["bytes"], expected["sha256"]):
            raise ValueError(f"pre-access file differs: {name}")


def normalize_longitude(value):
    return (int(value) + 180) % 360 - 180


def stem(instance, latitude, longitude):
    latitude, longitude = int(latitude), normalize_longitude(longitude)
    lat = f"S{-latitude:02d}" if latitude < 0 else f"N{latitude:02d}"
    lon = f"W{-longitude:03d}" if longitude < 0 else f"E{longitude:03d}"
    return f"Copernicus_DSM_COG_{INSTANCES[instance]['code']}_{lat}_00_{lon}_00_DEM"


def expected_rows():
    verify_inputs(); rows = []
    frame = pd.read_csv(FRAME, dtype={"dominant_region": str})
    for cell in frame.itertuples(index=False):
        longitudes = sorted({normalize_longitude(x) for x in range(cell.west - 1, cell.west + 2)})
        for instance in INSTANCES:
            for latitude in range(cell.south - 1, cell.south + 2):
                for longitude in longitudes:
                    object_id = stem(instance, latitude, longitude)
                    rows.append({"cell_key": cell.cell_key, "south": cell.south, "west": cell.west,
                                 "dominant_region": cell.dominant_region, "instance": instance,
                                 "role": "core" if (latitude, longitude) == (cell.south, cell.west) else "halo",
                                 "latitude": latitude, "longitude": longitude, "object_id": object_id,
                                 "key": f"{object_id}/{object_id}.tif"})
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def parse_listing(body, instance):
    root = ElementTree.fromstring(body); namespace = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
    rows = []
    for item in root.findall(f"{namespace}Contents"):
        key = item.findtext(f"{namespace}Key"); match = KEY.fullmatch(key or "")
        if not match or match.group(2) != INSTANCES[instance]["code"]:
            continue
        rows.append({"instance": instance, "object_id": match.group(1), "key": key,
                     "bytes": int(item.findtext(f"{namespace}Size")),
                     "etag": (item.findtext(f"{namespace}ETag") or "").strip('"'),
                     "last_modified": item.findtext(f"{namespace}LastModified") or ""})
    truncated = root.findtext(f"{namespace}IsTruncated") == "true"
    return rows, truncated, root.findtext(f"{namespace}NextContinuationToken")


def inventory_url(instance, token=None):
    info = INSTANCES[instance]
    query = {"list-type": 2, "max-keys": 1000, "prefix": f"Copernicus_DSM_COG_{info['code']}_"}
    if token: query["continuation-token"] = token
    return f"https://{info['bucket']}.s3.amazonaws.com/?{urlencode(query)}"


def fetch_inventory(instance):
    raw = OUTPUT / "source_raw" / instance; raw.mkdir(parents=True, exist_ok=True)
    rows, pages, token, seen = [], [], None, set()
    while True:
        url = inventory_url(instance, token)
        with urlopen(url, timeout=120) as response:
            if response.status != 200: raise ValueError(f"listing status {response.status}")
            body = response.read()
        page_rows, truncated, next_token = parse_listing(body, instance)
        path = raw / f"page_{len(pages)+1:04d}.xml"; path.write_bytes(body)
        pages.append({"instance": instance, "page": len(pages)+1, "url": url,
                      "retrieved_utc": datetime.now(timezone.utc).isoformat(), "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(), "is_truncated": truncated,
                      "next_continuation_token": next_token or ""})
        rows.extend(page_rows)
        if not truncated: break
        if not next_token or next_token in seen: raise ValueError("invalid continuation token")
        seen.add(next_token); token = next_token
    if len({row["key"] for row in rows}) != len(rows): raise ValueError("duplicate exact DEM key")
    return rows, pages


def support_tables(expected, inventory):
    present = set(zip(inventory.instance, inventory.object_id)); selected = set(pd.read_csv(SAMPLE).cell_key)
    table = expected.copy(); table["present"] = [pair in present for pair in zip(table.instance, table.object_id)]
    rows = []
    for (cell_key, instance), group in table.groupby(["cell_key", "instance"], sort=False):
        absent = sorted(group.loc[~group.present, "object_id"])
        first = group.iloc[0]; core = group.loc[group.role == "core", "present"]
        rows.append({"cell_key": cell_key, "south": int(first.south), "west": int(first.west),
                     "dominant_region": first.dominant_region, "latitude_band_south": int(first.south // 10 * 10),
                     "instance": instance, "required_object_count": len(group),
                     "present_object_count": int(group.present.sum()), "absent_object_count": len(absent),
                     "absent_object_ids": json.dumps(absent, separators=(",", ":")),
                     "core_object_present": bool(core.iloc[0]), "full_halo_object_support": not absent,
                     "selected_annotation": cell_key in selected})
    cells = pd.DataFrame(rows)
    groups = []
    for dimension, column in (("region", "dominant_region"), ("latitude", "latitude_band_south")):
        for (instance, group), values in cells.groupby(["instance", column], sort=True):
            groups.append({"dimension": dimension, "group": group, "instance": instance,
                           "population_cells": len(values), "core_object_present_cells": int(values.core_object_present.sum()),
                           "full_halo_object_support_cells": int(values.full_halo_object_support.sum())})
    return cells, pd.DataFrame(groups)


def acquire(manifest):
    verify_manifest(manifest); expected = pd.read_csv(OUTPUT / "expected_objects.csv", dtype={"dominant_region": str})
    inventory, pages = [], []
    for instance in INSTANCES:
        found, ledger = fetch_inventory(instance); inventory.extend(found); pages.extend(ledger)
    write_csv(OUTPUT / "object_inventory.csv", inventory)
    (OUTPUT / "inventory_pages.json").write_text(json.dumps(pages, indent=2) + "\n")
    cells, groups = support_tables(expected, pd.DataFrame(inventory))
    cells.to_csv(OUTPUT / "cell_support.csv", index=False, lineterminator="\n")
    groups.to_csv(OUTPUT / "group_support.csv", index=False, lineterminator="\n")
    summary = {instance: {"population_cells": len(part), "core_object_present_cells": int(part.core_object_present.sum()),
                          "full_halo_object_support_cells": int(part.full_halo_object_support.sum())}
               for instance, part in cells.groupby("instance", sort=True)}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["expected", "acquire"])
    parser.add_argument("--manifest", type=Path); args = parser.parse_args()
    if args.action == "expected": write_csv(OUTPUT / "expected_objects.csv", expected_rows())
    elif not args.manifest: raise ValueError("metadata acquisition requires a pre-access manifest")
    else: acquire(args.manifest)


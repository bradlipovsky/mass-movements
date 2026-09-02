#!/usr/bin/env python3
"""Freeze and acquire native GLO-90 sources without opening raster payloads."""
import argparse, csv, hashlib, importlib.metadata, json, platform
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "data/native_glo90_transfer"
WINDOWS, EXPECTED, SCHEMAS = OUT / "windows.csv", OUT / "expected_sources.csv", OUT / "output_schemas.json"
PRE, LEDGER, RAW_MANIFEST = OUT / "preaccess_manifest.json", OUT / "source_ledger.csv", OUT / "raw_source_manifest.json"
RAW = OUT / "source_raw"
REGISTERED = ["protocol/native-glo90-transfer.md", "requirements-denominator.txt", "requirements-native-glo90-transfer.txt", "scripts/native_glo90_transfer_source.py", "scripts/native_glo90_transfer.py", "tests/test_native_glo90_transfer.py",
 "scripts/denominator_pilot.py", "scripts/scale_explicit_steep_area.py", "scripts/scale_explicit_transfer.py", "scripts/susceptible_area_convergence.py",
 "data/native_glo90_transfer/windows.csv", "data/native_glo90_transfer/expected_sources.csv", "data/native_glo90_transfer/output_schemas.json"]
BASELINES = ["data/scale_explicit_steep_area/equivalent_area_long.csv", "data/scale_explicit_steep_area/diagnostics.csv", "data/scale_explicit_transfer/equivalent_area_long.csv", "data/scale_explicit_transfer/decisions.csv"]
IDENTITY = ["region", "window_key", "latitude", "longitude", "object_id", "key", "url"]
PACKAGES = ["affine", "numpy", "pandas", "rasterio", "scipy", "shapely", "pyproj"]
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):
    with Path(path).open(newline="") as handle: return list(csv.DictReader(handle))
def write_rows(path, records):
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(records)
    temporary.replace(path)
def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_text(json.dumps(value, indent=2) + "\n"); temporary.replace(path)
def environment(): return {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in PACKAGES}}
def schema_columns(name): return json.loads(SCHEMAS.read_text())[name]["columns"]
def normalize_longitude(value): return (int(value) + 180) % 360 - 180
def object_id(latitude, longitude):
    latitude, longitude = int(latitude), normalize_longitude(longitude)
    ns = f"S{-latitude:02d}" if latitude < 0 else f"N{latitude:02d}"; ew = f"W{-longitude:03d}" if longitude < 0 else f"E{longitude:03d}"
    return f"Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM"
def expected_records():
    records = []
    for window in rows(WINDOWS):
        south, west = int(window["south"]), int(window["west"]); longitudes = sorted({normalize_longitude(x) for x in range(west - 1, west + 2)})
        for latitude in range(south - 1, south + 2):
            for longitude in longitudes:
                identity = object_id(latitude, longitude); key = f"{identity}/{identity}.tif"
                records.append(dict(region=window["region"], window_key=window["window_key"], latitude=latitude,
                    longitude=longitude, object_id=identity, key=key, url=f"https://copernicus-dem-90m.s3.amazonaws.com/{key}"))
    if len(records) != 63 or len({x["object_id"] for x in records}) != 63: raise ValueError("expected 63 distinct requests")
    return records
def baseline_files():
    names = list(BASELINES)
    for window in rows(WINDOWS):
        family, region = window["source_family"], window["region"]
        names += [f"data/{family}/source/dem_{region}_p00_30m.tif", f"data/{family}/source/pzi_{region}.tif", f"data/{family}/source/rgi_{region}.geojson"]
    return names
def registered_files(): return REGISTERED + baseline_files()
def file_record(name): path = ROOT / name; return {"bytes": path.stat().st_size, "sha256": digest(path)}
def write_preaccess():
    expected = expected_records(); write_rows(EXPECTED, expected); names = registered_files()
    manifest = {"status": "pre_native_glo90_access_v2", "issue": 27, "request_rows": 63, "environment": environment(), "schemas": json.loads(SCHEMAS.read_text()),
        "files": {name: file_record(name) for name in sorted(names)}}
    write_json(PRE, manifest)
def verify_preaccess(path, approved_sha256):
    if Path(path).resolve() != PRE.resolve() or digest(PRE) != approved_sha256: raise ValueError("unapproved pre-access manifest")
    manifest = json.loads(PRE.read_text()); expected = expected_records()
    fixed = (manifest.get("status"), manifest.get("issue"), manifest.get("request_rows"), manifest.get("environment"), manifest.get("schemas"))
    wanted = ("pre_native_glo90_access_v2", 27, 63, environment(), json.loads(SCHEMAS.read_text()))
    normalized = [{key: str(value) for key, value in item.items()} for item in expected]
    if fixed != wanted or set(manifest.get("files", {})) != set(registered_files()) or rows(EXPECTED) != normalized: raise ValueError("invalid pre-access closure")
    if any(file_record(name) != record for name, record in manifest["files"].items()): raise ValueError("frozen file differs")
def validate_ledger(records, expected, complete=False):
    schema = schema_columns("source_ledger"); names = [x["name"] for x in schema]
    if any(list(record) != names for record in records): raise ValueError("ledger schema differs")
    if len(records) > 63 or len({x.get("object_id") for x in records}) != len(records): raise ValueError("duplicate or excess ledger rows")
    left = [[str(x.get(key, "")) for key in IDENTITY] for x in records]; right = [[str(x[key]) for key in IDENTITY] for x in expected[:len(records)]]
    if left != right or (complete and len(records) != 63): raise ValueError("ledger is not the exact ordered expected population")
    for record in records:
        for column in (x["name"] for x in schema if x["dtype"] == "int64"): int(record[column])
        stamp = datetime.fromisoformat(record["retrieved_utc"])
        if stamp.tzinfo is None or len(record["sha256"]) != 64 or any(character not in "0123456789abcdef" for character in record["sha256"]) or int(record["bytes"]) < 0 or (record["content_length"] and int(record["content_length"]) != int(record["bytes"])): raise ValueError("invalid response metadata")
        status = int(record["http_status"])
        if status not in (200, 404): raise ValueError(f"retained unexpected HTTP status: {record['object_id']}")
        suffix = ".tif" if status == 200 else ".http404"
        if record["path"] != f"source_raw/{record['object_id']}{suffix}": raise ValueError("noncanonical response path")
def save_ledger(records): write_rows(LEDGER, records)
def acquire(manifest, approved_sha256):
    verify_preaccess(manifest, approved_sha256); RAW.mkdir(parents=True, exist_ok=True); expected = rows(EXPECTED)
    acquired = rows(LEDGER) if LEDGER.exists() else []; validate_ledger(acquired, expected)
    for record in acquired:
        path = OUT / record["path"]
        if (path.stat().st_size, digest(path)) != (int(record["bytes"]), record["sha256"]): raise ValueError(f"retained response differs: {record['object_id']}")
    for item in expected[len(acquired):]:
        try:
            response = urlopen(Request(item["url"], headers={"User-Agent": "mass-movements-issue-27"}), timeout=240)
            status, body, headers = response.status, response.read(), response.headers; response.close()
        except HTTPError as error: status, body, headers = error.code, error.read(), error.headers
        suffix = ".tif" if status == 200 else f".http{status}"; path = RAW / f"{item['object_id']}{suffix}"; path.write_bytes(body)
        record = dict(item, retrieved_utc=datetime.now(timezone.utc).isoformat(), http_status=status,
            path=str(path.relative_to(OUT)), bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
            etag=headers.get("ETag", "").strip('"'), last_modified=headers.get("Last-Modified", ""),
            content_type=headers.get("Content-Type", ""), content_length=headers.get("Content-Length", ""))
        acquired.append(record); save_ledger(acquired)
        if status not in (200, 404): raise ValueError(f"unexpected HTTP status {status}: {item['object_id']}")
    validate_ledger(acquired, expected, complete=True); names = [str(LEDGER.relative_to(ROOT))] + [str((OUT / x["path"]).relative_to(ROOT)) for x in acquired]
    manifest = {"status": "raw_native_glo90_sources_sealed_unopened_v2", "preaccess_manifest_sha256": digest(PRE),
        "expected_sources_sha256": digest(EXPECTED), "responses": 63,
        "http_status_counts": {str(code): sum(int(x["http_status"]) == code for x in acquired) for code in (200, 404)},
        "files": {name: file_record(name) for name in sorted(names)}}
    write_json(RAW_MANIFEST, manifest)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["freeze", "acquire"]); parser.add_argument("--manifest", type=Path); parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    if args.action == "freeze": write_preaccess()
    elif not args.manifest or not args.manifest_sha256: raise ValueError("acquisition requires the approved pre-access path and SHA-256")
    else: acquire(args.manifest, args.manifest_sha256)

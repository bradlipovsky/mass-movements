#!/usr/bin/env python3
"""Freeze and acquire native GLO-90 sources without opening raster payloads."""
import argparse, csv, hashlib, importlib.metadata, json, platform
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/native_glo90_transfer"
WINDOWS, EXPECTED = OUT / "windows.csv", OUT / "expected_sources.csv"
PRE, LEDGER, RAW_MANIFEST = OUT / "preaccess_manifest.json", OUT / "source_ledger.csv", OUT / "raw_source_manifest.json"
RAW = OUT / "source_raw"
REGISTERED = ["protocol/native-glo90-transfer.md", "requirements-denominator.txt",
              "scripts/native_glo90_transfer_source.py", "scripts/native_glo90_transfer.py",
              "tests/test_native_glo90_transfer.py", "data/native_glo90_transfer/windows.csv",
              "data/native_glo90_transfer/expected_sources.csv"]
BASELINES = ["data/scale_explicit_steep_area/equivalent_area_long.csv",
             "data/scale_explicit_steep_area/diagnostics.csv",
             "data/scale_explicit_transfer/equivalent_area_long.csv",
             "data/scale_explicit_transfer/decisions.csv"]


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    with Path(path).open(newline="") as source: return list(csv.DictReader(source))


def write_rows(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(records)


def normalize_longitude(value): return (int(value) + 180) % 360 - 180


def object_id(latitude, longitude):
    latitude, longitude = int(latitude), normalize_longitude(longitude)
    ns = f"S{-latitude:02d}" if latitude < 0 else f"N{latitude:02d}"
    ew = f"W{-longitude:03d}" if longitude < 0 else f"E{longitude:03d}"
    return f"Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM"


def expected_records():
    records = []
    for window in rows(WINDOWS):
        south, west = int(window["south"]), int(window["west"])
        longitudes = sorted({normalize_longitude(x) for x in range(west - 1, west + 2)})
        for latitude in range(south - 1, south + 2):
            for longitude in longitudes:
                identity = object_id(latitude, longitude); key = f"{identity}/{identity}.tif"
                records.append(dict(region=window["region"], window_key=window["window_key"],
                                    latitude=latitude, longitude=longitude, object_id=identity, key=key,
                                    url=f"https://copernicus-dem-90m.s3.amazonaws.com/{key}"))
    if len(records) != 63 or len({x["object_id"] for x in records}) != 63: raise ValueError("expected 63 distinct requests")
    return records


def baseline_files():
    names = list(BASELINES)
    for window in rows(WINDOWS):
        family, region = window["source_family"], window["region"]
        names += [f"data/{family}/source/dem_{region}_p00_30m.tif",
                  f"data/{family}/source/pzi_{region}.tif", f"data/{family}/source/rgi_{region}.geojson"]
    return names


def file_record(name):
    path = ROOT / name
    return {"bytes": path.stat().st_size, "sha256": digest(path)}


def write_preaccess():
    expected = expected_records(); write_rows(EXPECTED, expected)
    names = REGISTERED + baseline_files()
    manifest = {"status": "pre_native_glo90_access", "issue": 27, "request_rows": 63,
                "environment": {"python": platform.python_version(), **{p: importlib.metadata.version(p)
                for p in ["numpy", "pandas", "rasterio", "scipy", "shapely", "pyproj"]}},
                "schemas": {"equivalent_area_long_rows": 56, "comparison_rows": 14},
                "files": {name: file_record(name) for name in sorted(names)}}
    PRE.write_text(json.dumps(manifest, indent=2) + "\n")


def verify_preaccess(path):
    if Path(path).resolve() != PRE.resolve(): raise ValueError("unapproved pre-access manifest path")
    manifest = json.loads(PRE.read_text())
    if manifest.get("status") != "pre_native_glo90_access" or set(manifest["files"]) != set(REGISTERED + baseline_files()):
        raise ValueError("invalid pre-access manifest")
    for name, expected in manifest["files"].items():
        item = ROOT / name
        if (item.stat().st_size, digest(item)) != (expected["bytes"], expected["sha256"]): raise ValueError(f"frozen file differs: {name}")


def save_ledger(records): write_rows(LEDGER, records)


def acquire(manifest):
    verify_preaccess(manifest); RAW.mkdir(parents=True, exist_ok=True)
    prior = {x["object_id"]: x for x in rows(LEDGER)} if LEDGER.exists() else {}; acquired = []
    for expected in rows(EXPECTED):
        identity = expected["object_id"]
        if identity in prior:
            record = prior[identity]; path = OUT / record["path"]
            if (path.stat().st_size, digest(path), record["url"]) != (int(record["bytes"]), record["sha256"], expected["url"]):
                raise ValueError(f"retained response differs: {identity}")
            acquired.append(record); continue
        try:
            response = urlopen(Request(expected["url"], headers={"User-Agent": "mass-movements-issue-27"}), timeout=240)
            status, body, headers = response.status, response.read(), response.headers; response.close()
        except HTTPError as error: status, body, headers = error.code, error.read(), error.headers
        suffix = ".tif" if status == 200 else f".http{status}"
        path = RAW / f"{identity}{suffix}"; path.write_bytes(body)
        record = dict(expected, retrieved_utc=datetime.now(timezone.utc).isoformat(), http_status=status,
                      path=str(path.relative_to(OUT)), bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                      etag=headers.get("ETag", "").strip('"'), last_modified=headers.get("Last-Modified", ""),
                      content_type=headers.get("Content-Type", ""), content_length=headers.get("Content-Length", ""))
        acquired.append(record); save_ledger(acquired)
        if status not in (200, 404): raise ValueError(f"unexpected HTTP status {status}: {identity}")
    files = {str(LEDGER.relative_to(ROOT)): file_record(str(LEDGER.relative_to(ROOT)))}
    files.update({str((OUT / x["path"]).relative_to(ROOT)): file_record(str((OUT / x["path"]).relative_to(ROOT))) for x in acquired})
    RAW_MANIFEST.write_text(json.dumps({"status": "raw_native_glo90_sources_sealed_unopened",
        "preaccess_manifest_sha256": digest(PRE), "responses": len(acquired), "http_status_counts":
        {str(code): sum(int(x["http_status"]) == code for x in acquired) for code in (200, 404)},
        "files": dict(sorted(files.items()))}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["freeze", "acquire"]); parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.action == "freeze": write_preaccess()
    elif not args.manifest: raise ValueError("acquisition requires pre-access manifest")
    else: acquire(args.manifest)

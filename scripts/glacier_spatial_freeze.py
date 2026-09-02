#!/usr/bin/env python3
"""Freeze glacier ERA5 support and opaque IceBoost archive inventories."""
import csv, hashlib, json, math, os, platform, shutil, subprocess, sys, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import fiona
from pyproj import Geod
from shapely import box
from shapely.geometry import shape
from shapely.ops import orient, transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import glacier_matching_freeze as matching
import glacier_warming_steepness as gate

OUT = ROOT / "data" / "glacier_warming_steepness"
RGI_RAW = ROOT / "data" / "geographic_sample" / "source_raw" / "rgi"
ICEBOOST_RAW = OUT / "source_raw" / "iceboost"
PROGRAM = Path(__file__).resolve()
TESTS = ROOT / "tests" / "test_glacier_spatial_freeze.py"
REQUIREMENTS = ROOT / "requirements-glacier-spatial-freeze.txt"
SCHEMAS = ROOT / "protocol" / "glacier_spatial_freeze_output_schemas.json"
MATCHING_COMMIT = "95ee158e43fc8d755a999650fbf3cde7575f3945"
PREACCESS_SHA256 = "d4640d9079ed81ff9654a22590f5effa84b07355bdf58fa26712575056e73676"
ICEBOOST_MANIFEST_SHA256 = "6fcde5e0cf9a2d75f41746af15994b7592bb953488666f1e58e06c30913215ec"
RGI_MANIFEST_SHA256 = "6b411fc26af146c9dd0959490775e413aa97f57491cf6de6c91261e7e09e196b"
PROTOCOL_SHA256 = "e1104cdc0ed0aaa9275e62ad6aa7f33271dc5fdc8dc1130fcde7657fdc5dfb60"
EXPECTED_REGIONS = {"01", "13", "17"}
GEOD = Geod(ellps="WGS84")
FIELDS = {
    "glacier_era5_weights.csv": ["rgi_id", "latitude", "longitude", "intersection_area_m2", "weight"],
    "glacier_era5_weight_checks.csv": ["rgi_id", "polygon_area_m2", "intersected_area_m2", "planar_relative_closure_error", "geodesic_representation_difference", "weight_sum"],
    "spatial_dependence_ledger.csv": ["candidate_id", "initial_cluster", "final_cluster"],
    "dependence_merge_edges.csv": ["left_initial_cluster", "right_initial_cluster", "latitude", "longitude"],
    "iceboost_archive_members.csv": ["archive", "member", "archive_bytes", "archive_md5", "archive_sha256", "member_crc32", "member_bytes"],
}
TARGETS = tuple(FIELDS) + ("spatial_freeze_manifest.json",)

def sha256(path):
    return gate.sha256(path)

def csv_rows(path):
    with open(path, newline="") as stream: return list(csv.DictReader(stream))

def file_hashes(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            md5.update(block); sha.update(block)
    return md5.hexdigest(), sha.hexdigest()

def region_of(rgi_id):
    parts = rgi_id.split("-")
    if len(parts) < 2 or len(parts[-2]) != 2: raise ValueError(f"invalid RGI ID: {rgi_id}")
    return parts[-2]

def unwrap_geometry(geometry):
    if geometry.bounds[2] - geometry.bounds[0] < 180: return geometry
    def shift(x, y, z=None):
        try: shifted = tuple(value + 360 if value < 0 else value for value in x)
        except TypeError: shifted = x + 360 if x < 0 else x
        return (shifted, y) if z is None else (shifted, y, z)
    shifted = transform(shift, geometry)
    if shifted.geom_type == "MultiPolygon": shifted = unary_union(list(shifted.geoms))
    if (shifted.is_empty or not shifted.is_valid or shifted.geom_type not in ("Polygon", "MultiPolygon")
            or shifted.bounds[2] - shifted.bounds[0] >= 180):
        raise ValueError("geometry has no valid narrow longitude branch")
    return shifted

def participant_frame(case_rows, status_rows, selected_rows):
    primary = {row["candidate_id"] for row in case_rows if row["primary_case"] == "True"}
    status = {row["candidate_id"]: row for row in status_rows}
    cases = {case: status[case]["rgi_id"] for case in primary if status[case]["match_status"] == "matched"}
    controls = {case: [] for case in cases}
    for row in selected_rows:
        if row["candidate_id"] not in controls: raise ValueError("selected row lacks matched case")
        controls[row["candidate_id"]].append(row["rgi_id"])
    if len(primary) != 10 or set(cases) != primary or any(len(ids) != 20 for ids in controls.values()):
        raise ValueError("participant frame is not ten matched 1:20 sets")
    ids = set(cases.values()) | {rgi for values in controls.values() for rgi in values}
    if len(ids) != 207 or {region_of(value) for value in ids} != EXPECTED_REGIONS:
        raise ValueError("participant identities or regions drift")
    clusters = {case: status[case]["dependence_cluster"] for case in cases}
    return cases, controls, clusters, ids

def load_geometries(ids, source_manifest):
    geometries = {}
    records = {row["region"]: row for row in source_manifest["archives"]}
    for region in sorted(EXPECTED_REGIONS):
        record, wanted = records[region], {value for value in ids if region_of(value) == region}
        path = RGI_RAW / record["filename"]
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise ValueError(f"RGI geometry archive drift: {region}")
        with fiona.open("zip://" + str(path), include_fields=["rgi_id"]) as source:
            if source.crs.to_epsg() != 4326: raise ValueError(f"unexpected RGI CRS: {region}")
            for feature in source:
                if set(feature["properties"]) != {"rgi_id"}: raise ValueError("RGI projection exposed extra fields")
                rgi_id = feature["properties"]["rgi_id"]
                if rgi_id in wanted:
                    geometry = shape(feature["geometry"])
                    if rgi_id in geometries: raise ValueError(f"duplicate RGI geometry: {rgi_id}")
                    if not geometry.is_valid or geometry.geom_type not in ("Polygon", "MultiPolygon"):
                        raise ValueError(f"invalid or non-polygonal RGI geometry: {rgi_id}")
                    geometry = unwrap_geometry(geometry)
                    if geometry.is_empty:
                        raise ValueError(f"unsupported or empty geometry: {rgi_id}")
                    geometries[rgi_id] = geometry
    if set(geometries) != ids: raise ValueError(f"missing RGI geometries: {sorted(ids-set(geometries))}")
    return geometries

def geodesic_area(geometry):
    if geometry.is_empty: return 0.0
    if geometry.geom_type == "Polygon":
        return abs(GEOD.geometry_area_perimeter(orient(geometry, sign=1.0))[0])
    if geometry.geom_type not in ("MultiPolygon", "GeometryCollection"): return 0.0
    return sum(geodesic_area(part) for part in geometry.geoms)

def centers_between(low, high, minimum, maximum):
    first = math.ceil((low - .125) * 4 - 1e-12) / 4
    last = math.floor((high + .125) * 4 + 1e-12) / 4
    return [value / 4 for value in range(int(round(first * 4)), int(round(last * 4)) + 1)
            if minimum <= value / 4 <= maximum]

def geometry_weights(rgi_id, geometry):
    xmin, ymin, xmax, ymax = geometry.bounds
    if not all(math.isfinite(value) for value in (xmin, ymin, xmax, ymax, geometry.area)):
        raise ValueError(f"nonfinite geometry: {rgi_id}")
    areas, planar_areas = [], []
    for latitude in centers_between(ymin, ymax, -90, 90):
        for longitude in centers_between(xmin, xmax, -180, 360):
            cell = box(longitude - .125, max(-90, latitude - .125),
                       longitude + .125, min(90, latitude + .125))
            intersection = geometry.intersection(cell)
            area = geodesic_area(intersection)
            if not math.isfinite(area) or not math.isfinite(intersection.area):
                raise ValueError(f"nonfinite intersection: {rgi_id}")
            if area > 0:
                areas.append((latitude, longitude % 360, area)); planar_areas.append(intersection.area)
    total, full = sum(row[2] for row in areas), geodesic_area(geometry)
    planar_error = abs(sum(planar_areas) / geometry.area - 1) if geometry.area else float("inf")
    geodesic_difference = abs(total / full - 1) if full else float("inf")
    values = (total, full, planar_error, geodesic_difference)
    if not all(math.isfinite(value) for value in values) or not total or planar_error > 1e-12 or geodesic_difference > 1e-4:
        raise ValueError(f"ERA5 cells do not partition {rgi_id}")
    rows = [{"rgi_id": rgi_id, "latitude": f"{lat:.2f}", "longitude": f"{lon:.2f}",
             "intersection_area_m2": f"{area:.16g}", "weight": f"{area/total:.16g}"}
            for lat, lon, area in sorted(areas)]
    weight_sum = sum(float(row["weight"]) for row in rows)
    if not math.isfinite(weight_sum) or abs(weight_sum - 1) > 1e-12 or any(
            float(row["intersection_area_m2"]) <= 0 for row in rows):
        raise ValueError(f"serialized weights are invalid: {rgi_id}")
    check = {"rgi_id": rgi_id, "polygon_area_m2": f"{full:.16g}",
        "intersected_area_m2": f"{total:.16g}",
        "planar_relative_closure_error": f"{planar_error:.16g}",
        "geodesic_representation_difference": f"{geodesic_difference:.16g}",
        "weight_sum": f"{weight_sum:.16g}"}
    return rows, check

def dependence_tables(cases, controls, clusters, weights):
    cells = {}
    for row in weights: cells.setdefault(row["rgi_id"], set()).add((row["latitude"], row["longitude"]))
    support = {cluster: set() for cluster in set(clusters.values())}
    for case, case_rgi in cases.items():
        for rgi_id in [case_rgi] + controls[case]: support[clusters[case]].update(cells[rgi_id])
    parent = {cluster: cluster for cluster in support}
    def find(value):
        while parent[value] != value: parent[value] = parent[parent[value]]; value = parent[value]
        return value
    edges = []
    ordered = sorted(support)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            for latitude, longitude in sorted(support[left] & support[right]):
                edges.append({"left_initial_cluster": left, "right_initial_cluster": right,
                              "latitude": latitude, "longitude": longitude})
            if support[left] & support[right]: parent[find(right)] = find(left)
    components = {}
    for cluster in ordered: components.setdefault(find(cluster), []).append(cluster)
    final = {cluster: min(members) for members in components.values() for cluster in members}
    ledger = [{"candidate_id": case, "initial_cluster": clusters[case],
               "final_cluster": final[clusters[case]]} for case in sorted(cases)]
    return ledger, edges

def archive_inventory(metadata):
    rows, paths = [], []
    expected = {row["filename"] for row in metadata["archives"]
                if f"{int(row['region']):02d}" in EXPECTED_REGIONS}
    for record in metadata["archives"]:
        if f"{int(record['region']):02d}" not in EXPECTED_REGIONS: continue
        path = ICEBOOST_RAW / record["filename"]
        md5, sha = file_hashes(path)
        if path.stat().st_size != record["bytes"] or md5 != record["md5"]:
            raise ValueError(f"IceBoost archive drift: {path.name}")
        paths.append(path)
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len({member.filename for member in members}) != len(members):
                raise ValueError(f"duplicate IceBoost member: {path.name}")
            for member in members:
                member_path = PurePosixPath(member.filename)
                mode = member.external_attr >> 16
                if (member.flag_bits & 1 or member_path.is_absolute() or ".." in member_path.parts
                        or member.filename.startswith("\\") or mode & 0o170000 == 0o120000):
                    raise ValueError(f"unsafe IceBoost member: {member.filename}")
                rows.append({"archive": path.name, "member": member.filename,
                    "archive_bytes": record["bytes"], "archive_md5": md5, "archive_sha256": sha,
                    "member_crc32": f"{member.CRC:08x}", "member_bytes": member.file_size})
    if {path.name for path in paths} != expected: raise ValueError("IceBoost regions drift")
    return rows, paths

def input_paths(rgi_manifest, iceboost_paths):
    names = ["case_frame.csv", "case_glacier_status.csv", "selected_backgrounds.csv",
             "matching_summary.csv", "matching_pools.csv", "preaccess_manifest.json"]
    paths = [OUT / name for name in names] + [gate.PROTOCOL, gate.SCHEMAS, SCHEMAS, PROGRAM,
        Path(matching.__file__), Path(gate.__file__), TESTS, REQUIREMENTS,
        ROOT / "data/geographic_sample/source_manifest.json", OUT / "iceboost_source_manifest.json"]
    records = {row["region"]: row for row in rgi_manifest["archives"]}
    paths += [RGI_RAW / records[region]["filename"] for region in sorted(EXPECTED_REGIONS)]
    return paths + iceboost_paths

def freeze(output_dir=OUT):
    output_dir = Path(output_dir)
    existing = [name for name in TARGETS if (output_dir / name).exists()]
    if existing: raise FileExistsError(f"refusing to replace spatial freeze: {existing}")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT)).strip():
        raise ValueError("spatial freeze requires a clean worktree")
    if subprocess.call(["git", "merge-base", "--is-ancestor", MATCHING_COMMIT, "HEAD"], cwd=str(ROOT)):
        raise ValueError("matching artifact commit is not an ancestor")
    if sha256(gate.PROTOCOL) != PROTOCOL_SHA256 or sha256(OUT / "iceboost_source_manifest.json") != ICEBOOST_MANIFEST_SHA256:
        raise ValueError("protocol or IceBoost metadata drift")
    if sha256(ROOT / "data/geographic_sample/source_manifest.json") != RGI_MANIFEST_SHA256:
        raise ValueError("RGI source manifest drift")
    matching.verify_manifest(approved_sha256=PREACCESS_SHA256)
    rgi_manifest = json.loads((ROOT / "data/geographic_sample/source_manifest.json").read_text())
    iceboost_metadata = json.loads((OUT / "iceboost_source_manifest.json").read_text())
    cases, controls, clusters, ids = participant_frame(csv_rows(OUT / "case_frame.csv"),
        csv_rows(OUT / "case_glacier_status.csv"), csv_rows(OUT / "selected_backgrounds.csv"))
    geometries = load_geometries(ids, rgi_manifest)
    weight_sets = [geometry_weights(rgi_id, geometries[rgi_id]) for rgi_id in sorted(ids)]
    weights = [row for rows, check in weight_sets for row in rows]
    checks = [check for rows, check in weight_sets]
    ledger, edges = dependence_tables(cases, controls, clusters, weights)
    members, iceboost_paths = archive_inventory(iceboost_metadata)
    tables = dict(zip(FIELDS, (weights, checks, ledger, edges, members)))
    temporary = Path(tempfile.mkdtemp(prefix="spatial-freeze-", dir=output_dir)); published = []
    try:
        for name, fields in FIELDS.items(): gate.write_csv_atomic(temporary / name, fields, tables[name])
        paths = input_paths(rgi_manifest, iceboost_paths)
        manifest = {"status": "ERA5 support and opaque IceBoost central-directory declarations frozen; registered values unopened",
            "registration_url": "https://github.com/bradlipovsky/mass-movements/issues/33",
            "inventory_verified_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                universal_newlines=True).strip(), "python": sys.version, "platform": platform.platform(),
            "request_rows": 210, "rgi_ids": len(ids), "case_rgi_ids": len(set(cases.values())),
            "control_rgi_ids": len(ids-set(cases.values())), "weight_rows": len(weights),
            "unique_era5_cells": len({(row['latitude'], row['longitude']) for row in weights}),
            "initial_clusters": len(set(clusters.values())),
            "final_clusters": len({row['final_cluster'] for row in ledger}),
            "grid": "0.25 degree center-defined; longitude [0,360); latitude bounds clipped at poles",
            "planar_closure_tolerance": 1e-12, "geodesic_representation_tolerance": 1e-4,
            "weight_sum_tolerance": 1e-12,
            "iceboost_regions": sorted(EXPECTED_REGIONS), "iceboost_members": len(members),
            "inputs": {str(path.relative_to(ROOT)): {"bytes": path.stat().st_size,
                "sha256": sha256(path)} for path in paths},
            "outputs": {name: {"rows": len(tables[name]), "bytes": (temporary/name).stat().st_size,
                "sha256": sha256(temporary/name)} for name in FIELDS}}
        gate.write_json_atomic(temporary / "spatial_freeze_manifest.json", manifest)
        if [name for name in TARGETS if (output_dir/name).exists()]: raise FileExistsError("spatial target appeared")
        for name in TARGETS: os.link(str(temporary/name), str(output_dir/name)); published.append(output_dir/name)
    except Exception:
        for path in published: path.unlink()
        shutil.rmtree(temporary, ignore_errors=True); raise
    shutil.rmtree(temporary); return manifest

if __name__ == "__main__": print(json.dumps(freeze(), indent=2, sort_keys=True))

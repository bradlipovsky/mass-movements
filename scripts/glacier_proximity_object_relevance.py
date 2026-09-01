#!/usr/bin/env python3
"""Screen absent DEM delivery units against a conservative RGI geometry."""
import argparse, hashlib, json
from pathlib import Path
import fiona
import pandas as pd
import pyproj
import shapely
from pyproj import Transformer
from shapely import STRtree, box, force_2d, from_geojson, get_coordinates, make_valid, segmentize, union_all
from shapely.affinity import translate
from shapely.ops import transform
from shapely.validation import explain_validity
from scripts.denominator_pilot import local_crs, window_geometry
from scripts.geographic_sample import unwrap
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/glacier_proximity_object_relevance"
RGI_RAW = ROOT / "data/geographic_sample/source_raw/rgi"
FRAME = ROOT / "data/geographic_sample/frame.csv"
RGI_MANIFEST = ROOT / "data/geographic_sample/source_manifest.json"
EXPECTED = ROOT / "data/global_dem_support/expected_objects.csv"
INVENTORY = ROOT / "data/global_dem_support/object_inventory.csv"
ISSUE23 = ROOT / "data/global_dem_support/final_manifest.json"
PRE = OUTPUT / "pregeometry_manifest.json"
GEOMETRY = OUTPUT / "geometry_manifest.json"
ISSUE23_SHA = "a660e3eda35d4fa671e35c03e6c42f3dabad4c3393ca86cd07655d6a0b9d58d3"
PROXIMITY_M, SCREEN_M, QUAD_SEGS, REPAIR_TOL = 101, 1001, 32, 1e-8
PRE_FILES = {"protocol/glacier-proximity-object-relevance.md", "requirements-object-relevance.txt", "scripts/glacier_proximity_object_relevance.py",
             "tests/test_glacier_proximity_object_relevance.py", "data/geographic_sample/frame.csv", "data/geographic_sample/source_manifest.json",
             "data/global_dem_support/expected_objects.csv", "scripts/denominator_pilot.py", "scripts/geographic_sample.py"}
GEOMETRY_FILES = {"data/glacier_proximity_object_relevance/object_screen.csv", "data/glacier_proximity_object_relevance/projection_repairs.csv"}
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def runtime_versions(): return {"fiona": fiona.__version__, "pandas": pd.__version__, "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str,
            "shapely": shapely.__version__, "geos": shapely.geos_version_string}
def validate_file_set(data, status):
    expected = PRE_FILES if status == "pre_geometry" else GEOMETRY_FILES
    names = set(data.get("files", {}))
    if names != expected or any(Path(x).is_absolute() or ".." in Path(x).parts for x in names): raise ValueError("manifest file set differs")
def verify_manifest(path, status):
    canonical = PRE if status == "pre_geometry" else GEOMETRY
    if Path(path).resolve() != canonical.resolve():
        raise ValueError("manifest path differs")
    data = json.loads(canonical.read_text())
    if data.get("status") != status:
        raise ValueError("manifest status differs")
    validate_file_set(data, status)
    if status == "pre_geometry" and data.get("environment") != runtime_versions():
        raise ValueError("runtime environment differs")
    if status != "pre_geometry" and data.get("pregeometry_manifest_sha256") != digest(PRE):
        raise ValueError("geometry manifest predecessor differs")
    for name, item in data["files"].items():
        path = ROOT / name
        if (path.stat().st_size, digest(path)) != (item["bytes"], item["sha256"]):
            raise ValueError(f"frozen file differs: {name}")
    return data
def report_geometries(south, west):
    crs = local_crs(south, west)
    geographic, projected = window_geometry(south, west, crs)
    inverse = Transformer.from_crs(crs, 4326, always_xy=True).transform
    envelope = unwrap(transform(inverse, projected.buffer(1100, quad_segs=QUAD_SEGS)), west + .5)
    return crs, geographic, projected, envelope
def load_matches(frame):
    envelopes, owners = [], []
    for index, row in frame.iterrows():
        envelope = report_geometries(row.south, row.west)[3]
        for shift in (-360, 0, 360):
            envelopes.append(translate(envelope, xoff=shift))
            owners.append(index)
    tree, matches, seen = STRtree(envelopes), [[] for _ in range(len(frame))], set()
    source = json.loads(RGI_MANIFEST.read_text())
    if len(source.get("archives", [])) != 19:
        raise ValueError("expected 19 RGI archives")
    for item in source["archives"]:
        archive = RGI_RAW / item["filename"]
        if (archive.stat().st_size, digest(archive)) != (item["bytes"], item["sha256"]):
            raise ValueError("RGI archive differs")
        member = next(x["name"] for x in item["members"] if x["name"].endswith(".shp"))
        with fiona.open(f"zip://{archive}!{member}") as collection:
            if collection.crs.to_epsg() != 4326:
                raise ValueError("RGI source CRS differs")
            for feature in collection:
                properties = dict(feature["properties"])
                rgi_id = properties["rgi_id"]
                if rgi_id in seen or str(properties["o1region"]) != item["region"]:
                    raise ValueError(f"RGI identity differs: {rgi_id}")
                seen.add(rgi_id)
                geometry = force_2d(from_geojson(json.dumps(dict(feature["geometry"]))))
                if not geometry.is_valid:
                    raise ValueError(f"invalid source-WGS84 geometry: {rgi_id}")
                query = unwrap(geometry, float(get_coordinates(geometry)[0, 0]))
                for owner in {owners[int(k)] for k in tree.query(query, predicate="intersects")}:
                    matches[owner].append((rgi_id, geometry))
    if len(seen) != 274531 or any(not group for group in matches):
        raise ValueError("RGI population or cell match differs")
    return matches
def projected_union(items, crs, west, cell_key):
    forward = Transformer.from_crs(4326, crs, always_xy=True).transform
    projected, repairs = [], []
    for rgi_id, geometry in items:
        item = transform(forward, unwrap(geometry, west + .5))
        if not item.is_valid:
            before, reason = item.area, explain_validity(item)
            fixed = make_valid(item, method="linework")
            relative = abs(fixed.area - before) / before if before else float("inf")
            if fixed.geom_type not in ("Polygon", "MultiPolygon") or not fixed.is_valid or relative > REPAIR_TOL:
                raise ValueError(f"projection repair failed: {rgi_id}")
            repairs.append({"cell_key": cell_key, "rgi_id": rgi_id, "reason": reason,
                "input_type": item.geom_type, "output_type": fixed.geom_type,
                "projected_area_before_m2": before, "projected_area_after_m2": fixed.area,
                "relative_area_change": relative, "shapely_version": shapely.__version__,
                "geos_version": shapely.geos_version_string, "proj_version": pyproj.proj_version_str,
                "projected_crs_wkt": crs.to_wkt()})
            item = fixed
        projected.append(item)
    glacier = union_all(projected)
    if glacier.is_empty or not glacier.is_valid:
        raise ValueError(f"invalid projected union: {cell_key}")
    return glacier, repairs
def dependency_region(report, glacier):
    proximity = report.intersection(glacier.buffer(PROXIMITY_M, quad_segs=QUAD_SEGS)).difference(glacier)
    screen = proximity.buffer(SCREEN_M, quad_segs=QUAD_SEGS) if not proximity.is_empty else proximity
    return proximity, screen
def tile_footprint(latitude, longitude, crs, center):
    geographic = segmentize(box(longitude, latitude, longitude + 1, latitude + 1), .01)
    forward = Transformer.from_crs(4326, crs, always_xy=True).transform
    return transform(forward, unwrap(geographic, center))
def join_tables(expected, screen, inventory):
    keys = ["cell_key", "south", "west", "dominant_region", "role", "latitude", "longitude"]
    out = expected.merge(screen, on=keys, how="left", validate="many_to_one", indicator=True)
    if len(out) != 32868 or not out._merge.eq("both").all():
        raise ValueError("object-screen join differs")
    present = set(zip(inventory.instance, inventory.object_id))
    out["listed"] = [(x.instance, x.object_id) in present for x in out.itertuples()]
    out["state"] = "listed"
    out.loc[~out.listed & ~out.screen_relevant, "state"] = "absent_outside_conservative_screen"
    out.loc[~out.listed & out.screen_relevant, "state"] = "absent_relevance_unresolved"
    return out.drop(columns="_merge")
def cell_table(objects):
    table = objects.assign(listed_relevant=objects.listed & objects.screen_relevant)
    keys = ["cell_key", "south", "west", "dominant_region", "instance"]
    cells = table.groupby(keys, sort=False).agg(
        proximity_applicable=("proximity_applicable", "first"),
        screen_relevant_objects=("screen_relevant", "sum"),
        listed_relevant_objects=("listed_relevant", "sum"),
        absent_outside_conservative_screen=("state", lambda x: int((x == "absent_outside_conservative_screen").sum())),
        absent_relevance_unresolved=("state", lambda x: int((x == "absent_relevance_unresolved").sum()))).reset_index()
    if len(cells) != 3652 or not table.groupby(keys).size().eq(9).all():
        raise ValueError("cell dimensions differ")
    cells["cell_state"] = "all_relevant_objects_listed"
    cells.loc[~cells.proximity_applicable, "cell_state"] = "not_applicable"
    cells.loc[cells.absent_relevance_unresolved.gt(0), "cell_state"] = "unresolved"
    cells["latitude_band_south"] = (cells.south // 10) * 10
    return cells
def group_table(cells):
    rows = []
    for dimension, column in [("region", "dominant_region"), ("latitude", "latitude_band_south")]:
        for (instance, label), group in cells.groupby(["instance", column], sort=True):
            rows.append({"dimension": dimension, "group": label, "instance": instance,
                "population_cells": len(group),
                "all_relevant_objects_listed_cells": int(group.cell_state.eq("all_relevant_objects_listed").sum()),
                "unresolved_cells": int(group.cell_state.eq("unresolved").sum()),
                "not_applicable_cells": int(group.cell_state.eq("not_applicable").sum())})
    result = pd.DataFrame(rows)
    if len(result) != 68 or not result.groupby(["instance", "dimension"]).population_cells.sum().eq(1826).all():
        raise ValueError("group accounting differs")
    return result
def geometry(pre_manifest):
    verify_manifest(pre_manifest, "pre_geometry")
    frame = pd.read_csv(FRAME, dtype={"dominant_region": str}).reset_index(drop=True)
    expected = pd.read_csv(EXPECTED, dtype={"dominant_region": str})
    spatial = expected.drop_duplicates(["cell_key", "role", "latitude", "longitude"])
    if (len(frame), len(spatial)) != (1826, 16434):
        raise ValueError("frozen dimensions differ")
    matches, rows, repairs = load_matches(frame), [], []
    for index, cell in frame.iterrows():
        crs, _, report, _ = report_geometries(cell.south, cell.west)
        glacier, fixed = projected_union(matches[index], crs, cell.west, cell.cell_key)
        repairs.extend(fixed)
        proximity, screen = dependency_region(report, glacier)
        for item in spatial[spatial.cell_key.eq(cell.cell_key)].itertuples(index=False):
            footprint = tile_footprint(item.latitude, item.longitude, crs, cell.west + .5)
            rows.append({"cell_key": cell.cell_key, "south": cell.south, "west": cell.west,
                "dominant_region": cell.dominant_region, "role": item.role,
                "latitude": item.latitude, "longitude": item.longitude,
                "proximity_applicable": not proximity.is_empty,
                "screen_relevant": bool(not proximity.is_empty and footprint.intersects(screen))})
    object_screen = pd.DataFrame(rows)
    if len(object_screen) != 16434 or object_screen.duplicated(["cell_key", "latitude", "longitude"]).any():
        raise ValueError("screen identity differs")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    object_screen.to_csv(OUTPUT / "object_screen.csv", index=False, lineterminator="\n")
    repair_columns = ["cell_key", "rgi_id", "reason", "input_type", "output_type",
        "projected_area_before_m2", "projected_area_after_m2", "relative_area_change",
        "shapely_version", "geos_version", "proj_version", "projected_crs_wkt"]
    pd.DataFrame(repairs, columns=repair_columns).to_csv(OUTPUT / "projection_repairs.csv", index=False, lineterminator="\n")
    files = {str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": digest(path)}
             for path in [OUTPUT / "object_screen.csv", OUTPUT / "projection_repairs.csv"]}
    manifest = {"status": "geometry_sealed_before_inventory", "rows": len(object_screen),
                "pregeometry_manifest_sha256": digest(PRE), "files": files}
    GEOMETRY.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
def join(pre_manifest, geometry_manifest):
    verify_manifest(pre_manifest, "pre_geometry")
    verify_manifest(geometry_manifest, "geometry_sealed_before_inventory")
    if digest(ISSUE23) != ISSUE23_SHA:
        raise ValueError("Issue 23 manifest differs")
    issue23 = json.loads(ISSUE23.read_text())
    bound = issue23["files"][str(INVENTORY.relative_to(ROOT))]
    if (INVENTORY.stat().st_size, digest(INVENTORY)) != (bound["bytes"], bound["sha256"]):
        raise ValueError("inventory differs")
    expected = pd.read_csv(EXPECTED, dtype={"dominant_region": str})
    screen = pd.read_csv(OUTPUT / "object_screen.csv", dtype={"dominant_region": str})
    inventory = pd.read_csv(INVENTORY)
    objects = join_tables(expected, screen, inventory)
    cells, groups = cell_table(objects), None
    groups = group_table(cells)
    objects.to_csv(OUTPUT / "object_support.csv", index=False, lineterminator="\n")
    cells.to_csv(OUTPUT / "cell_support.csv", index=False, lineterminator="\n")
    groups.to_csv(OUTPUT / "group_support.csv", index=False, lineterminator="\n")
    summary = {instance: {state: int(group.cell_state.eq(state).sum())
        for state in ["all_relevant_objects_listed", "unresolved", "not_applicable"]}
        for instance, group in cells.groupby("instance")}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["geometry", "join"])
    parser.add_argument("--pre-manifest", type=Path, required=True); parser.add_argument("--geometry-manifest", type=Path); args = parser.parse_args()
    geometry(args.pre_manifest) if args.action == "geometry" else join(args.pre_manifest, args.geometry_manifest)

#!/usr/bin/env python3
"""Stage replayable sources for the frozen geographic terrain sample."""
import argparse, csv, hashlib, json, zipfile
from pathlib import Path
import fiona, numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely import STRtree
from shapely.geometry import mapping, shape
from shapely.ops import transform
from scripts.scale_explicit_transfer_source import tile_name, write_raster
from scripts.susceptible_area_convergence import PHASES, local_crs, phase_grid, window_geometry
ROOT = Path(__file__).resolve().parents[1]
OUTPUT, RAW = ROOT / "data/geographic_total", ROOT / "data/geographic_total/source_raw"
SOURCE = OUTPUT / "source"
SAMPLE = ROOT / "data/geographic_sample/sample.csv"
RGI_RAW = ROOT / "data/geographic_sample/source_raw/rgi"
DEM_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
PZI_URL = "https://microsite.geo.uzh.ch/cryodata/pf_global/PZI.flt"
INPUT_HASHES = {"data/geographic_sample/sample.csv": "1e9164813893e285aeeeaa1a7833e16c87172cbe4d3357e245854ab13966613b",
 "data/geographic_sample/frame.csv": "482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879",
 "data/geographic_sample/source_manifest.json": "6b411fc26af146c9dd0959490775e413aa97f57491cf6de6c91261e7e09e196b",
 "scripts/denominator_pilot.py": "5f733147434f859ea3cbfc815da77a1bd8ae83137d80e59a65243d6d3e23508a",
 "scripts/scale_explicit_transfer_source.py": "c495d3b587e40ed6ad036a24857dc6fb6ee4bb0934e0c385d82e8bd7ba259830",
 "scripts/susceptible_area_convergence.py": "9ac2644257ce1ba90bd8f2edbc6e9b47ea152fa02304b0c4b994e495a512b20c"}
def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
def verify(manifest=None):
    for name, expected in INPUT_HASHES.items():
        if sha256(ROOT / name) != expected: raise ValueError(f"frozen file differs: {name}")
    if manifest:
        for name, item in json.loads(Path(manifest).read_text())["files"].items():
            path = ROOT / name
            if (path.stat().st_size, sha256(path)) != (item["bytes"], item["sha256"]): raise ValueError(f"source differs: {name}")
def cells():
    return pd.read_csv(SAMPLE, dtype={"dominant_region": str}).sort_values(
        ["dominant_region", "stratum_rank"], kind="stable")
def cell_label(south, west):
    return f"s{int(south):+04d}_w{int(west):+05d}"
def dem_requests():
    objects = {}
    for row in cells().itertuples(index=False):
        for latitude in range(row.south - 1, row.south + 2):
            for longitude in range(row.west - 1, row.west + 2):
                longitude = (longitude + 180) % 360 - 180
                stem = tile_name(latitude, longitude)
                objects[stem] = {"object_id": stem, "latitude": latitude, "longitude": longitude,
                                 "url": f"{DEM_BASE}/{stem}/{stem}.tif"}
    return [objects[key] for key in sorted(objects, key=lambda key: (objects[key]["latitude"],
                                                                      objects[key]["longitude"]))]
def pzi_request(south):
    north = south + 1.1
    row0 = round((90 - north) * 120)
    rows = min(144, 18000 - row0)
    start = row0 * 43200 * 4
    return {"object_id": f"pzi_rows_{cell_label(south, 0).split('_')[0]}", "south": south,
            "row0": row0, "rows": rows, "byte_start": start,
            "byte_end": start + rows * 43200 * 4 - 1, "url": PZI_URL}
def pzi_requests():
    return [pzi_request(south) for south in sorted(set(cells().south))]
def write_csv(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(records)
def write_requests():
    write_csv(OUTPUT / "dem_requests.csv", dem_requests())
    write_csv(OUTPUT / "pzi_requests.csv", pzi_requests())
def grid(south, west, variant):
    crs = local_crs(south, west)
    _, projected = window_geometry(south, west, crs)
    dx, dy = PHASES[variant]
    shape_grid, affine = phase_grid(projected.buffer(1000).bounds, dx, dy,
                                    3 if variant == "p00" else 1)
    return shape_grid, affine, crs
def dem_paths(south, west):
    paths = []
    for latitude in range(south - 1, south + 2):
        for longitude in sorted((value + 180) % 360 - 180 for value in range(west - 1, west + 2)):
            stem = tile_name(latitude, longitude)
            path = RAW / "dem" / f"{stem}.tif"
            if path.exists(): paths.append(path)
    return paths
def expected_dem_ids(south, west):
    return [tile_name(latitude, longitude)
            for latitude in range(south - 1, south + 2)
            for longitude in sorted((value + 180) % 360 - 180 for value in range(west - 1, west + 2))]
def replay_dem(south, west, variant):
    dimensions, affine, crs = grid(south, west, variant)
    combined = np.full(dimensions, np.nan, dtype=np.float32)
    for path in dem_paths(south, west):
        layer = np.full(dimensions, np.nan, dtype=np.float32)
        with rasterio.open(path) as dataset:
            reproject(rasterio.band(dataset, 1), layer, src_transform=dataset.transform,
                      src_crs=dataset.crs, src_nodata=dataset.nodata, dst_transform=affine,
                      dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.bilinear,
                      init_dest_nodata=True)
        combined[np.isfinite(layer)] = layer[np.isfinite(layer)]
    return combined, affine, crs
def replay_pzi(south, west):
    request = pzi_request(south)
    path = RAW / "pzi" / f"{request['object_id']}.rows"
    rows = np.fromfile(path, dtype="<f4")
    if rows.size != request["rows"] * 43200:
        raise ValueError(f"{path.name}: unexpected PZI range length")
    column = round((west - .1 + 180) * 120)
    values = rows.reshape(request["rows"], 43200)[:, column:column + 144].copy()
    return values, from_origin(west - .1, south + 1.1, 1 / 120, 1 / 120)
def value_hash(values):
    return hashlib.sha256(values.astype("<f4", copy=False).tobytes(order="C")).hexdigest()
def stage_rasters(manifest):
    if manifest is None: raise ValueError("raster staging requires a raw-source manifest")
    verify(manifest)
    sealed = set(json.loads(Path(manifest).read_text())["files"])
    used = {str(path.relative_to(ROOT)) for cell in cells().itertuples(index=False) for path in dem_paths(cell.south, cell.west)}
    used |= {str((RAW / "pzi" / f"{item['object_id']}.rows").relative_to(ROOT)) for item in pzi_requests()}
    if not used <= sealed: raise ValueError(f"unsealed raw source: {sorted(used-sealed)}")
    SOURCE.mkdir(parents=True, exist_ok=True); records = []
    for cell in cells().itertuples(index=False):
        label = cell_label(cell.south, cell.west)
        for variant in PHASES:
            values, affine, crs = replay_dem(cell.south, cell.west, variant)
            path = SOURCE / f"dem_{label}_{variant}.tif"
            write_raster(path, values, affine, crs, np.nan)
            replayed, replay_affine, _ = replay_dem(cell.south, cell.west, variant)
            with rasterio.open(path) as stored:
                retained = stored.read(1).astype(np.float32)
                stored_affine, stored_crs = stored.transform, stored.crs
            records.append({"cell_key": cell.cell_key, "layer": variant, "rows": values.shape[0],
                            "columns": values.shape[1], "affine": tuple(affine),
                            "crs": crs.to_wkt(), "stored_crs_equal": stored_crs == crs,
                            "source_count": len(dem_paths(cell.south, cell.west)),
                            "missing_object_ids": json.dumps(sorted(set(expected_dem_ids(cell.south, cell.west)) -
                                                                     {path.stem for path in dem_paths(cell.south, cell.west)})),
                            "value_sha256": value_hash(retained),
                            "replay_value_sha256": value_hash(replayed),
                            "replay_affine_equal": stored_affine == replay_affine,
                            "finite_mask_equal": np.array_equal(np.isfinite(retained), np.isfinite(replayed)),
                            "replay_max_abs_difference": float(np.nanmax(np.abs(retained - replayed)))})
        values, affine = replay_pzi(cell.south, cell.west)
        path = SOURCE / f"pzi_{label}.tif"
        write_raster(path, values, affine, "EPSG:4326", -9999)
        replayed, replay_affine = replay_pzi(cell.south, cell.west)
        with rasterio.open(path) as stored:
            retained, stored_affine, stored_crs = stored.read(1), stored.transform, stored.crs
        records.append({"cell_key": cell.cell_key, "layer": "pzi", "rows": values.shape[0],
                        "columns": values.shape[1], "affine": tuple(affine), "crs": "EPSG:4326",
                        "stored_crs_equal": stored_crs == rasterio.crs.CRS.from_epsg(4326),
                        "source_count": 1, "missing_object_ids": "[]",
                        "value_sha256": value_hash(retained), "replay_value_sha256": value_hash(replayed),
                        "replay_affine_equal": stored_affine == replay_affine,
                        "finite_mask_equal": np.array_equal(retained != -9999, replayed != -9999),
                        "replay_max_abs_difference": float(np.max(np.abs(retained - replayed)))})
    table = pd.DataFrame(records)
    if len(table) != 480 or not table.value_sha256.equals(table.replay_value_sha256) or not table[["stored_crs_equal", "replay_affine_equal", "finite_mask_equal"]].all().all() or (table.replay_max_abs_difference != 0).any(): raise ValueError("source replay differs")
    table.to_csv(OUTPUT / "source_replay.csv", index=False, lineterminator="\n")
def envelope(south, west):
    crs = local_crs(south, west)
    _, projected = window_geometry(south, west, crs)
    inverse = Transformer.from_crs(crs, 4326, always_xy=True).transform
    return transform(inverse, projected.buffer(1100))
def stage_rgi():
    SOURCE.mkdir(parents=True, exist_ok=True)
    selected = list(cells().itertuples(index=False)); bounds = [envelope(c.south, c.west) for c in selected]
    tree, matches, seen = STRtree(bounds), [[] for _ in selected], {}
    manifest = json.loads((ROOT / "data/geographic_sample/source_manifest.json").read_text())
    if len(manifest["archives"]) != 19: raise ValueError("expected 19 RGI archives")
    for item in manifest["archives"]:
        archive = RGI_RAW / item["filename"]
        if archive.stat().st_size != item["bytes"] or sha256(archive) != item["sha256"]: raise ValueError(f"RGI identity differs: {archive.name}")
        member = next(entry["name"] for entry in item["members"] if entry["name"].endswith(".shp"))
        with fiona.open(f"zip://{archive}!{member}") as collection:
            if collection.crs.to_epsg() != 4326: raise ValueError(f"RGI CRS differs: {archive.name}")
            for feature in collection:
                properties, geometry = dict(feature["properties"]), shape(feature["geometry"])
                rgi_id = properties["rgi_id"]
                identity = (geometry.wkb, json.dumps(properties, sort_keys=True, default=str))
                if str(properties["o1region"]) != item["region"]: raise ValueError(f"RGI region differs: {rgi_id}")
                if rgi_id in seen and seen[rgi_id] != identity: raise ValueError(f"unequal duplicate RGI ID: {rgi_id}")
                if rgi_id in seen: continue
                if not geometry.is_valid: raise ValueError(f"invalid WGS84 RGI geometry: {rgi_id}")
                seen[rgi_id] = identity
                for index in tree.query(geometry, predicate="intersects"):
                    matches[int(index)].append({"type": "Feature", "properties": {
                        "rgi_id": rgi_id, "o1region": properties["o1region"]},
                        "geometry": mapping(geometry)})
    for cell, features in zip(selected, matches):
        if not features: raise ValueError(f"no RGI geometry for {cell.cell_key}")
        path = SOURCE / f"rgi_{cell_label(cell.south, cell.west)}.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                   separators=(",", ":")) + "\n")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["requests", "rgi", "rasters"])
    parser.add_argument("--manifest", type=Path); args = parser.parse_args(); verify()
    {"requests": lambda: write_requests(), "rgi": lambda: stage_rgi(),
     "rasters": lambda: stage_rasters(args.manifest)}[args.action]()

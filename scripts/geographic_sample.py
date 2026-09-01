"""Build the registered RGI-intersecting one-degree probability frame."""

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import fiona
import numpy as np
import pyproj
import shapely
from pyproj import Geod
from shapely import box, force_2d, from_geojson, get_coordinates, make_valid, union_all
from shapely.ops import transform
from shapely.validation import explain_validity


GEOD = Geod(ellps="WGS84")
RGI_BASE = "https://cluster.klima.uni-bremen.de/~fmaussion/misc/rgi7_data/rgi70_official/RGI2000-v7.0-G-global/"
REGION_RE = re.compile(r"RGI2000-v7\.0-G-(\d{2})_[a-z_]+\.zip$")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def polygon_area_m2(geometry):
    if geometry.is_empty:
        return 0.0
    if geometry.geom_type == "Polygon":
        return abs(GEOD.geometry_area_perimeter(geometry)[0])
    if geometry.geom_type == "MultiPolygon":
        return sum(abs(GEOD.geometry_area_perimeter(part)[0]) for part in geometry.geoms)
    raise ValueError(f"non-polygonal geometry: {geometry.geom_type}")


def cell_key(south, west):
    return f"rgi7.0|global|south={south:+04d}|west={west:+05d}"


def unwrap(geometry, center):
    longitude = get_coordinates(geometry)[:, 0]
    if np.all((longitude - center >= -180.0) & (longitude - center < 180.0)):
        return geometry

    def shift(x, y, z=None):
        shifted = center + (np.asarray(x) - center + 180.0) % 360.0 - 180.0
        return (shifted, y) if z is None else (shifted, y, z)

    return transform(shift, geometry)


def polygonal_only(geometry):
    if geometry.geom_type == "Polygon":
        return geometry
    if geometry.geom_type == "MultiPolygon":
        return geometry
    if geometry.geom_type == "GeometryCollection":
        parts = [polygonal_only(part) for part in geometry.geoms]
        parts = [part for part in parts if part is not None and not part.is_empty]
        return union_all(parts) if parts else None
    return None


def clips_by_cell(geometry):
    """Yield canonical cell coordinates and positive-area clipped polygons."""
    original = get_coordinates(geometry)
    unwrapped = unwrap(geometry, float(original[0, 0]))
    minx, miny, maxx, maxy = unwrapped.bounds
    if maxx - minx >= 180 or miny < -90 or maxy > 90:
        raise ValueError(f"unsupported geographic bounds: {unwrapped.bounds}")
    changed = bool(np.any(np.abs(get_coordinates(unwrapped)[:, 0] - original[:, 0]) > 180))
    for south in range(max(-90, math.floor(miny)), min(90, math.ceil(maxy))):
        for unwrapped_west in range(math.floor(minx), math.ceil(maxx)):
            clipped = unwrapped.intersection(box(unwrapped_west, south, unwrapped_west + 1, south + 1))
            if clipped.area <= 0:
                continue
            clipped = polygonal_only(clipped)
            if clipped is None or clipped.area <= 0:
                continue
            west = (unwrapped_west + 180) % 360 - 180
            canonical = unwrap(clipped, west + 0.5)
            if canonical.geom_type not in ("Polygon", "MultiPolygon"):
                raise ValueError(f"positive intersection became {canonical.geom_type}")
            yield south, west, canonical, changed


def repair_geometry(geometry, rgi_id, region):
    if geometry.is_valid:
        return geometry, None
    before = polygon_area_m2(geometry)
    repaired = make_valid(geometry, method="linework")
    if repaired.geom_type not in ("Polygon", "MultiPolygon") or not repaired.is_valid:
        raise ValueError(f"{rgi_id}: make_valid returned {repaired.geom_type}")
    after = polygon_area_m2(repaired)
    relative = abs(after - before) / before if before else math.inf
    if relative > 1e-10:
        raise ValueError(f"{rgi_id}: repair area changed by {relative:.3g}")
    return repaired, {
        "region": region, "rgi_id": rgi_id, "original_reason": explain_validity(geometry),
        "input_type": geometry.geom_type, "output_type": repaired.geom_type,
        "input_area_m2": before, "output_area_m2": after, "relative_area_change": relative,
    }


def allocate(stratum_sizes, total=96):
    target = min(total, sum(stratum_sizes.values()))
    allocation = {h: min(4, size) for h, size in stratum_sizes.items()}
    while sum(allocation.values()) < target:
        candidates = [h for h in allocation if allocation[h] < stratum_sizes[h]]
        winner = min(candidates, key=lambda h: (-stratum_sizes[h] / (allocation[h] + 1), h))
        allocation[winner] += 1
    return allocation


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: f"{v:.12f}" if isinstance(v, float) else v for k, v in row.items()})


def source_manifest(archives, source_dir):
    entries = []
    for region, archive in archives:
        members = []
        with zipfile.ZipFile(archive) as bundle:
            for info in sorted(bundle.infolist(), key=lambda item: item.filename):
                if info.is_dir() or "/" in info.filename:
                    continue
                digest = hashlib.sha256()
                with bundle.open(info) as member:
                    for block in iter(lambda: member.read(1024 * 1024), b""):
                        digest.update(block)
                members.append({"name": info.filename, "bytes": info.file_size,
                                "compressed_bytes": info.compress_size, "compression": info.compress_type,
                                "modified": "%04d-%02d-%02dT%02d:%02d:%02d" % info.date_time,
                                "crc32": f"{info.CRC:08x}", "sha256": digest.hexdigest()})
        header = source_dir / f"rgi_{region}.headers"
        entries.append({"region": region, "url": RGI_BASE + archive.name, "filename": archive.name,
                        "bytes": archive.stat().st_size, "sha256": sha256(archive),
                        "response_headers_path": str(header), "response_headers_sha256": sha256(header),
                        "members": members})
    references = []
    for path in [source_dir / "rgi_distribution_index.html", source_dir / "rgi_distribution_index.headers",
                 source_dir / "rgi_region_definitions.html", source_dir / "rgi_region_definitions.headers",
                 Path("data/area_convergence/source/rgi_nsidc_collection_metadata.json"),
                 Path("data/area_convergence/source/pzi_README.txt"), Path("data/area_convergence/source/pzi.hdr")]:
        references.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"rgi_version": "7.0", "doi": "10.5067/F6JMOVY5NAVZ", "archives": entries,
            "references": references, "region_20": {"name": "Antarctic Mainland", "archive": None,
            "published_glacier_count": 0, "treatment": "explicit zero; no synthetic archive"}}


def build(archive_dir, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    archives = []
    for path in sorted(archive_dir.glob("*.zip")):
        match = REGION_RE.fullmatch(path.name)
        if match:
            archives.append((match.group(1), path))
    if [region for region, _ in archives] != [f"{i:02d}" for i in range(1, 20)]:
        raise ValueError("expected exactly RGI regions 01--19")
    manifest = source_manifest(archives, output_dir / "source")
    (output_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    contributions, repairs, unwraps, seen = {}, [], [], set()
    for region, archive in archives:
        local, counts = defaultdict(list), Counter()
        member = next(item["name"] for item in manifest["archives"][int(region) - 1]["members"] if item["name"].endswith(".shp"))
        with fiona.open(f"zip://{archive}!{member}") as collection:
            if collection.crs.to_epsg() != 4326:
                raise ValueError(f"region {region}: expected EPSG:4326")
            for feature in collection:
                properties = dict(feature["properties"])
                rgi_id = properties["rgi_id"]
                if rgi_id in seen:
                    raise ValueError(f"duplicate RGI ID: {rgi_id}")
                seen.add(rgi_id)
                if properties["o1region"] != region:
                    raise ValueError(f"{rgi_id}: wrong region")
                geometry = force_2d(from_geojson(json.dumps(dict(feature["geometry"]))))
                geometry, record = repair_geometry(geometry, rgi_id, region)
                if record:
                    repairs.append(record)
                was_unwrapped = False
                try:
                    for south, west, clipped, changed in clips_by_cell(geometry):
                        local[(south, west)].append(clipped)
                        counts[(south, west)] += 1
                        was_unwrapped |= changed
                except ValueError as error:
                    raise ValueError(f"{rgi_id}: {error}") from error
                if was_unwrapped:
                    unwraps.append({"region": region, "rgi_id": rgi_id, "operation": "unwrap_about_first_vertex"})
        for cell, geometries in local.items():
            merged = union_all(geometries)
            if not merged.is_valid or merged.geom_type not in ("Polygon", "MultiPolygon"):
                raise ValueError(f"region {region}, cell {cell}: invalid union")
            contributions[(cell[0], cell[1], region)] = (merged, counts[cell])

    by_cell = defaultdict(list)
    contribution_rows = []
    for (south, west, region), (geometry, count) in sorted(contributions.items()):
        by_cell[(south, west)].append((region, geometry))
        contribution_rows.append({"cell_key": cell_key(south, west), "south": south, "west": west,
            "region": region, "eligible_latitude": "yes" if -60 <= south <= 89 else "no",
            "feature_count": count, "region_union_intersection_area_km2": polygon_area_m2(geometry) / 1e6})

    cells, exclusions = [], []
    for (south, west), region_geometries in sorted(by_cell.items()):
        merged = union_all([geometry for _, geometry in region_geometries])
        total_area = polygon_area_m2(merged) / 1e6
        area_by_region = [(polygon_area_m2(geometry), region) for region, geometry in region_geometries]
        dominant = min(area_by_region, key=lambda item: (-item[0], item[1]))[1]
        base = {"cell_key": cell_key(south, west), "south": south, "west": west,
                "cell_area_km2": polygon_area_m2(box(west, south, west + 1, south + 1)) / 1e6,
                "rgi_union_intersection_area_km2": total_area,
                "contributing_region_count": len(region_geometries), "dominant_region": dominant}
        (cells if -60 <= south <= 89 else exclusions).append(base)

    sizes = Counter(row["dominant_region"] for row in cells)
    allocation = allocate({f"{i:02d}": sizes[f"{i:02d}"] for i in range(1, 21)})
    allocation_rows = [{"region": h, "population_cells": sizes[h], "sample_cells": allocation[h],
                        "inclusion_probability": allocation[h] / sizes[h] if sizes[h] else 0.0}
                       for h in sorted(allocation)]
    lookup = {row["region"]: row for row in allocation_rows}
    for row in cells:
        assigned = lookup[row["dominant_region"]]
        row.update({"stratum_population_cells": assigned["population_cells"],
                    "stratum_sample_cells": assigned["sample_cells"],
                    "inclusion_probability": assigned["inclusion_probability"]})

    outputs = {
        "frame.csv": (cells, list(cells[0])), "region_contributions.csv": (contribution_rows, list(contribution_rows[0])),
        "latitude_exclusions.csv": (exclusions, list(exclusions[0])),
        "region_allocations.csv": (allocation_rows, list(allocation_rows[0])),
        "geometry_repairs.csv": (repairs, ["region", "rgi_id", "original_reason", "input_type", "output_type",
                                                   "input_area_m2", "output_area_m2", "relative_area_change"]),
        "antimeridian_operations.csv": (unwraps, ["region", "rgi_id", "operation"]),
        "duplicate_ids.csv": ([], ["rgi_id", "first_region", "duplicate_region"]),
    }
    for name, (rows, fields) in outputs.items():
        write_csv(output_dir / name, rows, fields)
    artifact_hashes = {name: {"bytes": (output_dir / name).stat().st_size, "sha256": sha256(output_dir / name)}
                       for name in ["source_manifest.json", *outputs]}
    implementation_paths = [Path("protocol/geographic-probability-sample.md"), Path("requirements-geographic.txt"),
                            Path("scripts/geographic_sample.py"), Path("tests/test_geographic_sample.py")]
    implementation = {str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)}
                      for path in implementation_paths}
    freeze = {"status": "pre-randomization; no DEM or PZI values opened", "population_cells": len(cells),
              "excluded_cells": len(exclusions), "sample_cells": sum(allocation.values()),
              "rgi_features": len(seen), "artifacts": artifact_hashes, "implementation": implementation,
              "environment": {"python": platform.python_version(), "fiona": fiona.__version__,
                              "shapely": shapely.__version__, "geos": shapely.geos_version_string,
                              "pyproj": pyproj.__version__, "proj": pyproj.proj_version_str}}
    (output_dir / "pre_randomization_manifest.json").write_text(json.dumps(freeze, indent=2) + "\n")
    return freeze


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", type=Path, default=Path("data/geographic_sample/source_raw/rgi"))
    parser.add_argument("--output", type=Path, default=Path("data/geographic_sample"))
    args = parser.parse_args()
    print(json.dumps(build(args.archives, args.output), indent=2))

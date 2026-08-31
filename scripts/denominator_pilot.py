#!/usr/bin/env python3
"""Enumerate climate- and case-blind susceptible-terrain objects."""
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window, from_bounds, transform as window_transform
from scipy.ndimage import binary_erosion, distance_transform_edt, label
from shapely import box, segmentize
from shapely.geometry import mapping, shape
from shapely.ops import transform
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "denominator" / "source"
OUTPUT = ROOT / "data" / "denominator"
WINDOWS = {
    "01": ("Alaska", 58, -155, "005183c21b8b2a67edf336600e1070fb8146902d6bda46564a0bcb1cf7f70c67"),
    "11": ("Central Europe", 45, 7, "0a75db72f96d14931d6e78c41cb17310ce639e04c55629de12d0424500b92f11"),
    "13": ("Central Asia", 43, 94, "002eae9c6e63bb8b86dcc306c8866842861c87de413942ea69d7d3c31cbc1715"),
}
CROSS = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)
def select_window(rows, region):
    """Return the registered minimum-digest eligible one-degree cell."""
    cells = {}
    for row in rows:
        lon = (float(row["cenlon"]) + 180) % 360 - 180
        cell = math.floor(float(row["cenlat"])), math.floor(lon)
        cells.setdefault(cell, []).append(float(row["area_km2"]))
    eligible = []
    for (south, west), areas in cells.items():
        n, area = len(areas), math.fsum(areas)
        if n >= 10 and area >= 1:
            key = f"rgi7.0|{region}|south={south:+03d}|west={west:+04d}"
            eligible.append((hashlib.sha256(key.encode()).hexdigest(), south, west, n, area))
    if not eligible:
        raise ValueError(f"region {region} has no eligible cell")
    return min(eligible)
def slope_degrees(z, spacing):
    """Centered-difference slope with strict five-cell finite support."""
    out = np.full(z.shape, np.nan, dtype=np.float32)
    core = z[1:-1, 1:-1]
    valid = np.isfinite(core) & np.isfinite(z[1:-1, :-2]) & np.isfinite(z[1:-1, 2:])
    valid &= np.isfinite(z[:-2, 1:-1]) & np.isfinite(z[2:, 1:-1])
    dx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2 * spacing)
    dy = (z[:-2, 1:-1] - z[2:, 1:-1]) / (2 * spacing)
    values = np.degrees(np.arctan(np.hypot(dx, dy)))
    out[1:-1, 1:-1] = np.where(valid, values, np.nan)
    return out
def aggregate_3x3(z):
    """Strict arithmetic aggregation of an aligned 30 m grid."""
    if z.shape[0] % 3 or z.shape[1] % 3:
        raise ValueError("30 m grid dimensions must be divisible by three")
    blocks = z.reshape(z.shape[0] // 3, 3, z.shape[1] // 3, 3)
    valid = np.isfinite(blocks).all(axis=(1, 3))
    mean = blocks.mean(axis=(1, 3), dtype=np.float64).astype(np.float32)
    return np.where(valid, mean, np.nan)
def window_geometry(south, west, crs):
    geographic = segmentize(box(west, south, west + 1, south + 1), 0.01)
    project = Transformer.from_crs(4326, crs, always_xy=True).transform
    return geographic, transform(project, geographic)
def local_crs(south, west):
    return CRS.from_proj4(
        f"+proj=laea +lat_0={south + .5} +lon_0={west + .5} +datum=WGS84 +units=m +no_defs"
    )
def burn(geometries, out_shape, affine, all_touched=False):
    return rasterize(
        ((mapping(geom), 1) for geom in geometries if not geom.is_empty),
        out_shape=out_shape,
        transform=affine,
        fill=0,
        all_touched=all_touched,
        dtype="uint8",
    ).astype(bool)
def warp_band(path, out_shape, affine, crs):
    out = np.full(out_shape, np.nan, dtype=np.float32)
    with rasterio.open(path) as source:
        reproject(
            source=rasterio.band(source, 1),
            destination=out,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=affine,
            dst_crs=crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    return out
def polygon_values(array, affine, geometry, all_touched=False):
    """Values in pixel-center cells inside one polygon, without a full-grid mask."""
    raw = from_bounds(*geometry.bounds, transform=affine)
    col0, row0 = max(0, math.floor(raw.col_off)), max(0, math.floor(raw.row_off))
    col1 = min(array.shape[1], math.ceil(raw.col_off + raw.width))
    row1 = min(array.shape[0], math.ceil(raw.row_off + raw.height))
    if row1 <= row0 or col1 <= col0:
        return np.array([], dtype=array.dtype)
    window = Window(col0, row0, col1 - col0, row1 - row0)
    mask = burn([geometry], (row1 - row0, col1 - col0),
                window_transform(window, affine), all_touched)
    return array[row0:row1, col0:col1][mask]
def volume_fields(area):
    return {f"eligible_d{depth}": "yes" if area * depth >= 1e6 else "no" for depth in (10, 30, 100)}
def contact_distance(glaciers, spacing):
    return np.maximum(0, distance_transform_edt(~glaciers) - 1) * spacing
def pzi_classes(pzi):
    valid = np.isfinite(pzi)
    return (valid & (pzi >= 0.1), valid & (pzi >= 0.5),
            valid & np.isclose(pzi, 0.01, atol=1e-6), valid & (pzi == 0))
def component_rows(mask, report, spacing, base):
    labels, count = label(mask & report, structure=CROSS)
    boundary = report & ~binary_erosion(report, structure=CROSS, border_value=0)
    truncated = set(np.unique(labels[boundary])) - {0}
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    rows = []
    for component in range(1, count + 1):
        area = int(sizes[component]) * spacing**2
        row = dict(base, object_id=f"C{component:06d}", area_m2=area)
        row["edge_truncated"] = "yes" if component in truncated else "no"
        row.update(volume_fields(area))
        rows.append(row)
    return rows
def load_features(path, crs):
    with path.open() as handle:
        collection = json.load(handle)
    project = Transformer.from_crs(4326, crs, always_xy=True).transform
    return [(item["properties"], shape(item["geometry"]), transform(project, shape(item["geometry"])))
            for item in collection["features"]]
def glacier_rows(features, window_wgs, window_laea, z, affine, count_path):
    count = count_affine = count_project = None
    if count_path.exists():
        dataset = rasterio.open(count_path)
        count = dataset.read(1).astype(float)
        count_affine = dataset.transform
        count_project = Transformer.from_crs(4326, dataset.crs, always_xy=True).transform
        dataset.close()
    rows = []
    for properties, geographic, projected in features:
        clipped = projected.intersection(window_laea)
        if clipped.is_empty:
            continue
        area = clipped.area
        dem_values = polygon_values(z, affine, clipped)
        valid_dem = np.isfinite(dem_values)
        coverage = "not_covered"
        fraction = median = ""
        if count is not None:
            count_geom = transform(count_project, geographic.intersection(window_wgs))
            values = polygon_values(count, count_affine, count_geom, all_touched=True)
            if values.size:
                coverage = "covered"
                fraction = float(np.mean(values > 0))
                median = float(np.median(values[values > 0])) if np.any(values > 0) else ""
        row = {
            "stratum": "glacier", "resolution_m": 0, "slope_deg": "", "contact_m": "",
            "pzi_min": "", "object_id": properties["rgi_id"], "area_m2": area,
            "catalog_area_m2": float(properties["area_km2"]) * 1e6,
            "edge_truncated": "no" if window_laea.contains(projected) else "yes",
            "outline_date": properties["src_date"],
            "pzi_reference_period": "not_applicable", "pzi_status": "not_applicable",
            "itslive_period": "2014-2022",
            "dem_valid_fraction": float(np.mean(valid_dem)) if dem_values.size else 0.0,
            "itslive_status": coverage, "itslive_positive_fraction": fraction,
            "itslive_median_positive_count": median,
        }
        row.update(volume_fields(area))
        rows.append(row)
    return rows
def region_layers(region, resolution=30):
    _, south, west, _ = WINDOWS[region]
    crs = local_crs(south, west)
    features = load_features(SOURCE / f"rgi_{region}.geojson", crs)
    with rasterio.open(SOURCE / f"dem_{region}_30m.tif") as dataset:
        z = dataset.read(1, masked=True).filled(np.nan).astype(np.float32)
        affine = dataset.transform
        if dataset.crs != crs or abs(dataset.res[0] - 30) > 1e-6:
            raise ValueError(f"region {region} DEM grid differs from protocol")
    window_wgs, window_laea = window_geometry(south, west, crs)
    if resolution == 90:
        z, affine = aggregate_3x3(z), affine * Affine.scale(3)
    glaciers = burn((item[2] for item in features), z.shape, affine)
    report = burn([window_laea], z.shape, affine)
    pzi = warp_band(SOURCE / f"pzi_{region}.tif", z.shape, affine, crs)
    return z, affine, features, window_wgs, window_laea, report, glaciers, pzi
def analyze_region(region):
    name, south, west, digest = WINDOWS[region]
    base_region = {"region": region, "region_name": name, "rgi_target_epoch": "near_2000",
                   "dem_acquisition_epoch": "2011-2015"}
    rows = []
    layers30 = region_layers(region)
    z, affine, features, window_wgs, window_laea, report, _, _ = layers30
    rows.extend(dict(base_region, **row) for row in glacier_rows(
        features, window_wgs, window_laea, z, affine, SOURCE / f"itslive_count_{region}.tif"
    ))
    crs_wkt = local_crs(south, west).to_wkt()
    window_record = {
        **base_region, "south": south, "west": west, "selector_sha256": digest,
        "laea_wkt": crs_wkt, "laea_wkt_sha256": hashlib.sha256(crs_wkt.encode()).hexdigest(),
        "grid_transform_30m": ",".join(map(str, tuple(affine))),
        "grid_height_30m": z.shape[0], "grid_width_30m": z.shape[1],
        "dem_valid_fraction": float(np.mean(np.isfinite(z)[report])),
    }
    for spacing in (30, 90):
        z, affine, _, _, _, report, glaciers, pzi = region_layers(region, spacing)
        slope = slope_degrees(z, spacing)
        distance = contact_distance(glaciers, spacing)
        pzi_primary, pzi_sensitivity, pzi_fringe, pzi_background = pzi_classes(pzi)
        for threshold in (25, 30, 35):
            steep = np.isfinite(slope) & (slope >= threshold) & ~glaciers
            for contact in (0, 100, 300):
                base = dict(base_region, stratum="glacier_contact", resolution_m=spacing,
                            slope_deg=threshold, contact_m=contact, pzi_min="", outline_date="",
                            catalog_area_m2="", pzi_reference_period="not_applicable",
                            pzi_status="not_applicable", itslive_period="not_applicable",
                            dem_valid_fraction=1.0, itslive_status="not_applicable",
                            itslive_positive_fraction="", itslive_median_positive_count="")
                rows.extend(component_rows(steep & (distance <= contact), report, spacing, base))
            for pzi_min, pzi_mask in ((0.1, pzi_primary), (0.5, pzi_sensitivity)):
                base = dict(base_region, stratum="permafrost", resolution_m=spacing,
                            slope_deg=threshold, contact_m="", pzi_min=pzi_min, outline_date="",
                            catalog_area_m2="", pzi_reference_period="1961-1990",
                            pzi_status="covered", itslive_period="not_applicable",
                            dem_valid_fraction=1.0, itslive_status="not_applicable",
                            itslive_positive_fraction="", itslive_median_positive_count="")
                rows.extend(component_rows(steep & pzi_mask, report, spacing, base))
        window_record[f"pzi_valid_fraction_{spacing}m"] = float(np.mean(np.isfinite(pzi)[report]))
        window_record[f"pzi_fringe_fraction_{spacing}m"] = float(np.mean(pzi_fringe[report]))
        window_record[f"pzi_background_fraction_{spacing}m"] = float(np.mean(pzi_background[report]))
    return window_record, rows
def summarize(objects):
    groups = ["region", "region_name", "stratum", "resolution_m", "slope_deg", "contact_m", "pzi_min"]
    rows = []
    for keys, group in objects.groupby(groups, dropna=False, sort=True):
        for scope in ("all", "contained"):
            selected = group if scope == "all" else group[group.edge_truncated == "no"]
            row = dict(zip(groups, keys))
            row.update(edge_scope=scope, object_count=len(selected), area_m2=selected.area_m2.sum())
            for depth in (10, 30, 100):
                row[f"eligible_d{depth}_count"] = int((selected[f"eligible_d{depth}"] == "yes").sum())
            rows.append(row)
    return pd.DataFrame(rows)
def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    windows, rows = zip(*(analyze_region(region) for region in WINDOWS))
    objects = pd.DataFrame([row for region_rows in rows for row in region_rows])
    objects.to_csv(OUTPUT / "objects.csv", index=False)
    summarize(objects).to_csv(OUTPUT / "summary.csv", index=False)
    pd.DataFrame(windows).to_csv(OUTPUT / "windows.csv", index=False)
    primary = objects[(objects.resolution_m.isin([0, 30])) &
                      ((objects.stratum == "glacier") |
                       ((objects.stratum == "glacier_contact") & (objects.slope_deg == 30) &
                        (objects.contact_m == 100)) |
                       ((objects.stratum == "permafrost") & (objects.slope_deg == 30) &
                        (objects.pzi_min == 0.1)))].copy()
    primary["sample_hash"] = primary.apply(
        lambda row: hashlib.sha256(f"{row.region}|{row.stratum}|{row.object_id}".encode()).hexdigest(), axis=1
    )
    primary.sort_values("sample_hash").groupby(["region", "stratum"]).head(5).to_csv(
        OUTPUT / "validation_sample.csv", index=False
    )
    print(f"wrote {len(objects):,} object rows and {len(summarize(objects)):,} summaries")
if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build and replay frozen blind-transfer rasters from retained source bytes."""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

from scripts.susceptible_area_convergence import PHASES, local_crs, phase_grid, window_geometry

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "scale_explicit_transfer"
SOURCE, RAW = OUTPUT / "source", OUTPUT / "source_raw"
WINDOWS = {"10": (65, 145), "18": (-44, 171), "15": (28, 96), "04": (72, -79)}


def tile_name(latitude, longitude):
    """Return the literal GLO-30 COG stem for an integer tile origin."""
    lat = f"S{-latitude:02d}" if latitude < 0 else f"N{latitude:02d}"
    lon = f"W{-longitude:03d}" if longitude < 0 else f"E{longitude:03d}"
    return f"Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM"


def dem_sources(south, west):
    """Return available native COGs in registered latitude-longitude order."""
    candidates = [RAW / "dem" / f"{tile_name(lat, lon)}.tif"
                  for lat in range(south - 1, south + 2)
                  for lon in range(west - 1, west + 2)]
    return [path for path in candidates if path.exists()]


def replay_dem(south, west, variant):
    """Warp native COGs directly to one registered phase grid."""
    crs = local_crs(south, west)
    _, projected = window_geometry(south, west, crs)
    dx, dy = PHASES[variant]
    shape, affine = phase_grid(projected.buffer(1000).bounds, dx, dy,
                               3 if variant == "p00" else 1)
    combined = np.full(shape, np.nan, dtype=np.float32)
    for path in dem_sources(south, west):
        layer = np.full(shape, np.nan, dtype=np.float32)
        with rasterio.open(path) as dataset:
            reproject(rasterio.band(dataset, 1), layer,
                      src_transform=dataset.transform, src_crs=dataset.crs,
                      src_nodata=dataset.nodata, dst_transform=affine, dst_crs=crs,
                      dst_nodata=np.nan, resampling=Resampling.bilinear,
                      init_dest_nodata=True)
        finite = np.isfinite(layer)
        combined[finite] = layer[finite]
    return combined, affine, crs


def replay_pzi(region, south, west):
    """Extract the registered 144 columns from one exact 144-row range."""
    rows = np.fromfile(RAW / "pzi" / f"pzi_{region}.rows", dtype="<f4")
    if rows.size != 144 * 43200:
        raise ValueError(f"region {region} PZI range has unexpected length")
    column = round((west - 0.1 + 180) * 120)
    values = rows.reshape(144, 43200)[:, column:column + 144].copy()
    return values, from_origin(west - 0.1, south + 1.1, 1 / 120, 1 / 120)


def write_raster(path, values, affine, crs, nodata):
    """Serialize one analysis input without changing its Float32 values."""
    profile = dict(driver="GTiff", height=values.shape[0], width=values.shape[1],
                   count=1, dtype="float32", crs=crs, transform=affine,
                   nodata=nodata, compress="deflate", predictor=3, tiled=True)
    with rasterio.open(path, "w", **profile) as target:
        target.write(values.astype(np.float32), 1)


def value_hash(values):
    return hashlib.sha256(values.astype("<f4", copy=False).tobytes(order="C")).hexdigest()


def main():
    SOURCE.mkdir(parents=True, exist_ok=True)
    records = []
    for region, (south, west) in WINDOWS.items():
        for variant in PHASES:
            values, affine, crs = replay_dem(south, west, variant)
            path = SOURCE / f"dem_{region}_{variant}_30m.tif"
            write_raster(path, values, affine, crs, np.nan)
            replayed, replay_affine, _ = replay_dem(south, west, variant)
            difference = np.abs(values.astype(float) - replayed.astype(float))
            sources = dem_sources(south, west)
            source_key = "\n".join(f"{p.stem}\t{hashlib.sha256(p.read_bytes()).hexdigest()}"
                                   for p in sources)
            records.append(dict(region=region, layer=variant, rows=values.shape[0],
                                columns=values.shape[1], affine=tuple(affine),
                                source_count=len(sources),
                                source_set_sha256=hashlib.sha256(source_key.encode()).hexdigest(),
                                finite_cell_count=int(np.isfinite(values).sum()),
                                value_sha256=value_hash(values),
                                replay_value_sha256=value_hash(replayed),
                                replay_affine_equal=affine == replay_affine,
                                replay_max_abs_difference=float(np.nanmax(difference))))
        pzi, affine = replay_pzi(region, south, west)
        write_raster(SOURCE / f"pzi_{region}.tif", pzi, affine, "EPSG:4326", -9999)
        replayed, replay_affine = replay_pzi(region, south, west)
        records.append(dict(region=region, layer="pzi", rows=144, columns=144,
                            affine=tuple(affine), source_count=1,
                            source_set_sha256=hashlib.sha256(
                                (RAW / "pzi" / f"pzi_{region}.rows").read_bytes()).hexdigest(),
                            finite_cell_count=int((pzi != -9999).sum()), value_sha256=value_hash(pzi),
                            replay_value_sha256=value_hash(replayed),
                            replay_affine_equal=affine == replay_affine,
                            replay_max_abs_difference=float(np.max(np.abs(pzi - replayed)))))
    pd.DataFrame(records).to_csv(OUTPUT / "source_replay.csv", index=False, lineterminator="\n")
    print("froze and replayed 20 blind-transfer source rasters")


if __name__ == "__main__":
    main()

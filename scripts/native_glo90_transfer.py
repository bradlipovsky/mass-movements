#!/usr/bin/env python3
"""Compare native GLO-90 with frozen GLO-30 terrain-function results."""
import argparse, hashlib, json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.warp import Resampling, reproject

import scripts.scale_explicit_steep_area as estimator
from scripts.denominator_pilot import burn, warp_band, window_geometry
from scripts.scale_explicit_transfer import projected_features
from scripts.susceptible_area_convergence import local_crs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/native_glo90_transfer"
PRE, RAW = OUT / "preaccess_manifest.json", OUT / "raw_source_manifest.json"
WINDOWS, LEDGER = OUT / "windows.csv", OUT / "source_ledger.csv"
PHASES = {"n00": (0, 0), "nx45": (45, 0), "ny45": (0, 45), "nxy45": (45, 45)}


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_files(records):
    for name, expected in records.items():
        path = ROOT / name
        if (path.stat().st_size, digest(path)) != (expected["bytes"], expected["sha256"]): raise ValueError(f"sealed file differs: {name}")


def verify_raw(path):
    if Path(path).resolve() != RAW.resolve(): raise ValueError("unapproved raw-manifest path")
    pre, raw = json.loads(PRE.read_text()), json.loads(RAW.read_text())
    if pre.get("status") != "pre_native_glo90_access" or raw.get("status") != "raw_native_glo90_sources_sealed_unopened": raise ValueError("manifest status differs")
    if raw.get("preaccess_manifest_sha256") != digest(PRE) or raw.get("responses") != 63: raise ValueError("raw source ancestry differs")
    verify_files(pre["files"]); verify_files(raw["files"])
    ledger = pd.read_csv(LEDGER, dtype={"region": str})
    if len(ledger) != 63 or ledger.object_id.nunique() != 63 or not ledger.http_status.isin([200, 404]).all(): raise ValueError("source ledger differs")


def source_directory(window): return ROOT / "data" / window.source_family / "source"


def base_grid(window):
    path = source_directory(window) / f"dem_{window.region}_p00_30m.tif"
    with rasterio.open(path) as source:
        if source.res != (30, 30) or source.width % 3 or source.height % 3: raise ValueError(f"p00 grid differs: {window.region}")
        return (source.height // 3, source.width // 3), source.transform * Affine.scale(3), source.crs


def phase_affine(base, phase):
    dx, dy = PHASES[phase]
    return Affine(base.a, base.b, base.c + dx, base.d, base.e, base.f + dy)


def native_paths(region):
    ledger = pd.read_csv(LEDGER, dtype={"region": str})
    return [OUT / path for path in ledger[(ledger.region == region) & (ledger.http_status == 200)].path]


def warp_native(paths, shape, affine, crs):
    combined = np.full(shape, np.nan, dtype=np.float32)
    for path in paths:
        layer = np.full(shape, np.nan, dtype=np.float32)
        with rasterio.open(path) as source:
            if source.count != 1 or source.dtypes[0] != "float32" or source.crs.to_epsg() != 4326: raise ValueError(f"native source metadata differs: {path.name}")
            reproject(rasterio.band(source, 1), layer, src_transform=source.transform, src_crs=source.crs,
                      src_nodata=source.nodata, dst_transform=affine, dst_crs=crs, dst_nodata=np.nan,
                      resampling=Resampling.bilinear, init_dest_nodata=True)
        combined[np.isfinite(layer)] = layer[np.isfinite(layer)]
    return combined


def phase_records(window, phase):
    shape, base, crs = base_grid(window); affine = phase_affine(base, phase); paths = native_paths(window.region)
    z = warp_native(paths, shape, affine, crs)
    _, projected = window_geometry(window.south, window.west, crs)
    report = burn([projected], shape, affine)
    geometries = [item[2] for item in projected_features(source_directory(window) / f"rgi_{window.region}.geojson", crs)]
    inside, proximity = estimator.vector_masks(geometries, shape, affine)
    pzi = warp_band(source_directory(window) / f"pzi_{window.region}.tif", shape, affine, crs)
    a, b, complete = estimator.plane_gradient(z, 90); weight = estimator.steepness_weight(np.hypot(a, b))
    masks = {"glacier_proximity": proximity, "permafrost": ~inside & np.isfinite(pzi) & (pzi >= 0.1)}
    common = dict(region=window.region, region_name=window.region_name, south=window.south, west=window.west,
                  window_key=window.window_key, window_sha256=window.window_sha256, phase=phase,
                  phase_x_m=PHASES[phase][0], phase_y_m=PHASES[phase][1], spacing_m=90,
                  source_object_count=len(paths), missing_source_count=9-len(paths), report_cell_count=int(report.sum()),
                  finite_dem_center_count=int((report & np.isfinite(z)).sum()), complete_support_center_count=int((report & complete).sum()))
    records = []
    for stratum, mask in masks.items():
        support, weighted, area = estimator.integrate(weight, report, mask, complete, 90)
        records.append(dict(common, stratum=stratum, stratum_center_count=int((report & mask).sum()),
                            integration_center_count=int(support.sum()), weighted_cell_sum=weighted,
                            equivalent_steep_area_m2=area))
    return records


def baseline(window):
    directory = ROOT / "data" / ("scale_explicit_steep_area" if window.source_family == "area_convergence" else "scale_explicit_transfer")
    table = pd.read_csv(directory / "equivalent_area_long.csv", dtype={"region": str})
    return table[(table.region == window.region) & table.variant.isin(["p00", "r90"])][["stratum", "variant", "equivalent_steep_area_m2"]]


def departure(reference, value): return abs(value-reference)/reference if reference > 0 else (0.0 if value == 0 else np.nan)


def comparison_records(native, windows):
    records = []
    for window in windows.itertuples(index=False):
        base, group = baseline(window), native[native.region == window.region]
        for stratum in ["glacier_proximity", "permafrost"]:
            known = base[base.stratum == stratum].set_index("variant").equivalent_steep_area_m2
            phases = group[group.stratum == stratum].set_index("phase"); areas = phases.loc[list(PHASES)].equivalent_steep_area_m2.to_numpy(float)
            reference, aggregate, primary = float(known.p00), float(known.r90), float(areas[0]); mean = float(np.mean(areas))
            structural = reference == 0 and aggregate == 0 and np.all(areas == 0)
            records.append(dict(region=window.region, region_name=window.region_name, stratum=stratum,
                reference_glo30_p00_m2=reference, aggregated_glo30_r90_m2=aggregate,
                aggregated_glo30_departure=departure(reference, aggregate), native_glo90_n00_m2=primary,
                native_glo90_departure=departure(reference, primary), native_phase_mean_m2=mean,
                native_phase_cv=0.0 if structural else (float(np.std(areas)/mean) if mean > 0 else np.nan),
                primary_finite_center_fraction=float(phases.loc["n00"].finite_dem_center_count/phases.loc["n00"].report_cell_count),
                primary_complete_support_fraction=float(phases.loc["n00"].complete_support_center_count/phases.loc["n00"].report_cell_count),
                structural_zero="yes" if structural else "no",
                zero_reference_positive_comparison="yes" if reference == 0 and (aggregate > 0 or np.any(areas > 0)) else "no",
                interpretation="exposed_window_native_source_development_no_pass_label"))
    return records


def calculate(manifest):
    verify_raw(manifest); windows = pd.read_csv(WINDOWS, dtype={"region": str}); records = []
    for window in windows.itertuples(index=False):
        for phase in PHASES: records.extend(phase_records(window, phase))
    long = pd.DataFrame(records); comparisons = pd.DataFrame(comparison_records(long, windows))
    if (len(long), len(comparisons)) != (56, 14): raise ValueError("output dimensions differ")
    long.to_csv(OUT / "equivalent_area_long.csv", index=False, lineterminator="\n")
    comparisons.to_csv(OUT / "comparisons.csv", index=False, lineterminator="\n")
    print(f"wrote {len(long)} development rows and {len(comparisons)} comparisons; no pass label")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--raw-manifest", type=Path, required=True)
    calculate(parser.parse_args().raw_manifest)

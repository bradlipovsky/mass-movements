#!/usr/bin/env python3
"""Compare native GLO-90 with frozen GLO-30 terrain-function results."""
import argparse, csv, hashlib, importlib.metadata, json, platform
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
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "data/native_glo90_transfer"
PRE, RAW, SCHEMAS = OUT / "preaccess_manifest.json", OUT / "raw_source_manifest.json", OUT / "output_schemas.json"
WINDOWS, EXPECTED, LEDGER = OUT / "windows.csv", OUT / "expected_sources.csv", OUT / "source_ledger.csv"
PHASES = {"n00": (0, 0), "nx45": (45, 0), "ny45": (0, 45), "nxy45": (45, 45)}
IDENTITY = ["region", "window_key", "latitude", "longitude", "object_id", "key", "url"]
PACKAGES = ["affine", "numpy", "pandas", "rasterio", "scipy", "shapely", "pyproj"]
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def environment(): return {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in PACKAGES}}
def csv_rows(path):
    with Path(path).open(newline="") as handle: return list(csv.DictReader(handle))
def verify_files(records):
    for name, expected in records.items():
        path = ROOT / name
        if (path.stat().st_size, digest(path)) != (expected["bytes"], expected["sha256"]): raise ValueError(f"sealed file differs: {name}")
def verify_raw(path, approved_sha256):
    if Path(path).resolve() != RAW.resolve() or digest(RAW) != approved_sha256: raise ValueError("unapproved raw manifest")
    pre, raw = json.loads(PRE.read_text()), json.loads(RAW.read_text()); expected, ledger = csv_rows(EXPECTED), csv_rows(LEDGER)
    fixed = (pre.get("status"), pre.get("issue"), pre.get("request_rows"), pre.get("environment"), pre.get("schemas"))
    if fixed != ("pre_native_glo90_access_v2", 27, 63, environment(), json.loads(SCHEMAS.read_text())): raise ValueError("pre-access contract differs")
    if raw.get("status") != "raw_native_glo90_sources_sealed_unopened_v2" or raw.get("preaccess_manifest_sha256") != digest(PRE) or raw.get("expected_sources_sha256") != digest(EXPECTED): raise ValueError("raw ancestry differs")
    if len(ledger) != 63 or len({x.get("object_id") for x in ledger}) != 63 or [[x.get(key, "") for key in IDENTITY] for x in ledger] != [[x[key] for key in IDENTITY] for x in expected]: raise ValueError("ledger population or order differs")
    if any(int(x["http_status"]) not in (200, 404) for x in ledger): raise ValueError("unexpected retained response")
    for item in ledger:
        suffix = ".tif" if int(item["http_status"]) == 200 else ".http404"
        if item["path"] != f"source_raw/{item['object_id']}{suffix}" or (OUT / item["path"]).resolve().parent != (OUT / "source_raw").resolve(): raise ValueError("noncanonical raw path")
    names = {str(LEDGER.relative_to(ROOT)), *[str((OUT / x["path"]).relative_to(ROOT)) for x in ledger]}
    counts = {str(code): sum(int(x["http_status"]) == code for x in ledger) for code in (200, 404)}
    if raw.get("responses") != 63 or raw.get("http_status_counts") != counts or set(raw.get("files", {})) != names: raise ValueError("raw file closure differs")
    verify_files(pre["files"]); verify_files(raw["files"]); return pre, ledger
def source_directory(window): return ROOT / "data" / window.source_family / "source"
def base_grid(window):
    path = source_directory(window) / f"dem_{window.region}_p00_30m.tif"
    with rasterio.open(path) as source:
        if source.res != (30, 30) or source.width % 3 or source.height % 3: raise ValueError(f"p00 grid differs: {window.region}")
        return (source.height // 3, source.width // 3), source.transform * Affine.scale(3), source.crs
def phase_affine(base, phase):
    dx, dy = PHASES[phase]; return Affine(base.a, base.b, base.c + dx, base.d, base.e, base.f + dy)
def native_paths(region, ledger): return [OUT / x["path"] for x in ledger if x["region"] == region and int(x["http_status"]) == 200]
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
def phase_records(window, phase, ledger):
    shape, base, crs = base_grid(window); affine = phase_affine(base, phase); paths = native_paths(window.region, ledger)
    z = warp_native(paths, shape, affine, crs); _, projected = window_geometry(window.south, window.west, crs); report = burn([projected], shape, affine)
    geometries = [item[2] for item in projected_features(source_directory(window) / f"rgi_{window.region}.geojson", crs)]
    inside, proximity = estimator.vector_masks(geometries, shape, affine); pzi = warp_band(source_directory(window) / f"pzi_{window.region}.tif", shape, affine, crs)
    a, b, complete = estimator.plane_gradient(z, 90); weight = estimator.steepness_weight(np.hypot(a, b))
    masks = {"glacier_proximity": proximity, "permafrost": ~inside & np.isfinite(pzi) & (pzi >= 0.1)}
    common = dict(region=window.region, region_name=window.region_name, south=window.south, west=window.west,
        window_key=window.window_key, window_sha256=window.window_sha256, phase=phase, phase_x_m=PHASES[phase][0],
        phase_y_m=PHASES[phase][1], spacing_m=90, source_object_count=len(paths), missing_source_count=9-len(paths),
        report_cell_count=int(report.sum()), finite_dem_center_count=int((report & np.isfinite(z)).sum()),
        complete_support_center_count=int((report & complete).sum()))
    records = []
    for stratum, mask in masks.items():
        support, weighted, area = estimator.integrate(weight, report, mask, complete, 90); target = report & mask
        resolved = support_is_complete(stratum, report, inside, pzi, target, support)
        records.append(dict(common, stratum=stratum, stratum_center_count=int(target.sum()),
            integration_center_count=int(support.sum()), support_status="complete" if resolved else "unresolved",
            weighted_cell_sum=float(weighted) if resolved else np.nan, equivalent_steep_area_m2=float(area) if resolved else np.nan))
    return records
def baseline(window):
    family = "scale_explicit_steep_area" if window.source_family == "area_convergence" else "scale_explicit_transfer"
    table = pd.read_csv(ROOT / "data" / family / "equivalent_area_long.csv", dtype={"region": str})
    return table[(table.region == window.region) & table.variant.isin(["p00", "r90"])][["stratum", "variant", "equivalent_steep_area_m2"]]
def departure(reference, value): return abs(value-reference)/reference if reference > 0 else (0.0 if value == 0 else np.nan)
def support_is_complete(stratum, report, inside, pzi, target, support):
    return int(support.sum()) == int(target.sum()) and (stratum != "permafrost" or np.isfinite(pzi[report & ~inside]).all())
def comparison_records(native, windows):
    records = []
    for window in windows.itertuples(index=False):
        base, group = baseline(window), native[native.region == window.region]
        for stratum in ["glacier_proximity", "permafrost"]:
            known = base[base.stratum == stratum].set_index("variant").equivalent_steep_area_m2; phases = group[group.stratum == stratum].set_index("phase")
            ordered = phases.loc[list(PHASES)]; areas = ordered.equivalent_steep_area_m2.to_numpy(float); resolved = ordered.support_status.eq("complete").all() and np.isfinite(areas).all()
            reference, aggregate, primary = float(known.p00), float(known.r90), float(areas[0]); mean = float(np.mean(areas)) if resolved else np.nan
            structural = resolved and reference == 0 and aggregate == 0 and np.all(areas == 0)
            records.append(dict(region=window.region, region_name=window.region_name, stratum=stratum,
                reference_glo30_p00_m2=reference, aggregated_glo30_r90_m2=aggregate,
                aggregated_glo30_departure=departure(reference, aggregate), native_glo90_n00_m2=primary,
                native_glo90_departure=departure(reference, primary) if resolved else np.nan, native_phase_mean_m2=mean,
                native_phase_cv=0.0 if structural else (float(np.std(areas)/mean) if resolved and mean > 0 else np.nan),
                primary_finite_center_fraction=float(ordered.loc["n00"].finite_dem_center_count/ordered.loc["n00"].report_cell_count),
                primary_complete_support_fraction=float(ordered.loc["n00"].complete_support_center_count/ordered.loc["n00"].report_cell_count),
                native_support_status="complete" if resolved else "unresolved", structural_zero="yes" if structural else "no",
                zero_reference_positive_comparison="yes" if resolved and reference == 0 and (aggregate > 0 or np.any(areas > 0)) else "no",
                interpretation="exposed_window_native_source_development_no_pass_label"))
    return records
def schema_frame(records, schema):
    names = [x["name"] for x in schema["columns"]]; frame = pd.DataFrame(records)
    if set(frame.columns) != set(names) or len(frame) != schema["rows"]: raise ValueError("output schema or row count differs")
    return frame[names].astype({x["name"]: x["dtype"] for x in schema["columns"]})
def calculate(manifest, approved_sha256):
    pre, ledger = verify_raw(manifest, approved_sha256); windows = pd.read_csv(WINDOWS, dtype={"region": str}); records = []
    for window in windows.itertuples(index=False):
        for phase in PHASES: records.extend(phase_records(window, phase, ledger))
    long = schema_frame(records, pre["schemas"]["equivalent_area_long"])
    comparisons = schema_frame(comparison_records(long, windows), pre["schemas"]["comparisons"])
    long.to_csv(OUT / "equivalent_area_long.csv", index=False, lineterminator="\n"); comparisons.to_csv(OUT / "comparisons.csv", index=False, lineterminator="\n")
    print(f"wrote {len(long)} development rows and {len(comparisons)} comparisons; no pass label")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--raw-manifest", type=Path, required=True); parser.add_argument("--raw-manifest-sha256", required=True)
    args = parser.parse_args(); calculate(args.raw_manifest, args.raw_manifest_sha256)

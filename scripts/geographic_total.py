#!/usr/bin/env python3
"""Execute the frozen terrain functional and stratified inference atomically."""
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np, pandas as pd, rasterio, pyproj, shapely
from affine import Affine
from pyproj import Transformer
from scipy.stats import t
from shapely import make_valid
from shapely.geometry import shape
from shapely.ops import transform
from shapely.validation import explain_validity
import scripts.scale_explicit_steep_area as estimator
from scripts.denominator_pilot import aggregate_3x3, burn, warp_band, window_geometry
from scripts.geographic_sample import polygon_area_m2
from scripts.geographic_total_source import (OUTPUT, SOURCE, cell_label, cells, dem_paths,
                                             expected_dem_ids, grid)
from scripts.susceptible_area_convergence import PHASES, local_crs
ROOT = Path(__file__).resolve().parents[1]
HASHES = {"scripts/scale_explicit_steep_area.py": "15f7bff92b7ae44e5f64eac0db70598eb0f318f9a6ac5e2e689e5de9bc89e231",
          "scripts/denominator_pilot.py": "5f733147434f859ea3cbfc815da77a1bd8ae83137d80e59a65243d6d3e23508a",
          "scripts/susceptible_area_convergence.py": "9ac2644257ce1ba90bd8f2edbc6e9b47ea152fa02304b0c4b994e495a512b20c",
          "scripts/scale_explicit_transfer_source.py": "c495d3b587e40ed6ad036a24857dc6fb6ee4bb0934e0c385d82e8bd7ba259830",
          "scripts/geographic_sample.py": "21bb6d250f67aa55c42f8efabe3302a2a0a045c950f1455805e2e0ba2cb4faaa",
          "data/geographic_sample/frame.csv": "482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879",
          "data/geographic_sample/sample.csv": "1e9164813893e285aeeeaa1a7833e16c87172cbe4d3357e245854ab13966613b"}
REPAIR_RELATIVE_TOLERANCE = 1e-8
def admissible_repair(g, p, q): return g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty and g.is_valid and max(p, q) <= REPAIR_RELATIVE_TOLERANCE
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(manifest=None):
    for name, expected in HASHES.items():
        if digest(ROOT / name) != expected: raise ValueError(f"frozen file differs: {name}")
    if manifest:
        for name, expected in json.loads(Path(manifest).read_text())["files"].items():
            path = ROOT / name
            if (path.stat().st_size, digest(path)) != (expected["bytes"], expected["sha256"]):
                raise ValueError(f"source freeze differs: {name}")
def population():
    return pd.read_csv(ROOT / "data/geographic_sample/frame.csv", dtype={"dominant_region": str}).groupby("dominant_region").size()
def windows():
    table = cells().copy()
    table["region"] = [cell_label(s, w) for s, w in zip(table.south, table.west)]
    table["region_name"], table["key"], table["digest"] = (
        table.dominant_region, table.cell_key, table.random_digest)
    return table
def layers(_, south, west, variant):
    source_variant = "p00" if variant == "r90" else variant
    expected_shape, expected_affine, crs = grid(south, west, source_variant)
    label = cell_label(south, west)
    with rasterio.open(SOURCE / f"dem_{label}_{source_variant}.tif") as dataset:
        z = dataset.read(1, masked=True).filled(np.nan).astype(np.float32)
        affine = dataset.transform
        if z.shape != expected_shape or affine != expected_affine or dataset.crs != crs:
            raise ValueError(f"{label} {source_variant}: grid identity differs")
    spacing = 30
    if variant == "r90": z, affine, spacing = aggregate_3x3(z), affine * Affine.scale(3), 90
    window_wgs, projected = window_geometry(south, west, crs)
    report = burn([projected], z.shape, affine)
    pzi = warp_band(SOURCE / f"pzi_{label}.tif", z.shape, affine, crs)
    return z, affine, report, None, pzi, spacing, window_wgs
def projected_geometries(cell):
    collection = json.loads((SOURCE / f"rgi_{cell.region}.geojson").read_text())
    crs = local_crs(cell.south, cell.west)
    forward = Transformer.from_crs(4326, crs, always_xy=True).transform
    inverse = Transformer.from_crs(crs, 4326, always_xy=True).transform
    geometries, repairs = [], []
    for feature in collection["features"]:
        geographic = shape(feature["geometry"]); projected = transform(forward, geographic)
        if not projected.is_valid:
            before_p, before_g, reason = projected.area, polygon_area_m2(geographic), explain_validity(projected)
            repaired = make_valid(projected, method="linework")
            after_g = polygon_area_m2(transform(inverse, repaired))
            relative_p = abs(repaired.area - before_p) / before_p
            relative_g = abs(after_g - before_g) / before_g
            if not admissible_repair(repaired, relative_p, relative_g):
                raise ValueError(f"projection repair failed: {feature['properties']['rgi_id']}")
            repairs.append({"cell_key": cell.key, "rgi_id": feature["properties"]["rgi_id"],
                            "reason": reason, "input_type": projected.geom_type,
                            "output_type": repaired.geom_type, "projected_area_before_m2": before_p,
                            "projected_area_after_m2": repaired.area, "projected_relative_change": relative_p,
                            "geodesic_area_before_m2": before_g, "geodesic_area_after_m2": after_g,
                            "geodesic_relative_change": relative_g, "original_valid": False, "output_valid": repaired.is_valid,
                            "shapely_version": shapely.__version__,
                            "geos_version": shapely.geos_version_string, "proj_version": pyproj.__proj_version__,
                            "projected_crs_wkt": crs.to_wkt()})
            projected = repaired
        geometries.append(projected)
    return geometries, repairs
def coverage_estimates(coverage):
    records, populations = [], population()
    definitions = [("dem", "complete_dem_support_count", "report_center_count"),
                   ("rgi_predicate", "glacier_predicate_coverage_count", "report_center_count"),
                   ("pzi", "outside_RGI_finite_PZI_count", "outside_RGI_center_count")]
    for variant, group in coverage.groupby("variant", sort=False):
        for dimension, numerator, denominator in definitions:
            values = np.where(group[denominator] == 0, 1., group[numerator] / group[denominator])
            temporary = group.assign(q=values, covered=group[numerator] * group.spacing_m**2,
                                     base=group[denominator] * group.spacing_m**2)
            mean_total = variance = covered = base = 0.
            for _, h in temporary.groupby("dominant_region"):
                N, n = int(populations.loc[h.dominant_region.iloc[0]]), len(h)
                if N != int(h.stratum_population_cells.iloc[0]) or n != int(h.stratum_sample_cells.iloc[0]): raise ValueError("coverage design identity differs")
                mean_total += N * h.q.mean(); variance += N**2 * (1-n/N) * h.q.var(ddof=1) / n
                covered += N * h.covered.mean(); base += N * h.base.mean()
            records.append({"variant": variant, "dimension": dimension,
                            "mean_cell_coverage_fraction": mean_total / 1826,
                            "mean_cell_variance": variance / 1826**2,
                            "expanded_covered_area_m2": covered, "expanded_denominator_area_m2": base,
                            "expanded_area_coverage_ratio": covered / base if base else 1.})
    return pd.DataFrame(records)
def write_coverage():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows, repairs = [], []
    for cell in windows().itertuples(index=False):
        geometries, fixed = projected_geometries(cell); repairs.extend(fixed)
        for variant in (*PHASES, "r90"):
            z, affine, report, _, pzi, spacing, _ = layers(None, cell.south, cell.west, variant)
            complete = estimator.plane_gradient(z, spacing)[2]
            inside, proximity = estimator.vector_masks(geometries, z.shape, affine)
            outside = report & ~inside
            row = {"cell_key": cell.key, "dominant_region": cell.dominant_region,
                   "stratum_population_cells": cell.stratum_population_cells,
                   "stratum_sample_cells": cell.stratum_sample_cells, "variant": variant,
                   "spacing_m": spacing, "report_center_count": int(report.sum()),
                   "source_object_count": len(dem_paths(cell.south, cell.west)),
                   "missing_object_ids": json.dumps(sorted(set(expected_dem_ids(cell.south, cell.west)) -
                                                            {path.stem for path in dem_paths(cell.south, cell.west)})),
                   "complete_dem_support_count": int((report & complete).sum()),
                   "glacier_predicate_coverage_count": int(report.sum()),
                   "glacier_proximity_center_count": int((report & proximity).sum()),
                   "glacier_proximity_complete_dem_count": int((report & proximity & complete).sum()),
                   "outside_RGI_center_count": int(outside.sum()),
                   "outside_RGI_finite_PZI_count": int((outside & np.isfinite(pzi)).sum()),
                   "PZI_mask_center_count": int((outside & np.isfinite(pzi) & (pzi >= .1)).sum()),
                   "PZI_mask_complete_dem_count": int((outside & np.isfinite(pzi) & (pzi >= .1) & complete).sum())}
            if (not row["complete_dem_support_count"] or
                    row["glacier_predicate_coverage_count"] != row["report_center_count"] or
                    (row["outside_RGI_center_count"] and not row["outside_RGI_finite_PZI_count"])):
                raise ValueError(f"uncomputable source coverage: {cell.key} {variant}")
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "source_coverage.csv", index=False, lineterminator="\n")
    coverage_estimates(table).to_csv(OUTPUT / "coverage_estimates.csv", index=False, lineterminator="\n")
    repair_columns = ["cell_key", "rgi_id", "reason", "input_type", "output_type",
                      "projected_area_before_m2", "projected_area_after_m2", "projected_relative_change",
                      "geodesic_area_before_m2", "geodesic_area_after_m2", "geodesic_relative_change", "original_valid", "output_valid",
                      "shapely_version", "geos_version", "proj_version", "projected_crs_wkt"]
    pd.DataFrame(repairs, columns=repair_columns).to_csv(OUTPUT / "projection_repairs.csv", index=False, lineterminator="\n")
def diagnostics(records, coverage):
    rows = []; source = cells().set_index("cell_key")
    for (key, stratum), group in records.groupby(["window_key", "stratum"], sort=False):
        values = group.set_index("variant").equivalent_steep_area_m2
        if len(values) != 5 or not np.isfinite(values).all() or (values < 0).any(): raise ValueError(f"uncomputable outcome: {key} {stratum}")
        reference, structural = float(values.p00), bool((values == 0).all())
        phases = values.loc[list(PHASES)].to_numpy(float); mean = phases.mean()
        departure = abs(float(values.r90)-reference)/reference if reference > 0 else np.nan
        cv = 0. if structural else float(np.std(phases)/mean) if mean > 0 else np.nan
        center = "glacier_proximity_center_count" if stratum == "glacier_proximity" else "PZI_mask_center_count"
        supported = "glacier_proximity_complete_dem_count" if stratum == "glacier_proximity" else "PZI_mask_complete_dem_count"
        related = coverage[coverage.cell_key == key]
        if len(related) != 5: raise ValueError(f"incomplete coverage: {key}")
        limited = structural and any(related[supported] < related[center])
        if stratum == "permafrost": limited |= structural and any(related.outside_RGI_finite_PZI_count < related.outside_RGI_center_count)
        meta = source.loc[key]
        rows.append({"cell_key": key, "dominant_region": meta.dominant_region,
                     "stratum_population_cells": meta.stratum_population_cells,
                     "stratum_sample_cells": meta.stratum_sample_cells, "inclusion_probability": meta.inclusion_probability,
                     "stratum": stratum, "reference_equivalent_area_m2": reference,
                     "area_90m_m2": float(values.r90), "departure_90m": departure, "phase_cv": cv,
                     "structural_zero": "yes" if structural else "no",
                    "coverage_limited_zero": "yes" if limited else "no",
                    "adequate_coverage_zero": "yes" if structural and not limited else "no",
                    "zero_reference_positive_variant": "yes" if reference == 0 and (values > 0).any() else "no",
                    "cell_quality_pass": "yes" if reference > 0 and departure <= .2 and cv <= .1 else "no",
                    "usable_transfer": "yes" if reference > 0 and departure <= .2 and cv <= .1 else "no"})
    return pd.DataFrame(rows)
def estimates(primary):
    strata, covariance, totals, populations = [], [], [], population()
    for outcome, group in primary.groupby("stratum", sort=False):
        for region, h in group.groupby("dominant_region"):
            N, n = int(populations.loc[region]), len(h); y = h.reference_equivalent_area_m2
            if N != int(h.stratum_population_cells.iloc[0]) or n != int(h.stratum_sample_cells.iloc[0]) or not np.allclose(n / h.inclusion_probability, N):
                raise ValueError(f"design identity differs: {region}")
            s2 = y.var(ddof=1); variance = N**2 * (1-n/N) * s2/n
            strata.append({"stratum": outcome, "dominant_region": region, "N_h": N, "n_h": n,
                           "sample_mean_m2": y.mean(), "estimated_total_m2": N*y.mean(),
                           "sample_variance_m4": s2, "variance_contribution_m4": variance})
        selected = pd.DataFrame(strata)[lambda x: x.stratum == outcome]
        total, variance = selected.estimated_total_m2.sum(), selected.variance_contribution_m4.sum()
        if not np.isfinite([total, variance]).all() or total < 0 or variance < 0: raise ValueError("invalid estimate")
        df = variance**2 / sum(row.variance_contribution_m4**2/(row.n_h-1) for row in selected.itertuples() if row.variance_contribution_m4 > 0) if variance > 0 else math.inf
        se = math.sqrt(variance); critical = t.ppf(.975, df) if math.isfinite(df) else 1.96
        rse = se/total if total > 0 else np.nan
        totals.append({"stratum": outcome, "estimated_total_m2": total, "SE_m2": se, "RSE": rse,
                       "estimated_mean_m2_per_cell": total/1826,
                       "degrees_of_freedom": df, "CI_lower_m2": total-critical*se,
                       "CI_upper_m2": total+critical*se,
                       "precision_pass": "yes" if np.isfinite(rse) and 0 < rse <= .25 else "no",
                       "numerical_quality_pass": "yes" if (group.cell_quality_pass == "yes").all() else "no"})
    wide = primary.pivot(index="cell_key", columns="stratum", values="reference_equivalent_area_m2")
    meta = primary.drop_duplicates("cell_key").set_index("cell_key")
    for region, keys in meta.groupby("dominant_region").groups.items():
        N, n = int(populations.loc[region]), len(keys)
        sample_cov = wide.loc[list(keys)].cov(ddof=1).iloc[0, 1]
        covariance.append({"dominant_region": region, "N_h": N, "n_h": n,
                           "sample_covariance_m4": sample_cov,
                           "covariance_contribution_m4": N**2*(1-n/N)*sample_cov/n})
    joint = "yes" if all(item["numerical_quality_pass"] == "yes" for item in totals) else "no"
    for item in totals: item["joint_numerical_quality_pass"] = joint
    return pd.DataFrame(strata), pd.DataFrame(covariance), pd.DataFrame(totals)
def execute(manifest):
    if manifest is None: raise ValueError("execute requires a source manifest")
    verify(manifest); estimator.variant_layers = layers; rows = []
    for cell in windows().itertuples(index=False):
        geometries, _ = projected_geometries(cell)
        for variant in (*PHASES, "r90"): rows.extend(estimator.variant_records(cell, variant, geometries))
    records = pd.DataFrame(rows)
    if len(records) != 960: raise ValueError("incomplete atomic result")
    coverage = pd.read_csv(OUTPUT / "source_coverage.csv")
    primary = diagnostics(records, coverage); strata, covariance, totals = estimates(primary)
    if (len(primary), len(strata), len(covariance), len(totals)) != (192, 38, 19, 2): raise ValueError("output identity differs")
    temporary = OUTPUT / ".equivalent_area_long.csv.tmp"
    records.to_csv(temporary, index=False, lineterminator="\n"); temporary.replace(OUTPUT / "equivalent_area_long.csv")
    for name, table in [("cell_outcomes.csv", primary),
                        ("stratum_estimates.csv", strata), ("stratum_covariance.csv", covariance),
                        ("total_estimates.csv", totals)]:
        table.to_csv(OUTPUT / name, index=False, lineterminator="\n")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["coverage", "execute"])
    parser.add_argument("--manifest", type=Path); args = parser.parse_args()
    if args.manifest is None: raise ValueError("coverage and execution require a source manifest")
    verify(args.manifest); write_coverage() if args.action == "coverage" else execute(args.manifest)

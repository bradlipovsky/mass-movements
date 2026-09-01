#!/usr/bin/env python3
"""Develop a nominal-support equivalent steep-area measure on exposed windows."""
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import binary_erosion, correlate
from shapely import dwithin, intersects_xy, points, prepare, union_all

from scripts.denominator_pilot import load_features
from scripts.susceptible_area_convergence import (
    PHASES,
    SOURCE,
    local_crs,
    variant_layers,
)

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "data" / "area_convergence"
OUTPUT = ROOT / "data" / "scale_explicit_steep_area"
RADIUS_M = 300
CONTACT_M = 100
RAMP_DEG = (25, 35)


def disk_offsets(spacing):
    """Return the registered center stencil within the nominal-radius disk."""
    reach = math.ceil(RADIUS_M / spacing)
    rows, columns = np.mgrid[-reach:reach + 1, -reach:reach + 1]
    u, v = columns * spacing, -rows * spacing
    disk = u * u + v * v <= RADIUS_M**2
    return u, v, disk


def plane_gradient(z, spacing):
    """Fit signed local-plane gradients with strict full-disk support."""
    u, v, disk = disk_offsets(spacing)
    ku = np.where(disk, u / np.sum(u[disk] ** 2), 0.0)
    kv = np.where(disk, v / np.sum(v[disk] ** 2), 0.0)
    finite = np.isfinite(z)
    complete = binary_erosion(finite, structure=disk, border_value=0)
    filled = np.where(finite, z, 0.0).astype(np.float64)
    a = correlate(filled, ku, mode="constant", cval=0.0)
    b = correlate(filled, kv, mode="constant", cval=0.0)
    a[~complete] = np.nan
    b[~complete] = np.nan
    return a, b, complete


def steepness_weight(gradient):
    """Map surface-gradient magnitude to the fixed 25--35 degree ramp."""
    q25, q35 = np.tan(np.radians(RAMP_DEG))
    return np.clip((gradient - q25) / (q35 - q25), 0.0, 1.0)


def center_coordinates(shape, affine):
    """Return broadcastable target-cell center coordinates."""
    x = affine.c + (np.arange(shape[1]) + 0.5) * affine.a
    y = affine.f + (np.arange(shape[0]) + 0.5) * affine.e
    return x[None, :], y[:, None]


def vector_masks(geometries, shape, affine):
    """Evaluate exact closed-distance glacier proximity in bounded row chunks."""
    if not geometries or any(geometry.is_empty or not geometry.is_valid for geometry in geometries):
        raise ValueError("projected glacier geometry is empty or invalid")
    glacier = union_all(geometries)
    if glacier.is_empty or not glacier.is_valid:
        raise ValueError("projected glacier union is empty or invalid")
    prepare(glacier)
    x, y = center_coordinates(shape, affine)
    inside, proximity = np.empty(shape, bool), np.empty(shape, bool)
    for start in range(0, shape[0], 256):
        rows = slice(start, min(start + 256, shape[0]))
        inside[rows] = intersects_xy(glacier, x, y[rows])
        proximity[rows] = dwithin(glacier, points(x, y[rows]), CONTACT_M) & ~inside[rows]
    return inside, proximity


def integrate(weight, report, mask, complete, spacing):
    """Integrate dimensionless steepness weight over projected cell area."""
    support = report & mask & complete
    weighted_cells = float(np.sum(weight[support], dtype=np.float64))
    return support, weighted_cells, weighted_cells * spacing**2


def variant_records(window, variant, geometries):
    """Calculate both registered strata for one exposed grid variant."""
    z, affine, report, _, pzi, spacing, _ = variant_layers(
        window.region, window.south, window.west, variant
    )
    a, b, complete = plane_gradient(z, spacing)
    weight = steepness_weight(np.hypot(a, b))
    inside, proximity = vector_masks(geometries, z.shape, affine)
    masks = {
        "glacier_proximity": proximity,
        "permafrost": ~inside & np.isfinite(pzi) & (pzi >= 0.1),
    }
    phase_x, phase_y = (0, 0) if variant == "r90" else PHASES[variant]
    common = dict(
        region=window.region, region_name=window.region_name,
        south=window.south, west=window.west, window_key=window.key,
        window_sha256=window.digest, variant=variant, spacing_m=spacing,
        phase_x_m=phase_x, phase_y_m=phase_y, support_radius_m=RADIUS_M,
        ramp_lower_deg=RAMP_DEG[0], ramp_upper_deg=RAMP_DEG[1],
        report_cell_count=int(report.sum()), support_disk_cell_count=int(disk_offsets(spacing)[2].sum()),
        complete_support_cell_count=int((report & complete).sum()),
    )
    rows = []
    for stratum, mask in masks.items():
        support, weighted_cells, area = integrate(weight, report, mask, complete, spacing)
        rows.append(dict(
            common, stratum=stratum,
            mask_definition=("outside_inventory_glacier_planar_distance_le_100m" if stratum == "glacier_proximity"
                             else "outside_glacier_pzi_ge_0.1"),
            stratum_center_count=int((report & mask).sum()),
            integration_cell_count=int(support.sum()), weighted_cell_sum=weighted_cells,
            equivalent_steep_area_m2=area,
        ))
    return rows


def comparisons(records, hard):
    """Attach reference ratios and exposed-window diagnostics without pass labels."""
    records = records.copy()
    for column in ("reference_equivalent_area_m2", "area_ratio", "fractional_departure"):
        records[column] = np.nan
    records["structural_zero"] = "no"
    diagnostics = []
    for (region, stratum), indices in records.groupby(["region", "stratum"]).groups.items():
        group = records.loc[indices]
        by_variant = group.set_index("variant").equivalent_steep_area_m2
        reference = float(by_variant.p00)
        records.loc[indices, "reference_equivalent_area_m2"] = reference
        if reference > 0:
            records.loc[indices, "area_ratio"] = group.equivalent_steep_area_m2 / reference
            records.loc[indices, "fractional_departure"] = (
                group.equivalent_steep_area_m2.sub(reference).abs() / reference
            )
        elif (by_variant == 0).all():
            records.loc[indices, "fractional_departure"] = 0.0
            records.loc[indices, "structural_zero"] = "yes"
        phases = by_variant.loc[list(PHASES)].to_numpy(dtype=float)
        structural_zero = bool(np.all(by_variant == 0))
        phase_mean = float(np.mean(phases))
        phase_cv = (0.0 if structural_zero else
                    float(np.std(phases) / phase_mean) if phase_mean > 0 else np.nan)
        hard_stratum = "glacier_contact" if stratum == "glacier_proximity" else stratum
        hard_departure = float(hard[(hard.region == region) & (hard.stratum == hard_stratum)].departure_90m.iloc[0])
        diagnostics.append(dict(
            region=region, stratum=stratum, reference_equivalent_area_m2=reference,
            area_90m_m2=float(by_variant.r90), departure_90m=(abs(float(by_variant.r90) - reference) / reference
                                                               if reference > 0 else np.nan),
            phase_mean_area_m2=phase_mean, phase_cv=phase_cv,
            structural_zero="yes" if structural_zero else "no",
            zero_reference_positive_variant="yes" if reference == 0 and np.any(by_variant > 0) else "no",
            hard_threshold_departure_90m=hard_departure,
            reference_departure_bound=0.20, reference_phase_cv_bound=0.10,
            interpretation="exposed_window_method_development_no_pass_label",
        ))
    return records, pd.DataFrame(diagnostics)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    windows = pd.read_csv(AREA / "windows.csv", dtype={"region": str})
    rows = []
    for window in windows.itertuples(index=False):
        crs = local_crs(window.south, window.west)
        geometries = [item[2] for item in load_features(SOURCE / f"rgi_{window.region}.geojson", crs)]
        for variant in (*PHASES, "r90"):
            rows.extend(variant_records(window, variant, geometries))
    hard = pd.read_csv(AREA / "decisions.csv", dtype={"region": str})
    records, diagnostics = comparisons(pd.DataFrame(rows), hard)
    records.to_csv(OUTPUT / "equivalent_area_long.csv", index=False, lineterminator="\n")
    diagnostics.to_csv(OUTPUT / "diagnostics.csv", index=False, lineterminator="\n")
    print(f"wrote {len(records)} equivalent-area rows and {len(diagnostics)} diagnostics")


if __name__ == "__main__":
    main()

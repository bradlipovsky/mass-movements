#!/usr/bin/env python3
"""Test susceptible-area convergence without case or climate inputs."""
import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine

from scripts.denominator_pilot import (
    aggregate_3x3,
    burn,
    contact_distance,
    load_features,
    local_crs,
    slope_degrees,
    warp_band,
    window_geometry,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "area_convergence"
SOURCE = OUTPUT / "source"
PHASES = {"p00": (0, 0), "p10": (15, 0), "p01": (0, 15), "p11": (15, 15)}


def rank_regions(regions):
    """Rank literal region keys by their registered SHA-256 digest."""
    rows = []
    for region in regions:
        key = f"susceptible-area-heldout-v1|{region}"
        rows.append((hashlib.sha256(key.encode()).hexdigest(), region, key))
    return sorted(rows)


def eligible_windows(rows, region):
    """Return the complete registered RGI window universe in digest order."""
    cells = {}
    for row in rows:
        lon = (float(row["cenlon"]) + 180) % 360 - 180
        cell = math.floor(float(row["cenlat"])), math.floor(lon)
        cells.setdefault(cell, []).append(float(row["area_km2"]))
    eligible = []
    for (south, west), areas in cells.items():
        area = math.fsum(areas)
        if len(areas) >= 10 and area >= 1:
            key = f"rgi7.0|{region}|south={south:+03d}|west={west:+04d}"
            digest = hashlib.sha256(
                f"susceptible-area-heldout-window-v1|{key}".encode()
            ).hexdigest()
            eligible.append((digest, key, south, west, len(areas), area))
    if not eligible:
        raise ValueError(f"region {region} has no eligible window")
    return sorted(eligible)


def phase_grid(bounds, dx=0, dy=0, multiple=1):
    """Cover projected bounds on a translated 30 m lattice."""
    xmin, ymin, xmax, ymax = bounds
    x0 = math.floor((xmin - dx) / 30) * 30 + dx
    y0 = math.floor((ymin - dy) / 30) * 30 + dy
    width = math.ceil((xmax - x0) / 30)
    height = math.ceil((ymax - y0) / 30)
    width += (-width) % multiple
    height += (-height) % multiple
    return (height, width), Affine(30, 0, x0, 0, -30, y0 + 30 * height)


def variant_layers(region, south, west, variant):
    """Load one independently warped DEM phase or its aligned 90 m mean."""
    crs = local_crs(south, west)
    window_wgs, window_laea = window_geometry(south, west, crs)
    features = load_features(SOURCE / f"rgi_{region}.geojson", crs)
    source_variant = "p00" if variant == "r90" else variant
    with rasterio.open(SOURCE / f"dem_{region}_{source_variant}_30m.tif") as dataset:
        z = dataset.read(1, masked=True).filled(np.nan).astype(np.float32)
        affine = dataset.transform
        if dataset.crs != crs or dataset.res != (30, 30):
            raise ValueError(f"region {region} {source_variant} grid metadata differs")
    dx, dy = PHASES[source_variant]
    expected = phase_grid(window_laea.buffer(1000).bounds, dx, dy,
                          3 if source_variant == "p00" else 1)
    if z.shape != expected[0] or affine != expected[1]:
        raise ValueError(f"region {region} {source_variant} grid anchor differs")
    spacing = 30
    if variant == "r90":
        z, affine, spacing = aggregate_3x3(z), affine * Affine.scale(3), 90
    glaciers = burn((item[2] for item in features), z.shape, affine)
    report = burn([window_laea], z.shape, affine)
    pzi = warp_band(SOURCE / f"pzi_{region}.tif", z.shape, affine, crs)
    return z, affine, report, glaciers, pzi, spacing, window_wgs


def area_records(window, variant):
    """Calculate every registered aggregate area for one grid variant."""
    region, south, west = window.region, int(window.south), int(window.west)
    z, _, report, glaciers, pzi, spacing, _ = variant_layers(
        region, south, west, variant
    )
    slope = slope_degrees(z, spacing)
    rock = report & np.isfinite(slope) & ~glaciers
    distance = contact_distance(glaciers, spacing)
    phase_x, phase_y = (0, 0) if variant == "r90" else PHASES[variant]
    common = dict(
        region=region,
        region_name=window.region_name,
        south=south,
        west=west,
        window_key=window.key,
        window_sha256=window.digest,
        variant=variant,
        spacing_m=spacing,
        phase_x_m=phase_x,
        phase_y_m=phase_y,
        report_cell_count=int(report.sum()),
    )
    records = []
    for threshold in (25, 30, 35):
        steep = rock & (slope >= threshold)
        for contact in (0, 100, 300):
            susceptible = steep & (distance <= contact)
            records.append(area_record(common, "glacier_contact", threshold,
                                       contact, np.nan, rock, susceptible))
        pzi_valid = rock & np.isfinite(pzi)
        for pzi_min in (0.1, 0.5):
            susceptible = steep & pzi_valid & (pzi >= pzi_min)
            records.append(area_record(common, "permafrost", threshold,
                                       np.nan, pzi_min, pzi_valid, susceptible))
    return records


def area_record(common, stratum, slope, contact, pzi_min, valid, susceptible):
    cells = int(valid.sum())
    susceptible_cells = int(susceptible.sum())
    area = common["spacing_m"] ** 2
    return dict(
        common,
        stratum=stratum,
        slope_deg=slope,
        contact_m=contact,
        pzi_min=pzi_min,
        valid_source_cell_count=cells,
        valid_source_area_m2=cells * area,
        coverage_fraction=cells / common["report_cell_count"],
        susceptible_cell_count=susceptible_cells,
        susceptible_area_m2=susceptible_cells * area,
    )


def comparisons(records):
    """Attach same-threshold reference ratios and fixed convergence decisions."""
    keys = ["region", "stratum", "slope_deg", "contact_m", "pzi_min"]
    records = records.copy()
    records["reference_area_m2"] = np.nan
    records["area_ratio"] = np.nan
    records["fractional_departure"] = np.nan
    records["structural_zero"] = "no"
    for _, indices in records.groupby(keys, dropna=False).groups.items():
        group = records.loc[indices]
        reference = float(group.loc[group.variant == "p00", "susceptible_area_m2"].iloc[0])
        records.loc[indices, "reference_area_m2"] = reference
        if reference > 0:
            records.loc[indices, "area_ratio"] = group.susceptible_area_m2 / reference
            records.loc[indices, "fractional_departure"] = (
                group.susceptible_area_m2.sub(reference).abs() / reference
            )
        elif (group.susceptible_area_m2 == 0).all():
            records.loc[indices, "fractional_departure"] = 0.0
            records.loc[indices, "structural_zero"] = "yes"
    primary = records[(records.slope_deg == 30) &
                      (((records.stratum == "glacier_contact") & (records.contact_m == 100)) |
                       ((records.stratum == "permafrost") & (records.pzi_min == 0.1)))]
    decisions = []
    for (region, stratum), group in primary.groupby(["region", "stratum"]):
        by_variant = group.set_index("variant").susceptible_area_m2
        reference, area90 = float(by_variant.p00), float(by_variant.r90)
        phases = by_variant.loc[list(PHASES)].to_numpy(dtype=float)
        structural_zero = bool(np.all(by_variant.to_numpy() == 0))
        zero_positive = bool(reference == 0 and np.any(by_variant.to_numpy() > 0))
        departure = 0.0 if structural_zero else (
            abs(area90 - reference) / reference if reference > 0 else np.nan
        )
        phase_cv = 0.0 if structural_zero else (
            float(np.std(phases, ddof=0) / np.mean(phases)) if np.mean(phases) > 0 else np.nan
        )
        resolution_pass = bool(np.isfinite(departure) and departure <= 0.20)
        phase_pass = bool(np.isfinite(phase_cv) and phase_cv <= 0.10)
        decisions.append(dict(
            region=region, stratum=stratum, reference_area_m2=reference,
            area_90m_m2=area90, departure_90m=departure,
            phase_mean_area_m2=float(np.mean(phases)), phase_cv=phase_cv,
            structural_zero="yes" if structural_zero else "no",
            zero_reference_positive_variant="yes" if zero_positive else "no",
            resolution_pass="yes" if resolution_pass else "no",
            phase_pass="yes" if phase_pass else "no",
            window_pass="yes" if resolution_pass and phase_pass and not zero_positive else "no",
        ))
    decisions = pd.DataFrame(decisions)
    passed = decisions.groupby("stratum").window_pass.transform(lambda x: (x == "yes").all())
    decisions["stratum_pass"] = np.where(passed, "yes", "no")
    return records, decisions


def main():
    windows = pd.read_csv(OUTPUT / "windows.csv", dtype={"region": str})
    rows = []
    for window in windows.itertuples(index=False):
        for variant in (*PHASES, "r90"):
            rows.extend(area_records(window, variant))
    records, decisions = comparisons(pd.DataFrame(rows))
    records.to_csv(OUTPUT / "area_long.csv", index=False)
    decisions.to_csv(OUTPUT / "decisions.csv", index=False)
    print(f"wrote {len(records)} area rows and {len(decisions)} window decisions")


if __name__ == "__main__":
    main()

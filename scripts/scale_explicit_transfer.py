#!/usr/bin/env python3
"""Run the registered equivalent-area estimator on frozen blind windows."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine

import scripts.scale_explicit_steep_area as estimator
from scripts.denominator_pilot import aggregate_3x3, burn, load_features, warp_band, window_geometry
from scripts.susceptible_area_convergence import PHASES, local_crs, phase_grid

ROOT = Path(__file__).resolve().parents[1]
OUTPUT, SOURCE = ROOT / "data" / "scale_explicit_transfer", ROOT / "data" / "scale_explicit_transfer" / "source"
ESTIMATOR = ROOT / "scripts" / "scale_explicit_steep_area.py"
ESTIMATOR_SHA256 = "15f7bff92b7ae44e5f64eac0db70598eb0f318f9a6ac5e2e689e5de9bc89e231"


def verify_hashes(manifest=None):
    """Stop before access if estimator or frozen-file identity differs."""
    if hashlib.sha256(ESTIMATOR.read_bytes()).hexdigest() != ESTIMATOR_SHA256:
        raise ValueError("registered estimator bytes differ")
    if manifest:
        frozen = json.loads(Path(manifest).read_text())
        for name, expected in frozen["files"].items():
            raw = (ROOT / name).read_bytes()
            if (len(raw), hashlib.sha256(raw).hexdigest()) != (expected["bytes"], expected["sha256"]):
                raise ValueError(f"frozen file differs: {name}")


def transfer_layers(region, south, west, variant):
    """Generalize only the inherited source directory to frozen transfer data."""
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


def windows():
    table = pd.read_csv(OUTPUT / "windows.csv", dtype={"region": str})
    return table.rename(columns={"window_key": "key", "window_digest": "digest"})


def write_coverage():
    """Freeze reporting-center source coverage without estimating steep area."""
    rows = []
    for window in windows().itertuples(index=False):
        for variant in (*PHASES, "r90"):
            z, _, report, glacier, pzi, spacing, _ = transfer_layers(
                window.region, window.south, window.west, variant)
            rows.append(dict(region=window.region, variant=variant, spacing_m=spacing,
                             report_cell_count=int(report.sum()),
                             dem_finite_center_count=int((report & np.isfinite(z)).sum()),
                             pzi_finite_center_count=int((report & np.isfinite(pzi)).sum()),
                             glacier_predicate_coverage_count=int(report.sum()),
                             pzi_outside_glacier_coverage_count=int(
                                 (report & ~glacier & np.isfinite(pzi)).sum())))
    pd.DataFrame(rows).to_csv(OUTPUT / "source_coverage.csv", index=False, lineterminator="\n")


def attach_decisions(records):
    """Apply the registered zero rules and intersection-union gate."""
    records = records.copy()
    for name in ("reference_equivalent_area_m2", "area_ratio", "fractional_departure"):
        records[name] = np.nan
    records["structural_zero"] = "no"
    decisions = []
    for (region, stratum), indices in records.groupby(["region", "stratum"]).groups.items():
        group, by_variant = records.loc[indices], records.loc[indices].set_index("variant").equivalent_steep_area_m2
        reference, phases = float(by_variant.p00), by_variant.loc[list(PHASES)].to_numpy(float)
        structural = bool(np.all(by_variant.to_numpy() == 0))
        if reference > 0:
            records.loc[indices, "reference_equivalent_area_m2"] = reference
            records.loc[indices, "area_ratio"] = group.equivalent_steep_area_m2 / reference
            records.loc[indices, "fractional_departure"] = abs(group.equivalent_steep_area_m2 / reference - 1)
        elif structural:
            records.loc[indices, "structural_zero"] = "yes"
        departure = abs(float(by_variant.r90) / reference - 1) if reference > 0 else np.nan
        phase_cv = 0.0 if structural else float(np.std(phases) / np.mean(phases)) if np.mean(phases) > 0 else np.nan
        usable = reference > 0 and np.isfinite(departure) and np.isfinite(phase_cv)
        resolution, phase = usable and departure <= 0.20, usable and phase_cv <= 0.10
        decisions.append(dict(region=region, stratum=stratum, reference_equivalent_area_m2=reference,
                              area_90m_m2=float(by_variant.r90), departure_90m=departure,
                              phase_mean_area_m2=float(np.mean(phases)), phase_cv=phase_cv,
                              structural_zero="yes" if structural else "no",
                              zero_reference_positive_variant="yes" if reference == 0 and np.any(by_variant > 0) else "no",
                              usable_transfer="yes" if usable else "no",
                              resolution_pass="yes" if resolution else "no",
                              phase_pass="yes" if phase else "no",
                              window_pass="yes" if resolution and phase else "no"))
    return records, pd.DataFrame(decisions)


def main():
    verify_hashes(OUTPUT / "preoutput_manifest.json")
    estimator.variant_layers = transfer_layers
    rows = []
    for window in windows().itertuples(index=False):
        geometries = [item[2] for item in load_features(
            SOURCE / f"rgi_{window.region}.geojson", local_crs(window.south, window.west))]
        for variant in (*PHASES, "r90"):
            rows.extend(estimator.variant_records(window, variant, geometries))
    records, decisions = attach_decisions(pd.DataFrame(rows))
    strata = decisions.groupby("stratum").window_pass.apply(lambda x: "yes" if (x == "yes").all() else "no").rename("stratum_pass").reset_index()
    overall = pd.DataFrame([{"transfer_gate_pass": "yes" if (strata.stratum_pass == "yes").all() else "no"}])
    records.to_csv(OUTPUT / "equivalent_area_long.csv", index=False, lineterminator="\n")
    decisions.to_csv(OUTPUT / "decisions.csv", index=False, lineterminator="\n")
    strata.to_csv(OUTPUT / "stratum_decisions.csv", index=False, lineterminator="\n")
    overall.to_csv(OUTPUT / "overall_decision.csv", index=False, lineterminator="\n")
    print(f"completed all {len(records)} rows; transfer gate={overall.iloc[0, 0]}")


if __name__ == "__main__":
    verify_hashes()
    write_coverage() if sys.argv[1:] == ["--coverage-only"] else main()

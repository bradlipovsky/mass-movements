#!/usr/bin/env python3
"""Freeze and run source-verified, onset-aligned ERA5 temperature transfer."""
import argparse, hashlib, importlib.metadata, json, os, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reanalysis_pilot as pilot  # noqa: E402

OUT = ROOT / "data" / "audited_reanalysis"
RESULTS = OUT / "results"
SCHEMAS = OUT / "output_schemas.json"
SELECTED_DIGEST = "93ba0bbc451c5babb9de4081b87f493005b4920dbc1a871efa479f89aae03a08"
WINDOWS = {"2d": 48, "7d": 168, "30d": 720}
YEARS = range(1979, 2026)
UPSTREAM = {
    "data/candidates.csv": "8b6b0f972180e26c326aaa0e6a501080843bd4b6e6674b07c5aa009340c8a249",
    "data/candidate_clusters.csv": "fd1545d60fe527e9881ec9169cf9ee93dc94eab1470595641695d1bcf089f309",
    "data/event_audit/manifest.json": "3263706361aeeb828ad33b318b1b19076e4448e2ff098a40af6110d6d34f317e",
    "data/event_audit/summary.csv": "8e9f1e43851263591c3c72f908ea4e073f6a19faa6a01738a1e6b82db9bdd532",
    "data/event_audit/coordinate_assertions.csv": "33fb1ac22ccec77d8f5ffc9e928b75042cc91fbe08645a4be4ffd879fdc57874",
    "data/event_audit/time_assertions.csv": "adde3bdb573f17c1c4e31ccf404d467bcb466f4075be2db79f812264c8a4ae54",
    "data/event_audit/sources.csv": "8a8e3acc21c471afb2fed6111dd13537e360ba9350fe4349ecc23445e809cd47",
    "protocol/source-time-audit.md": "55c0790ffc84a9da74d92277f7b14e8ea5e2a3241377c6049a1c04be4d75a16a",
    "protocol/reanalysis-pilot.md": "4bfc97462392472c6a4ef164f4e1d1dd0757a0b8beef241d34c8568e7cf4c9c5",
    "requirements-reanalysis.txt": "3b6625e4d6db124da740ee50fe1409309c9f67a6db5f06ea89ee7496de83bed2",
    "scripts/reanalysis_pilot.py": "18b0aff924fd8a5b3bcdad88a92c63b8b056c10d3aacdc39657939d61342ce5c",
    "tests/test_reanalysis_pilot.py": "2682448631a0dc61efce320fb5b663cb7bc01186af08894905e648c63e0bd07b",
    "data/reanalysis/retrieval_manifest.json": "a72e652b8f088a14cc939502a560981d87b9155cb98ee718dc45ed4e94fee6a1",
    "data/reanalysis/event_cells.csv": "d07cd42f4a953322d8c3c97070ba2ad436986b3ab7399e2ecb1f0ba0a5cf640e",
    "data/reanalysis/matched_windows.csv": "8c8e2f2484f8b5cae6a51f92abb17d2ff7bb90f06e54ef941c1eda8ca4b3e664",
    "data/reanalysis/diagnostics.csv": "0169e20d47c1c24284696a8be1553d5af47e7ce8e1d26f7cdf31ba1ef60cda73",
    "data/reanalysis/above_freezing_sensitivity.csv": "e5c43afe7d74db66fdaeab61e968ccc6fd68346d45dca06e4284ea134f6c467b",
    "data/reanalysis/cross_layout_probes.csv": "4e0a540fd93a2b42829d9d9170948e4ee46831b87566b2c48d024889be7d044d",
    "data/reanalysis/source/e5.oper.invariant.128_129_z.ll025sc.1979010100_1979010100.nc": "ebc93b1aeb0060fd5289b9b995f584c9b41abd40642afe34575dc619a310d66d",
    "data/reanalysis/source/e5.oper.invariant.128_172_lsm.ll025sc.1979010100_1979010100.nc": "ac5d93fbc2a7afc100cd8599fb6b324cfc2f2d20706f6e8df0b92f5bf61c6e61",
}
NEW_FILES = ["protocol/audited-reanalysis-transfer.md", "requirements-audited-reanalysis.txt",
             "data/audited_reanalysis/output_schemas.json", "scripts/audited_reanalysis.py",
             "tests/test_audited_reanalysis.py"]
PACKAGES = ["icechunk", "netCDF4", "numpy", "pandas", "pcodec", "scipy", "xarray", "zarr"]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def require_upstream():
    for name, expected in UPSTREAM.items():
        if sha256(ROOT / name) != expected: raise ValueError(f"frozen input drift: {name}")

def analysis_frame():
    require_upstream()
    candidates = pd.read_csv(ROOT / "data/candidates.csv", dtype=str).fillna("")
    candidates = candidates.query("consensus_decision == 'include' and trigger_time_eligible == 'yes'")
    audit = pd.read_csv(ROOT / "data/event_audit/summary.csv", dtype=str).fillna("")
    frame = candidates.merge(audit, on="candidate_id", validate="one_to_one")
    if len(frame) != 53: raise ValueError("registered audit frame is not 53 rows")
    frame["selected"] = (frame.coordinate_status == "accepted") & (frame.time_status == "accepted")
    coordinate_reason = np.where(frame.coordinate_status == "accepted", "accepted", frame.coordinate_unresolved_reason)
    time_reason = np.where(frame.time_status == "accepted", "accepted",
                           np.where(frame.time_unresolved_reason != "", frame.time_unresolved_reason, frame.time_status))
    frame["exclusion_reason"] = np.where(frame.selected, "selected",
        "coordinate=" + coordinate_reason + ";time=" + time_reason)
    eligibility = frame[["candidate_id", "coordinate_status", "coordinate_unresolved_reason", "time_status",
        "time_unresolved_reason", "selected", "exclusion_reason"]].sort_values("candidate_id")
    times = pd.read_csv(ROOT / "data/event_audit/time_assertions.csv", dtype=str).fillna("").rename(columns={
        "candidate_id": "assertion_candidate_id", "onset_lower_utc": "assertion_lower_utc",
        "onset_upper_utc": "assertion_upper_utc"})
    selected = frame[frame.selected].merge(times[["assertion_id", "assertion_candidate_id", "onset_role",
        "review_state", "assertion_lower_utc", "assertion_upper_utc"]],
        left_on="time_assertion_id", right_on="assertion_id", validate="one_to_one")
    if not ((selected.candidate_id == selected.assertion_candidate_id).all()
            and (selected.onset_lower_utc == selected.assertion_lower_utc).all()
            and (selected.onset_upper_utc == selected.assertion_upper_utc).all()
            and (selected.review_state == "agree").all()): raise ValueError("accepted onset assertion mismatch")
    lower = pd.to_datetime(selected.onset_lower_utc, utc=True, format="mixed")
    anchor = lower.dt.floor("h")
    selected = selected.assign(event_year=lower.dt.year, latitude_deg=selected.audited_latitude_deg.astype(float),
        longitude_deg=selected.audited_longitude_deg.astype(float), onset_anchor_utc=anchor.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        calendar_anchor_utc=selected.date_start + "T00:00:00Z",
        quantization_gap_seconds=(lower-anchor).dt.total_seconds())
    records = selected.to_dict("records"); pilot.dependence_components(records); selected = pd.DataFrame(records)
    old_ids = set(pd.read_csv(ROOT / "data/reanalysis/event_cells.csv", usecols=["candidate_id"]).candidate_id)
    selected["old_pilot_overlap"] = selected.candidate_id.isin(old_ids)
    if hashlib.sha256(("\n".join(sorted(selected.candidate_id))+"\n").encode()).hexdigest() != SELECTED_DIGEST:
        raise ValueError("audited selected IDs drift")
    if (len(selected), selected.onset_role.value_counts().to_dict(), selected.dependence_component.nunique(),
            selected.old_pilot_overlap.sum()) != (22, {"source_failure": 16, "trigger_proxy": 6}, 18, 9):
        raise ValueError("audited population counts drift")
    if selected.coordinate_uncertainty_class.value_counts().to_dict() != {"le_1_km": 19, "le_5_km": 3}:
        raise ValueError("coordinate uncertainty counts drift")
    columns = ["candidate_id", "event_group_id", "event_name", "date_start", "event_year",
        "audited_latitude_deg", "audited_longitude_deg", "coordinate_uncertainty_class",
        "coordinate_assertion_id", "onset_lower_utc", "onset_upper_utc", "time_assertion_id",
        "onset_role", "onset_anchor_utc", "calendar_anchor_utc", "quantization_gap_seconds",
        "dependence_component", "component_representative", "cluster_ids", "old_pilot_overlap"]
    return eligibility.reset_index(drop=True), selected[columns].sort_values("candidate_id").reset_index(drop=True)

def build_cells(selected):
    event_table = selected.rename(columns={"audited_latitude_deg": "latitude_deg",
        "audited_longitude_deg": "longitude_deg"}).copy()
    event_table[["latitude_deg", "longitude_deg"]] = event_table[["latitude_deg", "longitude_deg"]].astype(float)
    with pilot.xr.open_dataset(pilot.Z_FILE) as z_ds, pilot.xr.open_dataset(pilot.LSM_FILE) as lsm_ds:
        latitudes, longitudes = z_ds.latitude.values, z_ds.longitude.values
        if not (np.array_equal(latitudes, lsm_ds.latitude.values)
                and np.array_equal(longitudes, lsm_ds.longitude.values)): raise ValueError("invariant grids disagree")
        z, lsm = z_ds.Z.values[0], lsm_ds.LSM.values[0]
    lat_index = {float(value): i for i, value in enumerate(latitudes)}
    lon_index = {float(value): j for j, value in enumerate(longitudes)}; rows = []
    for event in event_table.to_dict("records"):
        event_lon = event["longitude_deg"] % 360.0; group = []
        for lat in pilot.nearest_two(latitudes, event["latitude_deg"]):
            for lon in pilot.nearest_two(longitudes, event_lon, circular=True):
                i, j = lat_index[float(lat)], lon_index[float(lon)]
                group.append({"candidate_id": event["candidate_id"], "event_group_id": event["event_group_id"],
                    "event_name": event["event_name"], "event_date": event["date_start"], "event_year": event["event_year"],
                    "audited_latitude_deg": event["latitude_deg"], "audited_longitude_deg": event["longitude_deg"],
                    "grid_latitude_deg": float(lat), "grid_longitude_deg_east": float(lon), "latitude_index": i,
                    "longitude_index": j, "land_fraction": float(lsm[i, j]), "model_surface_height_m": float(z[i, j]/9.80665),
                    "distance_km": pilot.great_circle_km(event["latitude_deg"], event_lon, lat, lon),
                    "dependence_component": event["dependence_component"],
                    "component_representative": event["component_representative"], "cluster_ids": event["cluster_ids"],
                    "coordinate_uncertainty_class": event["coordinate_uncertainty_class"], "onset_role": event["onset_role"]})
        group.sort(key=lambda row: (-row["land_fraction"], row["distance_km"], row["grid_latitude_deg"], row["grid_longitude_deg_east"]))
        for rank, row in enumerate(group, 1): row.update(cell_rank=rank, primary_cell=rank == 1); rows.append(row)
    cells = pd.DataFrame(rows)
    if len(cells) != 88 or not (cells.groupby("candidate_id").size() == 4).all():
        raise ValueError("audited cell population drift")
    columns = [item[0] for item in json.loads(SCHEMAS.read_text())["audited_cells.csv"]["columns"]]
    return cells[columns]

def cast_and_check(name, table):
    spec = json.loads(SCHEMAS.read_text())[name]
    columns = [item[0] for item in spec["columns"]]
    if len(table) != spec["rows"] or list(table.columns) != columns: raise ValueError(f"schema mismatch: {name}")
    for column, dtype in spec["columns"]:
        table[column] = table[column].astype({"string": str, "bool": bool, "int64": "int64", "float64": "float64"}[dtype])
    return table

def preaccess():
    OUT.mkdir(parents=True, exist_ok=True)
    eligibility, selected = analysis_frame(); cells = build_cells(selected)
    tables = {"eligibility.csv": eligibility, "selected_events.csv": selected, "audited_cells.csv": cells}
    for name, table in tables.items(): cast_and_check(name, table).to_csv(OUT/name, index=False, float_format="%.17g")
    bound = list(UPSTREAM) + NEW_FILES + [f"data/audited_reanalysis/{name}" for name in tables]
    manifest = {"status": "pre_event_temperature_access_v1", "issue": 29,
        "created_utc": datetime.now(timezone.utc).isoformat(), "selected_id_sha256": SELECTED_DIGEST,
        "population": {"frame": 53, "selected": 22, "source_failure": 16, "trigger_proxy": 6,
                       "components": 18, "old_pilot_overlap": 9, "cells": 88},
        "source": {"snapshot": pilot.SNAPSHOT, "group": "single/temporal", "variable": "t2m",
                   "years": [1979, 2025], "reference_years": [1991, 2020], "windows_hours": WINDOWS},
        "environment": {name: importlib.metadata.version(name) for name in PACKAGES},
        "files": {name: {"bytes": (ROOT/name).stat().st_size, "sha256": sha256(ROOT/name)} for name in bound}}
    (OUT/"preaccess_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    print("froze 53 rows, 22 audited events, and 88 cells; no remote temperature access")

def verify_gate(path, approved):
    if sha256(path) != approved: raise ValueError("preaccess manifest is not the approved digest")
    manifest = json.loads(path.read_text())
    if manifest["status"] != "pre_event_temperature_access_v1": raise ValueError("wrong gate status")
    for name, record in manifest["files"].items():
        target = ROOT/name
        if target.stat().st_size != record["bytes"] or sha256(target) != record["sha256"]: raise ValueError(f"gate drift: {name}")
    for name, version in manifest["environment"].items():
        if importlib.metadata.version(name) != version: raise ValueError(f"runtime drift: {name}")
    return manifest

def indices(time0, timestamp, year, hours):
    source = pd.Timestamp(timestamp)
    try: anchor = pd.Timestamp(year=year, month=source.month, day=source.day, hour=source.hour)
    except ValueError: return None
    stop = int((anchor.to_datetime64()-time0)/np.timedelta64(1, "h"))
    return np.arange(stop-hours, stop, dtype=np.int64)

def extract(selected, cells, temporal):
    lat, lon, times = temporal.latitude.values, temporal.longitude.values, temporal.valid_time.values
    if not (np.array_equal(lat, np.sort(lat)[::-1]) and np.allclose(np.diff(lon), .25)
            and np.all(np.diff(times) == np.timedelta64(1, "h"))): raise ValueError("unexpected ERA5 grid")
    for cell in cells.itertuples():
        if lat[cell.latitude_index] != cell.grid_latitude_deg or lon[cell.longitude_index] != cell.grid_longitude_deg_east:
            raise ValueError("invariant and temperature grids disagree")
    event = selected.set_index("candidate_id"); time0 = times[0]; matched, air = [], []
    tiles = {}
    for row in cells.to_dict("records"): tiles.setdefault((row["latitude_index"]//12, row["longitude_index"]//12), []).append(row)
    for tile, rows in sorted(tiles.items()):
        requests = []
        for candidate_id in {row["candidate_id"] for row in rows}:
            for anchor in ("onset", "calendar"):
                stamp = event.loc[candidate_id, f"{anchor}_anchor_utc"]
                for year in YEARS: requests.append(indices(time0, stamp, year, 720))
        requested = np.unique(np.concatenate([item for item in requests if item is not None]))
        if requested[0] < 0 or requested[-1] >= len(times): raise ValueError("registered request exceeds store coverage")
        i0, j0 = tile[0]*12, tile[1]*12
        block = temporal.t2m.isel(valid_time=requested, latitude=slice(i0, min(i0+12, 721)),
                                  longitude=slice(j0, min(j0+12, 1440))).values
        for cell in rows:
            candidate_id = cell["candidate_id"]
            for anchor in ("onset", "calendar"):
                stamp = event.loc[candidate_id, f"{anchor}_anchor_utc"]
                for year in YEARS:
                    for window, hours in WINDOWS.items():
                        idx = indices(time0, stamp, year, hours)
                        positions = np.searchsorted(requested, idx)
                        if not np.array_equal(requested[positions], idx): raise ValueError("requested hour lookup mismatch")
                        values = block[positions, cell["latitude_index"]-i0, cell["longitude_index"]-j0]
                        if len(values) != hours or not np.isfinite(values).all() or values.min() < 180 or values.max() > 340:
                            raise ValueError("invalid requested temperature hours")
                        matched.append({"candidate_id": candidate_id, "grid_latitude_deg": cell["grid_latitude_deg"],
                            "grid_longitude_deg_east": cell["grid_longitude_deg_east"], "primary_cell": cell["primary_cell"],
                            "anchor": anchor, "year": year, "window": window, "hours": hours, "mean_t2m_k": float(values.mean())})
                        if anchor == "onset" and window == "7d" and year == event.loc[candidate_id, "event_year"] and cell["primary_cell"]:
                            for lapse in (4., 6.5, 9.):
                                for offset in (-1, 0, 1, 2): air.append({"candidate_id": candidate_id,
                                    "onset_role": event.loc[candidate_id, "onset_role"], "lapse_rate_k_per_km": lapse,
                                    "site_minus_model_height_km": offset,
                                    "hours_above_273_15_k": int(np.sum(values-lapse*offset > 273.15))})
    return pd.DataFrame(matched), pd.DataFrame(air)

def derive(matched, cells, selected):
    parts = []
    for anchor in ("onset", "calendar"):
        part = pilot.derive_diagnostics(matched[matched.anchor == anchor].drop(columns="anchor"), cells)
        part.insert(4, "anchor", anchor); parts.append(part)
    diagnostics = pd.concat(parts, ignore_index=True)
    fields = ["event_mean_t2m_k", "warm_state_anomaly_k", "warm_state_rank", "theil_sen_k_per_decade",
              "fitted_change_1991_to_event_k", "linear_trend_residual_rank"]
    primary = diagnostics[diagnostics.primary_cell].pivot(index=["candidate_id", "window"], columns="anchor", values=fields)
    primary.columns = [f"{anchor}_{field}" for field, anchor in primary.columns]; primary = primary.reset_index()
    meta = selected[["candidate_id", "onset_role", "coordinate_uncertainty_class", "quantization_gap_seconds",
                     "dependence_component", "component_representative", "old_pilot_overlap"]]
    primary = primary.merge(meta, on="candidate_id", validate="many_to_one")
    primary["delta_time_warm_state_rank"] = primary.onset_warm_state_rank-primary.calendar_warm_state_rank
    primary["delta_time_linear_trend_residual_rank"] = primary.onset_linear_trend_residual_rank-primary.calendar_linear_trend_residual_rank
    onset = diagnostics[diagnostics.anchor == "onset"]
    ranges = onset.groupby(["candidate_id", "window"]).agg(
        onset_four_cell_warm_rank_min=("warm_state_rank", "min"), onset_four_cell_warm_rank_max=("warm_state_rank", "max"),
        onset_four_cell_residual_rank_min=("linear_trend_residual_rank", "min"),
        onset_four_cell_residual_rank_max=("linear_trend_residual_rank", "max")).reset_index()
    primary = primary.merge(ranges, on=["candidate_id", "window"], validate="one_to_one")
    for stem in ("warm_rank", "residual_rank"):
        primary[f"onset_four_cell_{stem}_range"] = primary[f"onset_four_cell_{stem}_max"]-primary[f"onset_four_cell_{stem}_min"]
    columns = [item[0] for item in json.loads(SCHEMAS.read_text())["primary_diagnostics.csv"]["columns"]]
    primary = primary[columns]
    old = pd.read_csv(ROOT/"data/reanalysis/diagnostics.csv", float_precision="round_trip")
    old = old[old.primary_cell & old.window.isin(WINDOWS)].rename(columns={name: f"old_{name}" for name in
        ("warm_state_anomaly_k", "warm_state_rank", "linear_trend_residual_rank")})
    overlap = primary[primary.old_pilot_overlap].merge(old[["candidate_id", "window", "old_warm_state_anomaly_k",
        "old_warm_state_rank", "old_linear_trend_residual_rank"]], on=["candidate_id", "window"], validate="one_to_one")
    for kind in ("warm_state_rank", "linear_trend_residual_rank"):
        overlap[f"delta_coordinate_{kind}"] = overlap[f"calendar_{kind}"]-overlap[f"old_{kind}"]
        overlap[f"delta_combined_{kind}"] = overlap[f"onset_{kind}"]-overlap[f"old_{kind}"]
    ocols = [item[0] for item in json.loads(SCHEMAS.read_text())["overlap_comparison.csv"]["columns"]]
    return diagnostics, primary, overlap[ocols]

def analyze(manifest_path, approved, result_dir):
    gate = verify_gate(manifest_path, approved)
    eligibility = pd.read_csv(OUT/"eligibility.csv"); selected = pd.read_csv(OUT/"selected_events.csv")
    cells = pd.read_csv(OUT/"audited_cells.csv"); session, temporal, spatial = pilot.open_store()
    if session.snapshot_id != gate["source"]["snapshot"]: raise ValueError("snapshot drift")
    probes = pilot.verify_probes(temporal, spatial); matched, air = extract(selected, cells, temporal)
    diagnostics, primary, overlap = derive(matched, cells, selected)
    tables = {"cross_layout_probes.csv": probes, "matched_windows.csv": matched, "diagnostics.csv": diagnostics,
              "primary_diagnostics.csv": primary, "overlap_comparison.csv": overlap,
              "above_freezing_sensitivity.csv": air}
    for name, table in tables.items(): cast_and_check(name, table)
    if result_dir.exists(): raise ValueError("registered result directory already exists")
    temp = Path(tempfile.mkdtemp(prefix="audited-reanalysis-", dir=result_dir.parent))
    try:
        for name, table in tables.items(): table.to_csv(temp/name, index=False, float_format="%.17g")
        manifest = {"status": "audited_event_temperature_transfer_v1", "approved_preaccess_sha256": approved,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(), "snapshot": session.snapshot_id,
            "packages": gate["environment"], "rows": {name: len(table) for name, table in tables.items()},
            "output_sha256": {name: sha256(temp/name) for name in tables}}
        (temp/"retrieval_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
        os.replace(temp, result_dir)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True); raise
    print(f"wrote {len(matched)} matched means and {len(primary)} primary diagnostics; no pass label")

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--action", choices=("preaccess", "analysis"), required=True)
    parser.add_argument("--preaccess-manifest", type=Path, default=OUT/"preaccess_manifest.json")
    parser.add_argument("--approved-manifest-sha256"); parser.add_argument("--results-dir", type=Path, default=RESULTS)
    args = parser.parse_args()
    if args.action == "preaccess": preaccess()
    elif not args.approved_manifest_sha256: parser.error("analysis requires --approved-manifest-sha256")
    else: analyze(args.preaccess_manifest, args.approved_manifest_sha256, args.results_dir)

if __name__ == "__main__": main()

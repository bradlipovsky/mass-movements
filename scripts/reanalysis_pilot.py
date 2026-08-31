#!/usr/bin/env python3
"""Extract the registered ERA5 temperature pilot and derive diagnostics."""
import csv
import hashlib
import importlib.metadata
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import icechunk
import numpy as np
import pandas as pd
import pcodec  # noqa: F401: registers the Zarr decoder
import xarray as xr
from scipy.stats import theilslopes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reanalysis"
SOURCE = OUT / "source"
Z_FILE = SOURCE / "e5.oper.invariant.128_129_z.ll025sc.1979010100_1979010100.nc"
LSM_FILE = SOURCE / "e5.oper.invariant.128_172_lsm.ll025sc.1979010100_1979010100.nc"
PROTOCOL_COMMIT = "39279a9a193d6d8112d8f1663b71832adfc8f5fb"
AUDIT_AMENDMENT_COMMIT = "785a2e055e452d099b3375e7b9c0cb0648b0d14a"
SNAPSHOT = "T9H8SG2PVXWNY0QNJPJG"
FROZEN_INPUT_SHA256 = {
    "data/candidates.csv": "8b6b0f972180e26c326aaa0e6a501080843bd4b6e6674b07c5aa009340c8a249",
    "data/candidate_clusters.csv": "fd1545d60fe527e9881ec9169cf9ee93dc94eab1470595641695d1bcf089f309",
}
SOURCE_URI = {
    Z_FILE.name: "s3://nsf-ncar-era5/e5.oper.invariant/197901/" + Z_FILE.name,
    LSM_FILE.name: "s3://nsf-ncar-era5/e5.oper.invariant/197901/" + LSM_FILE.name,
}
YEARS = range(1979, 2026)
WINDOWS = {"2d": (-2, 0), "7d": (-7, 0), "7d_buffered": (-8, -1),
           "30d": (-30, 0), "event_day": (0, 1)}
PROBES = [(0.0, 0.0, "2001-01-15T00:00:00"),
          (45.0, 10.0, "2011-06-15T12:00:00"),
          (-30.0, 140.0, "2020-12-15T18:00:00")]

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def selected_events():
    path = ROOT / "data" / "candidates.csv"
    if sha256(path) != FROZEN_INPUT_SHA256["data/candidates.csv"]:
        raise ValueError("candidate inventory differs from discovery freeze")
    with open(path, newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows = [row for row in rows
            if row["consensus_decision"] == "include"
            and row["trigger_time_eligible"] == "yes"
            and row["latitude_deg"] and row["longitude_deg"]]
    if len(rows) != 29:
        raise ValueError(f"registered selection has {len(rows)} rows, expected 29")
    for row in rows:
        row["latitude_deg"] = float(row["latitude_deg"])
        row["longitude_deg"] = float(row["longitude_deg"])
        row["event_year"] = int(row["date_start"][:4])
    return rows

def dependence_components(events):
    ids = {row["candidate_id"] for row in events}
    parent = {candidate_id: candidate_id for candidate_id in ids}
    links = {candidate_id: [] for candidate_id in ids}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    path = ROOT / "data" / "candidate_clusters.csv"
    if sha256(path) != FROZEN_INPUT_SHA256["data/candidate_clusters.csv"]:
        raise ValueError("dependence clusters differ from discovery freeze")
    with open(path, newline="") as stream:
        for cluster in csv.DictReader(stream):
            members = [item for item in cluster["candidate_ids"].split(";") if item in ids]
            for item in members:
                links[item].append(cluster["cluster_id"])
            for item in members[1:]:
                union(members[0], item)
    groups = {}
    for row in events:
        groups.setdefault(find(row["candidate_id"]), []).append(row)
    for members in groups.values():
        representative = min(members, key=lambda row: (row["date_start"], row["candidate_id"]))
        component = min(row["candidate_id"] for row in members)
        for row in members:
            row["dependence_component"] = component
            row["component_representative"] = row is representative
            row["cluster_ids"] = ";".join(sorted(links[row["candidate_id"]]))


def nearest_two(values, target, circular=False):
    def distance(value):
        delta = abs(float(value) - target)
        return min(delta, 360.0 - delta) if circular else delta
    return sorted(values, key=lambda value: (distance(value), float(value)))[:2]


def great_circle_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(((lon2 - lon1 + 180) % 360) - 180)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def build_cell_manifest(events):
    with xr.open_dataset(Z_FILE) as z_ds, xr.open_dataset(LSM_FILE) as lsm_ds:
        latitudes = z_ds.latitude.values
        longitudes = z_ds.longitude.values
        if not (np.array_equal(latitudes, lsm_ds.latitude.values)
                and np.array_equal(longitudes, lsm_ds.longitude.values)):
            raise ValueError("invariant grids disagree")
        z = z_ds.Z.values[0]
        lsm = lsm_ds.LSM.values[0]
    lat_index = {float(value): index for index, value in enumerate(latitudes)}
    lon_index = {float(value): index for index, value in enumerate(longitudes)}
    records = []
    for event in events:
        event_lon = event["longitude_deg"] % 360.0
        cells = []
        for lat in nearest_two(latitudes, event["latitude_deg"]):
            for lon in nearest_two(longitudes, event_lon, circular=True):
                i, j = lat_index[float(lat)], lon_index[float(lon)]
                cells.append({
                    "candidate_id": event["candidate_id"],
                    "event_group_id": event["event_group_id"],
                    "event_name": event["event_name"],
                    "event_date": event["date_start"],
                    "event_year": event["event_year"],
                    "event_latitude_deg": event["latitude_deg"],
                    "event_longitude_deg": event["longitude_deg"],
                    "grid_latitude_deg": float(lat), "grid_longitude_deg_east": float(lon),
                    "latitude_index": i, "longitude_index": j,
                    "land_fraction": float(lsm[i, j]),
                    "model_surface_height_m": float(z[i, j] / 9.80665),
                    "distance_km": great_circle_km(event["latitude_deg"], event_lon, lat, lon),
                    "dependence_component": event["dependence_component"],
                    "component_representative": event["component_representative"],
                    "cluster_ids": event["cluster_ids"],
                })
        cells.sort(key=lambda row: (-row["land_fraction"], row["distance_km"],
                                    row["grid_latitude_deg"], row["grid_longitude_deg_east"]))
        for rank, cell in enumerate(cells):
            cell["cell_rank"] = rank + 1
            cell["primary_cell"] = rank == 0
            records.append(cell)
    if len(records) != 116:
        raise ValueError("four-cell manifest is incomplete")
    return pd.DataFrame(records)


def open_store():
    storage = icechunk.s3_storage(bucket="earthmover-icechunk-era5", prefix="icechunkV2",
                                  region="us-east-1", anonymous=True)
    repo = icechunk.Repository.open(storage)
    session = repo.readonly_session(snapshot_id=SNAPSHOT)
    temporal = xr.open_zarr(session.store, group="single/temporal", consolidated=False, chunks=None)
    spatial = xr.open_zarr(session.store, group="single/spatial", consolidated=False, chunks=None)
    return session, temporal, spatial


def verify_probes(temporal, spatial):
    records = []
    for lat, lon, timestamp in PROBES:
        first = float(temporal.t2m.sel(latitude=lat, longitude=lon, valid_time=timestamp).item())
        second = float(spatial.t2m.sel(latitude=lat, longitude=lon, valid_time=timestamp).item())
        records.append({"latitude_deg": lat, "longitude_deg_east": lon, "valid_time": timestamp,
                        "temporal_t2m_k": first, "spatial_t2m_k": second,
                        "difference_k": first - second, "exact_match": first == second})
    result = pd.DataFrame(records)
    if not result.exact_match.all():
        raise ValueError("registered temporal/spatial probe mismatch")
    return result


def interval_indices(time0, date_text, year, start_day, end_day):
    source = pd.Timestamp(date_text)
    try:
        day = pd.Timestamp(year=year, month=source.month, day=source.day)
    except ValueError:
        return None
    start = day + pd.Timedelta(days=start_day)
    stop = day + pd.Timedelta(days=end_day)
    first = int((start.to_datetime64() - time0) / np.timedelta64(1, "h"))
    last = int((stop.to_datetime64() - time0) / np.timedelta64(1, "h"))
    return np.arange(first, last, dtype=np.int64)


def extract_windows(events, cells, temporal):
    if temporal.attrs["time_coverage_end"] < "2025-12-31T23:00:00Z":
        raise ValueError("store does not cover registered years")
    latitudes, longitudes = temporal.latitude.values, temporal.longitude.values
    times = temporal.valid_time.values
    if not (np.array_equal(latitudes, np.sort(latitudes)[::-1])
            and np.allclose(np.diff(longitudes), 0.25)
            and np.all(np.diff(times) == np.timedelta64(1, "h"))):
        raise ValueError("unexpected ERA5 grid")
    for cell in cells.itertuples():
        if (latitudes[cell.latitude_index] != cell.grid_latitude_deg
                or longitudes[cell.longitude_index] != cell.grid_longitude_deg_east):
            raise ValueError("invariant and temperature grids disagree")
    event_by_id = {row["candidate_id"]: row for row in events}
    time0 = temporal.valid_time.values[0]
    time_count = temporal.sizes["valid_time"]
    tiles = {}
    for row in cells.to_dict("records"):
        tile = (row["latitude_index"] // 12, row["longitude_index"] // 12)
        tiles.setdefault(tile, []).append(row)
    matched, thaw = [], []
    for number, (tile, tile_cells) in enumerate(sorted(tiles.items()), 1):
        event_ids = sorted({row["candidate_id"] for row in tile_cells})
        requests = []
        for candidate_id in event_ids:
            event = event_by_id[candidate_id]
            for year in YEARS:
                indices = interval_indices(time0, event["date_start"], year, -30, 1)
                if indices is not None:
                    requests.append(indices)
        requested = np.unique(np.concatenate(requests))
        if requested[0] < 0 or requested[-1] >= time_count:
            raise ValueError("registered request exceeds store coverage")
        i0, j0 = tile[0] * 12, tile[1] * 12
        block = temporal.t2m.isel(valid_time=requested,
                                  latitude=slice(i0, min(i0 + 12, 721)),
                                  longitude=slice(j0, min(j0 + 12, 1440))).values
        print(f"tile {number}/{len(tiles)} {tile}: {len(requested)} hours, {len(event_ids)} events")
        for cell in tile_cells:
            event = event_by_id[cell["candidate_id"]]
            for year in YEARS:
                for window, bounds in WINDOWS.items():
                    indices = interval_indices(time0, event["date_start"], year, *bounds)
                    if indices is None:
                        continue
                    positions = np.searchsorted(requested, indices)
                    values = block[positions, cell["latitude_index"] - i0,
                                   cell["longitude_index"] - j0]
                    if len(values) != 24 * (bounds[1] - bounds[0]) or not np.isfinite(values).all():
                        raise ValueError("missing or duplicate requested hours")
                    if values.min() < 180 or values.max() > 340:
                        raise ValueError("implausible ERA5 temperature")
                    matched.append({"candidate_id": cell["candidate_id"],
                                    "grid_latitude_deg": cell["grid_latitude_deg"],
                                    "grid_longitude_deg_east": cell["grid_longitude_deg_east"],
                                    "primary_cell": cell["primary_cell"], "year": year,
                                    "window": window, "hours": len(values),
                                    "mean_t2m_k": float(values.mean())})
                    if (cell["primary_cell"] and year == event["event_year"]
                            and window in ("7d", "7d_buffered")):
                        for lapse_rate in (4.0, 6.5, 9.0):
                            for offset in (-1, 0, 1, 2):
                                thaw.append({"candidate_id": cell["candidate_id"],
                                             "window": window,
                                             "lapse_rate_k_per_km": lapse_rate,
                                             "site_minus_model_height_km": offset,
                                             "hours_above_273_15_k": int(np.sum(values - lapse_rate * offset > 273.15))})
    return pd.DataFrame(matched), pd.DataFrame(thaw)


def midrank(value, controls):
    controls = np.asarray(controls)
    return float((np.sum(controls < value) + 0.5 * np.sum(controls == value)) / len(controls))


def derive_diagnostics(matched, cells):
    records = []
    event_years = cells.drop_duplicates("candidate_id").set_index("candidate_id")["event_year"]
    cell_fields = cells.set_index(["candidate_id", "grid_latitude_deg", "grid_longitude_deg_east"])
    keys = ["candidate_id", "grid_latitude_deg", "grid_longitude_deg_east", "window"]
    for key, group in matched.groupby(keys, sort=True):
        candidate_id, lat, lon, window = key
        event_year = int(event_years[candidate_id])
        years = group.year.to_numpy()
        values = group.mean_t2m_k.to_numpy()
        event_value = values[years == event_year][0]
        reference = (years >= 1991) & (years <= 2020) & (years != event_year)
        slope, intercept, _, _ = theilslopes(values, years)
        residuals = values - (intercept + slope * years)
        event_residual = residuals[years == event_year][0]
        cell = cell_fields.loc[(candidate_id, lat, lon)]
        records.append({"candidate_id": candidate_id, "grid_latitude_deg": lat,
                        "grid_longitude_deg_east": lon, "primary_cell": bool(cell.primary_cell),
                        "window": window, "event_year": event_year,
                        "event_mean_t2m_k": event_value,
                        "reference_median_t2m_k": float(np.median(values[reference])),
                        "warm_state_anomaly_k": float(event_value - np.median(values[reference])),
                        "warm_state_rank": midrank(event_value, values[reference]),
                        "theil_sen_k_per_decade": float(10 * slope),
                        "fitted_change_1991_to_event_k": float(slope * (event_year - 1991)),
                        "linear_trend_residual_rank": midrank(event_residual, residuals[reference]),
                        "dependence_component": cell.dependence_component,
                        "component_representative": bool(cell.component_representative)})
    return pd.DataFrame(records)


def write_outputs():
    OUT.mkdir(parents=True, exist_ok=True)
    events = selected_events()
    dependence_components(events)
    cells = build_cell_manifest(events)
    session, temporal, spatial = open_store()
    probes = verify_probes(temporal, spatial)
    matched, thaw = extract_windows(events, cells, temporal)
    diagnostics = derive_diagnostics(matched, cells)
    outputs = {"event_cells.csv": cells, "cross_layout_probes.csv": probes,
               "matched_windows.csv": matched, "diagnostics.csv": diagnostics,
               "above_freezing_sensitivity.csv": thaw}
    for filename, table in outputs.items():
        table.to_csv(OUT / filename, index=False, float_format="%.17g")
    packages = ["icechunk", "pcodec", "xarray", "zarr", "numpy", "pandas", "scipy", "netCDF4"]
    manifest = {
        "protocol_commit": PROTOCOL_COMMIT, "audit_amendment_commit": AUDIT_AMENDMENT_COMMIT,
        "icechunk_snapshot": session.snapshot_id,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "store": "s3://earthmover-icechunk-era5/icechunkV2",
        "group": "single/temporal", "variable": "t2m",
        "time_coverage_start": temporal.attrs["time_coverage_start"],
        "time_coverage_end": temporal.attrs["time_coverage_end"],
        "event_count": len(events), "cell_count": len(cells),
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "catalog_input_sha256": FROZEN_INPUT_SHA256,
        "source_uri": SOURCE_URI,
        "source_sha256": {path.name: sha256(path) for path in (Z_FILE, LSM_FILE)},
        "output_sha256": {filename: sha256(OUT / filename) for filename in outputs},
    }
    with open(OUT / "retrieval_manifest.json", "w") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"wrote {len(cells)} cells, {len(matched)} matched windows, {len(diagnostics)} diagnostics")


if __name__ == "__main__":
    write_outputs()

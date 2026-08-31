#!/usr/bin/env python3
"""Select blind transfer windows from RGI attributes and no terrain values."""
import csv
from pathlib import Path

import pandas as pd

from scripts.susceptible_area_convergence import eligible_windows, rank_regions

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "scale_explicit_transfer"
SOURCE = OUTPUT / "selection_source"
UNOPENED = ["02", "04", "06", "09", "10", "12", "14", "15", "16", "17", "18"]
REGIONS = {
    "10": ("North Asia", "RGI2000-v7.0-G-10_north_asia-attributes.csv"),
    "18": ("New Zealand", "RGI2000-v7.0-G-18_new_zealand-attributes.csv"),
    "15": ("South Asia East", "RGI2000-v7.0-G-15_south_asia_east-attributes.csv"),
    "04": ("Arctic Canada South", "RGI2000-v7.0-G-04_arctic_canada_south-attributes.csv"),
}


def attribute_rows(path):
    """Read exact RGI attribute CSV bytes extracted from the hashed archive."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def selection_tables():
    """Return complete eligible cells and the first digest per fixed region."""
    ranking = rank_regions(UNOPENED)
    fixed = [row[1] for row in ranking[:4]]
    if fixed != list(REGIONS):
        raise ValueError(f"region ranking changed: {fixed}")
    region_digests = {region: digest for digest, region, _ in ranking}
    eligible = []
    for region, (name, attribute_name) in REGIONS.items():
        rows = attribute_rows(SOURCE / attribute_name)
        for rank, (digest, key, south, west, count, area) in enumerate(
                eligible_windows(rows, region), start=1):
            eligible.append(dict(
                region=region, region_name=name, region_digest=region_digests[region],
                window_rank=rank, window_digest=digest, window_key=key,
                south=south, west=west, glacier_count=count,
                inventory_area_km2=area,
            ))
    table = pd.DataFrame(eligible)
    selected = table[table.window_rank == 1].copy().reset_index(drop=True)
    if list(selected.region) != list(REGIONS):
        raise ValueError("one selected window per frozen region was not obtained")
    return table, selected


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    eligible, selected = selection_tables()
    eligible.to_csv(OUTPUT / "eligible_windows.csv", index=False, lineterminator="\n")
    selected.to_csv(OUTPUT / "windows.csv", index=False, lineterminator="\n")
    print(f"froze {len(eligible)} eligible cells and {len(selected)} blind windows")


if __name__ == "__main__":
    main()

# Registered ERA5 temperature pilot

These files implement `protocol/reanalysis-pilot.md` for the 29 frozen
occurrences that are included, trigger-time eligible, and have coordinates.
This is 29 of 53 eligible occurrences, with strongly source-dependent
coordinate completeness. They are descriptive event-location exposures, not a
comparison with non-failing slopes.

## Source records

`retrieval_manifest.json` fixes the Earthmover Icechunk snapshot, array group,
variable, package versions, UTC retrieval time, and SHA-256 hashes. The
temperature source is the public temporal layout at
`s3://earthmover-icechunk-era5/icechunkV2`. The two archived NetCDF files in
  `source/` are the NSF NCAR ERA5 surface-geopotential and land--sea-mask
  invariants; their DOI is 10.5065/BH6N-5N20. The manifest records the exact S3
  object keys and hashes their bytes.

`cross_layout_probes.csv` records the three temperature-blind probe locations
and times registered before event extraction. The temporal and spatial layouts
agree exactly at all three probes.

## Derived tables

- `event_cells.csv` gives the four deterministic cells per occurrence,
  invariant fields, primary-cell flag, and registered dependence component.
- `matched_windows.csv` gives 1979--2025 matched-calendar means for the 2-, 7-,
  and 30-day pre-date windows, the conservative seven-day buffered window, and
  the descriptive event UTC day. Read its floats with a round-trip parser when
  recomputing ranks.
- `diagnostics.csv` gives warm-state ranks, robust trends, fitted secular
  changes, and linear-trend-residual ranks for every occurrence, cell, and
  window. A linear residual can retain nonlinear and low-frequency change.
- `above_freezing_sensitivity.csv` gives event-year seven-day 2-m air-
  temperature hours above 273.15 K for all 12 registered lapse-rate/elevation-
  offset scenarios at the primary cell. It covers both the original pre-date
  window and the conservative-antecedence amendment; it does not imply thaw.

The executed notebook `notebooks/era5_pilot.ipynb` reads these tables and
contains the quantitative summaries and figures. `make check-reanalysis`
reconciles dimensions, physical bounds, sample selection, probes, and hashes.
Remote extraction is deliberately separate: `make reanalysis` opens the exact
registered snapshot and stops if that snapshot is no longer available.

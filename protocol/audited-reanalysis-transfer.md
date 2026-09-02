# Source-verified ERA5 temperature transfer

Version 0.1, registered in GitHub Issue 29 before any new ERA5 value was
opened at an audited source coordinate.

## Physical question and boundary

This calculation asks how ERA5 2-m air-temperature diagnostics change when
the atmospheric sample moves from a catalog point and midnight calendar
endpoint to an independently audited initiating-source coordinate and the
last complete hour before the earliest source-supported onset. It tests
reanalysis assignment, not material temperature, melt, failure probability,
systematic climate triggering, or attribution.

The existing Issue 5 pilot remains immutable. Its 29 catalog-coordinate rows
cannot be silently relabeled as source locations: only nine later received
both an accepted source coordinate and an accepted UTC interval. Conversely,
13 other audited occurrences become eligible for the first time.

## Frozen population

Retain all 53 discovery rows satisfying `consensus_decision=include` and
`trigger_time_eligible=yes`. Select a row if and only if the frozen Issue 7
summary has both `coordinate_status=accepted` and `time_status=accepted`.
This mechanical rule gives 22 occurrences, comprising 16 measured
source-failure intervals, six event-specific earthquake trigger proxies, and
18 dependence components. Nineteen coordinates have uncertainty at most
1 km and three at most 5 km. The SHA-256 of sorted selected IDs joined by
newline, including a final newline, is
`93ba0bbc451c5babb9de4081b87f493005b4920dbc1a871efa479f89aae03a08`.

All 31 nonselected rows and controlled reasons remain in `eligibility.csv`.
Conflicting, unresolved, context-only, catalog-place, deposit, lake, gauge,
or downstream-impact assertions are never promoted. No selected row may be
deleted or replaced after temperature access.

## Spatial and temporal assignment

Use each accepted audited coordinate to retain the four 0.25-degree ERA5
cells that bracket it. The primary cell has the largest land fraction, with
great-circle distance, latitude, and longitude resolving successive ties.
This is the unchanged Issue 5 rule and never uses temperature.

For accepted half-open onset interval `[L_i,U_i)`, define

`A_i = floor_to_hour(L_i)`.

Hourly samples end at `A_i - 1 hour`, so they precede the earliest supported
onset. Record the quantization gap `L_i-A_i` in `[0,1 hour)`. A trigger proxy
anchors pre-trigger conditions and is not called a measured detachment time.

At the audited coordinate, also calculate the original Issue 5 calendar
assignment `C_i`, defined as 00:00 UTC on catalog `date_start`. The
onset-minus-calendar contrast isolates time assignment. For the nine old-pilot
overlaps, the audited-coordinate calendar result minus the immutable catalog-
coordinate calendar result isolates coordinate assignment.

## ERA5 source and equations

Reuse immutable Earthmover Icechunk ERA5 snapshot
`T9H8SG2PVXWNY0QNJPJG`, group `single/temporal`, variable `t2m`, plus the
already retained NSF NCAR surface-geopotential and land-fraction fields. Use
1979--2025 hourly values and 1991--2020 controls. Three registered neutral
probes must again match the spatial and temporal layouts exactly.

For anchor `B` in `{A_i,C_i}`, matched year `y`, cell `c`, and window length
`H` in `{48,168,720}` hours, calculate

`Tbar_iyc(B,H) = H^-1 sum_(k=1)^H T2m_c(B_iy-k hours)`.

Match month, day, and hour. Omit an impossible 29 February rather than shift
it. All 22 registered dates have 47 valid matched years, so the frozen table
has 24,816 rows. Reject missing or duplicate hours, non-hourly time axes,
grid mismatch, or values outside 180--340 K.

Against 1991--2020 matched controls, excluding the event year, retain the
event-minus-control-median anomaly, warm-state midrank, Theil--Sen trend in K
per decade, fitted 1991-to-event change, and linear-trend-residual midrank.
Removing a linear trend does not isolate weather from nonlinear or
low-frequency climate variability.

For warm-state and residual ranks, report

`Delta_t = R(audited coordinate, onset anchor)
           - R(audited coordinate, calendar anchor)`

for all 22 occurrences and

`Delta_x = R(audited coordinate, calendar anchor)
           - R(catalog coordinate, calendar anchor)`

for the nine old-pilot overlaps. Also retain their combined old-to-new
contrast, absolute contrasts in the reporting notebook, and four-cell ranges.
No contrast has a pass threshold.

For the onset-aligned primary-cell seven-day values, repeat all 12 Issue 5
lapse-rate/elevation-offset scenarios for hours above 273.15 K. These are
2-m air-temperature scenarios, not source elevation or material thaw.

## Pre-access and output gates

The `preaccess` action may read only frozen catalog/audit tables, immutable
old-pilot identities, and sealed invariant fields. It writes 53 eligibility
rows, 22 selected-event rows, 88 cell rows, and a manifest binding all input,
program, test, environment, and schema hashes. It cannot open the remote ERA5
store. The analysis action requires the independently approved manifest
SHA-256 and rechecks every bound byte and runtime version before opening ERA5.

Unanimous source/onset, numerical/time-grid, and implementation/provenance
approval must precede analysis. Analysis writes all results to a temporary
directory, checks exact schemas and row counts, then renames the complete
directory. A mismatch leaves no registered result directory.

Required result tables are:

- 24,816 matched means: 22 events by four cells by two anchors by three
  windows by 47 years;
- 528 cell-anchor-window diagnostics;
- 66 primary event-window comparisons;
- 27 old-pilot overlap comparisons;
- 264 seven-day above-freezing scenarios; and
- three neutral probe comparisons and a retrieval manifest.

Commit derived tables and retrieval manifest before interpretation and obtain
a second unanimous review. Only then execute a notebook of at most 50 code
lines, make one figure showing time, coordinate, and four-cell sensitivity,
and update the manuscript/PDF. Final reporting and terminal-manifest review
must again be unanimous.

## Review budget and interpretation

New handwritten source plus tests may not exceed 500 lines. Reuse the Issue 5
plain functions and add no class or dependency. Summaries are descriptive for
all 22 occurrences, 18 component representatives, 16 measured source
failures, and six trigger proxies. Uneven discovery, unresolved source data,
and the missing non-failing risk set preclude failure-odds or attribution
claims.

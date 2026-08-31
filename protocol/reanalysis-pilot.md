# ERA5 trigger-time and topographic-sensitivity pilot

Version 0.1. Registered on 30 August 2026 before any ERA5 temperature was read
at an event location. GitHub issue
[#5](https://github.com/bradlipovsky/mass-movements/issues/5) is the public
registration record.

## Question and inferential boundary

This pilot asks whether the frozen climate-blind occurrences can be mapped
reproducibly to ERA5 temperature histories and whether the resulting
event-window diagnostics are stable across neighboring model cells and
plausible elevation corrections. The inventory contains failures but no
denominator of susceptible, non-failing slopes. The pilot therefore measures
temperature exposure at observed occurrences; it cannot estimate a temperature
effect on failure probability or attribute a failure to climate.

## Fixed occurrence set

Select rows from `data/candidates.csv` at discovery freeze commit
`35d392944fef43aeb4084e023bc1fa9470728fab` if and only if:

1. `consensus_decision=include`;
2. `trigger_time_eligible=yes`; and
3. both latitude and longitude are finite.

The rule selects 29 occurrences. No occurrence may be added, removed, or
prioritized after its ERA5 values are viewed. Preserve `event_group_id` and all
registered links in `data/candidate_clusters.csv`. A later correction to an
event coordinate or date requires a named amendment and an old-versus-new
sensitivity result.

The catalog stores a UTC calendar date but not a verified UTC onset timestamp.
Primary antecedent windows therefore stop at 00:00 UTC on the event date and do
not include any event-day hour.

## Reanalysis and invariant fields

Hourly 2 m temperature comes from the public Earthmover Icechunk ERA5 store on
AWS, using its `single/temporal` layout. The AWS registry describes this layout
as long time series in small spatial tiles, states that compression is
lossless, and traces the assembly to the NSF NCAR curated ERA5 archive and the
Copernicus Climate Data Store. Record the Icechunk snapshot identifier, store
attributes, array path, retrieval time in UTC, and SHA-256 hashes of every
local derived table.

Surface geopotential and land--sea mask come from the 0.25 degree NSF NCAR
curated ERA5 invariant files. Convert geopotential to model surface height
using standard gravity, 9.80665 m s^-2. These fields describe model-grid
topography; they are not observations of source-slope elevation.

The Icechunk format requires an isolated modern Python environment and the
`icechunk`, `zarr`, and `xarray` libraries. A pinned requirements file will
document this dependency. The temporal layout is required because public
map-chunked copies make each point-hour request read a global field.

## Spatial extraction

Retain the four 0.25 degree grid cells that bracket each catalog coordinate.
Choose the primary cell by the largest land--sea-mask fraction and break an
exact mask tie by the shortest great-circle distance to the catalog
coordinate. Remaining exact ties are resolved by increasing latitude and then
increasing longitude. This selection never uses temperature.

Report the primary-cell diagnostic and the minimum and maximum over all four
cells. Do not replace the primary cell with the cell that gives a stronger
temperature result. Longitudes are normalized to the coordinate convention of
the source array before indexing.

## Time windows, reference ranks, and trend decomposition

For each event month and day, extract matched calendar windows for every year
from 1979 through 2025. Let `D_y` be 00:00 UTC on that month and day in year
`y`. The primary exposure is mean hourly 2 m temperature on
`[D_y - 7 days, D_y)`. Registered secondary exposures use 2-day and 30-day
antecedent windows. The mean over `[D_y, D_y + 1 day)` is descriptive because
some of those hours follow the failure. A nonexistent 29 February match is
omitted rather than shifted.

For a given cell and window, the *warm-state rank* is the event-year value's
midrank among the matching 1991--2020 values, excluding the event year when it
falls in that interval. In symbols,

\[
R = \frac{\#(T_c<T_e)+\tfrac12\#(T_c=T_e)}{n_c},
\]

where `e` denotes the event year and `c` the eligible reference years. This
diagnostic intentionally contains both secular temperature state and weather
variability.

For the registered decomposition, fit a Theil--Sen line to the 1979--2025
matching-window means separately for every cell and calendar window. Subtract
the fitted value in each year and compute a second midrank of the event
residual against 1991--2020 reference residuals. Report this
*weather-residual rank* together with the fitted change from 1991 to the event
year. A slope or rank is a reanalysis diagnostic, not an inferred failure
cause.

Summaries over occurrences are descriptive medians and interquartile ranges.
Also tabulate one row per registered independent site cluster, retaining the
earliest occurrence in an exact tie only for this sensitivity summary. Do not
attach a population hypothesis test until a susceptible-slope denominator and
an observation model are registered.

## Elevation sensitivity

Adding a fixed lapse correction to an event value and all same-cell reference
values cancels from anomalies, Theil--Sen slopes, and ranks. Verify that
identity numerically.

Absolute thaw exposure does not have this invariance. For the number of hours
above 273.15 K, evaluate every combination of lapse rate 4.0, 6.5, and
9.0 K km^-1 and site-minus-model elevation offset -1, 0, +1, and +2 km. These
12 values are a sensitivity grid, not estimates of source temperature or
source elevation. No combination is primary.

## Checks fixed before event extraction

Before reading an event location, compare the temporal and spatial Icechunk
layouts at three non-event probes:

- 0 degrees N, 0 degrees E at 2001-01-15 00:00 UTC;
- 45 degrees N, 10 degrees E at 2011-06-15 12:00 UTC; and
- 30 degrees S, 140 degrees E at 2020-12-15 18:00 UTC.

Require exact agreement after decoding or document a packing-scale tolerance
before continuing. Reject missing or duplicate requested hours, temperatures
outside 180--340 K, inconsistent coordinate spacing, and any mismatch between
the 29 selected catalog rows and the derived event manifest.

Synthetic tests cover longitude wrapping, four-cell bracketing, primary-cell
selection, UTC interval endpoints, midranks with ties, Theil--Sen detrending,
and lapse-correction cancellation.

## Expected artifacts and stopping rules

Commit a machine-checkable retrieval manifest and compact derived tables, plus
an executed notebook with two figures: occurrence-level warm-state and
weather-residual ranks; and four-cell/elevation sensitivity. If the manuscript
changes, rebuild and commit its PDF.

Stop and amend this protocol before event extraction if the temporal array does
not contain 2 m temperature through 2025, the two layouts fail the registered
probe comparison, or the fixed sample does not contain 29 rows. Stop and
simplify if handwritten source and tests approach 500 lines.

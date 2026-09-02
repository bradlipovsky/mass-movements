# Native GLO-90 development transfer of the terrain-screen functional

## Question and claim boundary

This development calculation asks how replacing Copernicus DEM GLO-30 with
the separately processed native GLO-90 product changes the frozen equivalent
steep-area functional in seven already exposed, climate- and case-blind
terrain windows. It compares source products; it is not a new blind transfer
test and has no pass label.

Native GLO-90 is not the Issue 13 `r90` variant. That variant is the strict
arithmetic mean of complete 3 by 3 blocks on the GLO-30 `p00` grid. This
calculation does not substitute GLO-90 into Issue 19, revise its stopped
probability-sample result, open any selected-cell raster, estimate a global
terrain total, identify unstable slopes, map hazard, or infer climate
attribution.

## Frozen exposed windows and inherited functional

Use the three post-outcome development windows from regions 03, 07, and 08
and the four previously blind, now exposed transfer windows from regions 04,
10, 15, and 18. Retain their exact coordinates, keys, digests, GLO-30 `p00`
rasters, PZI rasters, RGI subsets, equivalent-area tables, and prior
aggregated-GLO-30 `r90` results. They span seven regions but do not constitute
a geographic probability sample.

For every grid, retain without change:

1. the local WGS84 Lambert azimuthal equal-area CRS centered on the reporting
   cell;
2. the densified one-degree reporting polygon and 1 km processing envelope;
3. the complete center disk within nominal radius 300 m and its plane
   gradient;
4. the tangent-gradient weight zero through 25 degrees, linear from 25
   through 35 degrees, and one from 35 degrees upward;
5. exact closed distance no greater than 100 m outside the union of relevant
   RGI 7 outlines;
6. the outside-RGI, finite PZI at least 0.1 mask; and
7. equivalent area equal to \(r^2\) times the sum of the weight at reporting
   centers satisfying the mask and complete-support rule, where \(r=30\) m
   for `p00` and \(r=90\) m for aggregated `r90` and native grids.

The local least-squares regression plane estimates a neighborhood tangent
gradient; it is neither a resolved terrain facet nor a stress calculation.
The 25--35 degree ramp is a deterministic screening weight, not a
constitutive law or failure probability. Equivalent steep area is the
integral of that weight over a registered mask, not literal susceptible area.

The source epochs and physical limits remain unchanged: RGI 7 approximates
year 2000, Copernicus DEM source acquisitions span 2011--2015, and PZI uses
1961--1990 air-temperature inputs. RGI proximity does not establish present
glacier contact or lost support, and PZI does not measure local ground
temperature.

## Pre-access source freeze

The first pre-access freeze was rejected in independent audit before any
request or payload access. This version supersedes it by sealing the complete
import graph and runtime, closing the raw-response population, registering
ordered typed schemas, and making incomplete support unresolved.

Before requesting a GLO-90 object, commit and independently approve the exact
protocol, expected-source table, program, tests, environment, frozen-window
table, inherited input hashes, output schemas, and pre-access manifest. The
expected source population is the fixed 3 by 3 neighborhood around each of
seven reporting cells: 63 cell--object request incidences. Candidate order is
frozen window order, then increasing latitude, then increasing normalized
longitude. Repeated object identities would remain repeated incidences in the
expected table but would be requested only once; the frozen windows produce
63 distinct identities.

Use only the anonymous Registry of Open Data on AWS object endpoint

`https://copernicus-dem-90m.s3.amazonaws.com/<key>`

with exact key `<stem>/<stem>.tif`, where `<stem>` is
`Copernicus_DSM_COG_30_NSLL_00_EWLLL_00_DEM`.

Send one GET per distinct key after approval. Retain every response body,
status, selected response headers, timezone-aware ISO-8601 retrieval time,
byte count, and SHA-256.
HTTP 404 is a retained missing-source result. Any other non-200 status stops
after its response is recorded. Interrupted acquisition may reuse only an
ordered-prefix ledger-bound response whose identity fields, canonical path,
byte count, SHA-256, and allowed status still agree. Duplicate identities,
reordered or misassigned rows, and any retained status other than 200 or 404
stop before another request. Ledger and manifest replacement is atomic.

The acquisition action may not import Rasterio or open any payload. It writes
a raw-source manifest after all requests finish. Commit and independently
approve that exact manifest and its response files before the analysis action
opens a raster.

## Native grids and comparisons

For each window, derive the primary native target grid from the exact inherited
GLO-30 `p00` grid after strict 3 by 3 aggregation: retain its shape, 90 m
spacing, and affine origin. Warp each available native GLO-90 COG independently
to that grid with bilinear interpolation, Float32 destination values, source
nodata, and destination NaN. Combine sources in frozen candidate order. Missing
coverage remains NaN.

Before reprojection, require each HTTP-200 payload to be a tiled, one-band
Float32 GeoTIFF in EPSG:4326 with `AREA_OR_POINT=Point`, 1,200 north--south
posts at 3 arc seconds, and 1,200 divided by the DGED longitude reduction
factor posts. The AWS COG transformation removes the shared east and south
edge posts. The first post center must equal the ledger geocell's northwest
integer-degree corner and the last must lie one native interval inside its
southeast corner. Require the exact north-up affine: positive longitude scale,
negative latitude scale, zero skew and rotation, and the RasterPixelIsPoint
half-pixel corner origin. A payload with another resolution, footprint, axis
order, or ledger identity stops the calculation.

Evaluate four native target-grid origins: the inherited origin `n00`, then
half-pixel translations `nx45`, `ny45`, and `nxy45` at (45, 0), (0, 45), and
(45, 45) m. Retain the same array shape; the 1 km envelope exceeds the 300 m
complete-support disk plus the 45 m translation. These phases quantify target
grid-origin sensitivity only and add no source resolution.

For each window, phase, and mask, retain source counts, reporting-center
counts, finite DEM centers, complete-support centers, mask centers,
integration centers, support status, weight sum, and equivalent area. A
glacier-proximity result is unresolved if any masked reporting center lacks
complete DEM support. A permafrost result is also unresolved if PZI is missing
at any outside-glacier reporting center, because an unobserved value could
enter the mask. Unresolved weight sums and areas are missing, not zero. The
long table contains
7 by 4 by 2 = 56 rows. For each of 14 window--mask pairs, report:

- the inherited GLO-30 `p00` reference area;
- the previously calculated aggregated-GLO-30 `r90` area and fractional
  departure;
- the primary native-GLO-90 `n00` area and fractional departure;
- native phase mean and coefficient of variation; and
- primary finite-center and complete-support fractions.

If all four native phases have complete support and the GLO-30 reference is
positive, fractional departure is absolute area difference divided by that
reference. If all reference and compared areas are zero, label a structural
zero and retain zero departure. A zero reference with any positive compared
area is unresolved and retains missing aggregated and native departures.
When the reference is zero, a group with incomplete native support likewise
cannot establish the all-zero condition, so both departures remain missing.
With a positive reference, incomplete native support retains missing native
summaries and native departure while the aggregated-GLO-30 departure remains
defined. It cannot be structural zero. No threshold is applied and no
development result is called a pass or fail.

## Outputs and review

The source action writes `expected_sources.csv`, `source_ledger.csv`, and
`raw_source_manifest.json`. The analysis writes `equivalent_area_long.csv`
and `comparisons.csv`. After independent result review, retain an executed
notebook with at most 50 code lines, a non-map figure comparing native and
aggregated departures with native support and phase sensitivity visible,
updated manuscript source and PDF, and a final manifest.

`output_schemas.json` fixes the source-ledger, raw-manifest, and output-table
field names, order, types, and row or entry counts. The
pre-access and raw-manifest command lines require the independently approved
manifest SHA-256, and runtime versions are rechecked at both gates. The raw
manifest must contain exactly the ordered 63-row ledger and every canonical
response path, with no unlisted response eligible for raster opening.

Handwritten source plus tests may not exceed 320 lines. Add no class or new
scientific dependency; the existing Rasterio `affine` dependency is pinned
explicitly. Tests cover frozen identities, key formatting,
longitude normalization, action separation, pre-access and raw-manifest
verification, target-grid origin shifts, row conservation, positive and zero
reference rules, and forbidden sample, event, climate, and hazard inputs.

The result may specify a source-transfer estimator and decision rule for a
later hash-selected blind test. It cannot itself validate native GLO-90 beyond
these seven exposed windows or authorize a new probability-sample total.

## Sources fixed before access

- Copernicus DEM Product Handbook, version 5.0:
  https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf
- Registry of Open Data on AWS, Copernicus DEM:
  https://registry.opendata.aws/copernicus-dem/
- AWS Copernicus DEM COG dimensions and edge-post conversion:
  https://copernicus-dem-90m.s3.amazonaws.com/readme.html

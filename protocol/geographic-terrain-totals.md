# Design-based totals of the frozen terrain-screen functional

Version 0.4. Version 0.1 was registered in GitHub issue
[#19](https://github.com/bradlipovsky/mass-movements/issues/19) on 31 August
2026 before retrieving or opening any DEM or PZI value for an issue #17
selected cell.

After independent approval of version 0.1, the 15 exact retained COG byte
sequences identified below were copied into the new raw cache while the
source-freeze code audit was still pending. No raster array, subset, coverage
value, or equivalent-area value was opened or calculated. The first bulk
external-download command was rejected during local option parsing before any
request was sent. Version 0.2 responds to that source-freeze audit before the
first external DEM/PZI retrieval: it pins every imported module, reconstructs
population counts from the complete frame, requires a raw-byte manifest before
raster staging, and strengthens RGI duplicate and repair checks. None of these
changes uses a terrain value.

After version 0.2 and the raw-source freeze were committed, deterministic
raster staging was stopped on 31 August 2026 when an independent geometry
audit found that 14 projected RGI incidences exceeded the registered
`1e-10` repair-area tolerance. At the stop, 170 DEM phase rasters and 42 PZI
rasters existed: 42 complete cell bundles and two DEM phases for the next
cell. No replay table, coverage table, repair ledger, or equivalent-area value
had been written, printed, summarized, or inspected. A single complete-support
operation had previously been timed on one `p00` raster; only its 17.93 s
runtime and 453,684 kB maximum resident set size were observed or retained.

Version 0.3 is the geometry-only correction registered publicly before code
modification or staging resumption. It changes the maximum relative area
change allowed independently in projected and round-trip geodesic area from
`1e-10` to `1e-8`. The largest audit-observed change was `4.87e-9`, and every
absolute projected-area change was below one square metre. All polygonal,
nonempty, and validity stops remain. Partial derived rasters are preserved;
deterministic staging restarts from its beginning and may overwrite those
files only by the same registered construction. The next staged manifest also
seals all 96 RGI subset GeoJSON files. This correction used RGI geometry, not
DEM or PZI values, coverage, masks, or equivalent areas, and requires
independent approval of its exact commit before raster staging resumes.

Independent review of the exact version 0.3 commit found two additional
pre-resumption gates. The immutable version 1.0 raw manifest correctly seals
the pre-amendment protocol, program, and test bytes, so it rejects the amended
program; and the amendment test checked the constant but not its behavior.
Version 0.4 preserves that original manifest unchanged and adds a successor
pre-raster manifest. The successor inherits all 2,514 identities, updates only
the amended tracked identities, includes the original manifest and stop
record, and newly seals all 96 RGI subset GeoJSONs. No external-source identity
may change. It also directly tests passing below and at `1e-8`, independent
projected and geodesic failure above it, and the unchanged nonpolygonal, empty,
and invalid-result stops. This correction was registered publicly before
modification and still requires independent exact-commit approval before
staging resumes.

## Question and boundary

Estimate the stratified design-based finite-population total of the issue #15
unshifted 30 m equivalent steep-area functional over the 1,826-cell issue #17
target population, separately for RGI-outline proximity and PZI intersection.
The calculation does not validate unstable slopes, compare failing with
non-failing terrain, infer climate effects, estimate incidence, or map hazard.

Selected cell identities, RGI frame geometry, inventory attributes, and beacon
material are already exposed. Until this protocol commit receives independent
pre-outcome approval, do not retrieve, open, summarize, probe, or map any DEM
or PZI value for a selected cell. Freeze these identities:

| object | identity |
|---|---|
| issue #17 frame commit | `0ff1c327468b5fb874ef2f87b1d64107838418e5` |
| issue #17 executed sample commit | `6afdbf2a509a27c2b574392a296e6c119d8f53d6` |
| `frame.csv` SHA-256 | `482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879` |
| `randomized_frame.csv` SHA-256 | `14db0fffd4d46c52b5cea7cba29c783d958aa94fefca8dd67e210df1a8134022` |
| `sample.csv` SHA-256 | `1e9164813893e285aeeeaa1a7833e16c87172cbe4d3357e245854ab13966613b` |
| issue #13 estimator commit | `acec6401bfa02b20d375e03d3eb82910148edf90` |
| estimator program SHA-256 | `15f7bff92b7ae44e5f64eac0db70598eb0f318f9a6ac5e2e689e5de9bc89e231` |

Pin the inherited numerical stack before access:

| imported program | SHA-256 |
|---|---|
| `scripts/denominator_pilot.py` | `5f733147434f859ea3cbfc815da77a1bd8ae83137d80e59a65243d6d3e23508a` |
| `scripts/susceptible_area_convergence.py` | `9ac2644257ce1ba90bd8f2edbc6e9b47ea152fa02304b0c4b994e495a512b20c` |
| `scripts/scale_explicit_transfer_source.py` | `c495d3b587e40ed6ad036a24857dc6fb6ee4bb0934e0c385d82e8bd7ba259830` |
| `scripts/geographic_sample.py` | `21bb6d250f67aa55c42f8efabe3302a2a0a045c950f1455805e2e0ba2cb4faaa` |

The numerical environment is Python 3.12.11, NumPy 2.5.2, SciPy 1.18.1,
Rasterio 1.5.1, Shapely 2.1.2, PyProj 3.7.2, Fiona 1.10.1, and Pandas 3.0.5.

No replacement, redraw, deletion, sample expansion, or outcome-dependent
source change is allowed. No selected cell exactly repeats an issue #15 blind
window. Previously retained raw source objects may be reused only after their
URL, version, byte count, and SHA-256 agree; no derived issue #15 grid, subset,
coverage value, or outcome may be reused.

## Frozen cell functional

For each selected reporting cell, call the issue #13 estimator directly and
retain without change:

1. a local WGS84 Lambert azimuthal equal-area CRS centered on the cell;
2. reporting edges densified at 0.01 degree, a 1 km processing halo, and the
   reporting-center inclusion rule;
3. the complete center disk within nominal radius 300 m and its
   vertical-residual plane gradient;
4. tangent-gradient weight zero through 25 degrees, linear from 25 through 35
   degrees, and one from 35 degrees upward;
5. exact closed planar distance at most 100 m outside the union of every
   relevant RGI 7 outline;
6. the outside-RGI, finite PZI at least 0.1 mask;
7. independently bilinear-warped 30 m phase grids `p00`, `p10`, `p01`, and
   `p11`, plus the aligned strict arithmetic mean of complete 3 by 3 unshifted
   blocks `r90`;
8. nearest-neighbor PZI warp, strict complete DEM support, and Float32 source
   arrays; and
9. equivalent area `E = spacing^2 sum(report mask complete weight)`.

The primary outcome is `p00`. Glacier-outline proximity and PZI intersection
can overlap and remain separate. Neither is physical terrain-surface area,
susceptibility, unstable-slope area, failure probability, incidence, or hazard.

For each cell-mask pair retain all five variants. Apply the issue #15
diagnostics exactly:

```text
D = abs(E90 - E00) / E00
CV = population_sd(E00, E10, E01, E11)
     / mean(E00, E10, E01, E11).
```

A positive finite reference has numerical labels `D <= 0.20` and `CV <=
0.10`. Set the inherited numerical label `structural_zero=yes` exactly when
all five finite equivalent-area values are zero after the source and replay
gates. Set `D=NA`, `CV=0`, and `usable_transfer=no`. Independently set
`coverage_limited_zero=yes` when any mask-true center lacks complete DEM
support in any variant or, for PZI, any outside-RGI center lacks finite PZI;
otherwise set `adequate_coverage_zero=yes`. If `E00=0` and any variant is
positive, set `D=NA`, retain the finite phase CV when defined, and fail
numerical quality. Preserve every failure. These labels do not alter units,
outcomes, or weights.

## RGI geometry staging

Reuse the 19 issue #17 regional archive byte sequences only after verifying
their recorded hashes. For every selected cell, construct the registered
densified reporting polygon in its local projection, buffer it by 1,100 m, and
inverse-project that envelope to WGS84. From all 19 regions retain the full,
unclipped, unsimplified geometry and identifier of every outline intersecting
an envelope. The extra 100 m beyond the processing halo includes all geometry
that could affect the closed proximity predicate. Dominant sampling region is
not a geometry-source filter. Deduplicate by RGI identifier and stop on a
duplicate with unequal geometry or attributes.

Apply GEOS linework `make_valid` only when a valid WGS84 geometry becomes
invalid after projection. Record cell, RGI ID, original validity, reason,
input/output type, geodesic and projected area before and after, both relative
area changes, GEOS, Shapely, PROJ, and CRS. A nonpolygonal result, empty result,
or either geodesic or projected relative area change above `1e-8` stops
execution. Geometry repair never
changes the sample, reporting cell, or frozen mask equation.

No sampled cell crosses the antimeridian. Still test longitude normalization,
tile identifiers, and synthetic cross-dateline geometry so the loader cannot
silently acquire the wrong source branch.

## Copernicus DEM staging

Use the public Copernicus DEM GLO-30 native 1 arc-second COGs at

```text
https://copernicus-dem-30m.s3.amazonaws.com/<stem>/<stem>.tif
```

where the literal stem is
`Copernicus_DSM_COG_10_<N|S><latitude>_00_<E|W><longitude>_00_DEM`.
For every selected integer-degree cell enumerate the 3 by 3 native tile origins
whose latitudes are `south-1` through `south+1` and whose longitudes are
`west-1` through `west+1`, in increasing integer latitude then normalized
numeric longitude order. Deduplicate the resulting object list before access.
The frozen sample produces 776 unique objects from 864 cell-object incidences.

Preserve every available COG in full with request URL, retrieval UTC, exact
headers, status, byte count, ETag, last-modified value, and SHA-256. Preserve a
404 in the unavailable-object ledger; do not create a zero raster. Exactly 15
objects match issue #15 raw COG identities and can be reused only after the complete
identity check above.

For each phase, build the registered equal-area grid over the densified
reporting polygon buffered by 1 km. The `p00` shape is extended to multiples of
three. Warp native elevations bilinearly and replace a prior overlap only with
a finite value, in the frozen source order. Store Float32 phase arrays and
their transforms. Build `r90` only by strict aligned 3 by 3 aggregation of
`p00`; do not warp a 90 m DEM independently.

## PZI staging

Use the Gruber 2012 UZH `PZI.flt` distribution and its frozen header, README,
and rights metadata. Its grid has 43,200 columns, 18,000 north-to-south rows,
30 arc-second cells, little-endian Float32 encoding, intrinsic latitude domain
`[-60,90)`, and nodata `-9999`.

For an ordinary cell, retain the 144 complete global rows spanning the source
collar from `south-0.1` through `south+1.1`. If rows are numbered from zero at
the north, the first row is

```text
r0 = round((90 - (south + 1.1)) * 120),
byte_start = r0 * 43200 * 4,
byte_end = byte_start + 144 * 43200 * 4 - 1.
```

Deduplicate cells with the same south edge, producing 54 request bands. The
selected cell whose south edge is `-60` clips the exterior staging collar at
the intrinsic lower bound: its north edge remains `-58.9`, `r0=17868`, and it
retains rows 17868 through 17999, or 132 complete rows. Its reporting centers,
nearest-neighbor mask, and outcome are unchanged. No out-of-domain value is
requested or imputed.

For each cell, copy the registered longitude columns from `west-0.1` through
`west+1.1` without value resampling, then nearest-neighbor warp this subset to
each equal-area phase grid. Preserve nodata as nodata, not background zero.
The sample has no cross-dateline PZI subset. One issue #15 full-row band at
`south=-44` may be reused only after exact request-range, URL, byte, and hash
agreement.

## Source gate before output

Separate source staging from outcome execution. Before calculating the first
equivalent-area value, commit:

- complete request and unavailable-object ledgers;
- raw-source hashes and exact HTTP records;
- RGI subsets and any projection-repair ledger;
- four DEM phase grids and one PZI subset per selected cell;
- exactly 480 replay rows: five stored input layers for each of 96 cells;
- exactly 480 coverage rows: five variants for each of 96 cells;
- loader/wrapper code, tests, software versions, fixed output schemas, module
  hashes, and a pre-output manifest.

Reconstruct every stored DEM phase and PZI subset from retained raw source
bytes. Require equal shapes, affine transforms, coordinate systems, little-
endian C-order value hashes, finite/nodata masks, and zero maximum absolute
difference. Verify `r90` against strict aggregation of the replayed `p00`.

For each cell and variant record `report_center_count`,
`complete_dem_support_count`, `glacier_predicate_coverage_count`,
`glacier_proximity_center_count`, `outside_RGI_center_count`,
`outside_RGI_finite_PZI_count`, source-object count, and missing-object
identities. Predicate coverage is computability, whereas proximity-center count
is predicate truth; never conflate them. Valid staged RGI geometry gives
glacier predicate coverage at every reporting center.

For each source dimension form the cell fraction $q_i=C_i/R_i$: complete DEM
support over reporting centers, glacier-predicate coverage over reporting
centers, and finite PZI over outside-RGI centers. When a cell has no outside-RGI
center, its PZI coverage fraction is one by the vacuous-coverage rule. Estimate
and report the finite-population mean cell fraction and its stratified variance:

```text
qbar_hat = (1/N) sum_h N_h mean_sample_h(q_i)
Var(qbar_hat) = (1/N^2) sum_h
  N_h^2 (1 - n_h/N_h) sample_variance_h(q_i) / n_h.
```

Separately HT-expand the covered and denominator grid areas, using count times
`spacing^2`, and report their descriptive ratio by variant and source
dimension. Label this area ratio separately from the mean cell fraction. Neither
coverage summary reweights the equivalent-area outcome.

A cell is computable only if every variant has at least one complete-DEM-
support reporting center, RGI predicate coverage equals reporting-center count,
and either no outside-RGI center exists or at least one has finite PZI. A
nonfinite or negative equivalent-area value is also uncomputable. Failure stops
the complete total. Documented COG 404s and internal nodata otherwise remain
part of the frozen complete-support and finite-PZI numerical functional and its
coverage summaries. Partial coverage is explicit; nodata never becomes
physical zero.

Any cache mismatch, replay mismatch, grid-anchor mismatch, geometry failure,
out-of-domain PZI extraction, or uncomputable selected outcome stops
without replacement. Obtain independent source, numerical, and mechanics
approval of this source-freeze commit before execution.

## Atomic execution

Verify every frozen byte and module hash at start. Process cells serially to
bound memory, but retain the 960 result rows (`96 cells * 5 variants * 2
masks`) in memory. Do not print, write, summarize, plot, or inspect a partial
equivalent-area result. Only after every cell and variant completes may the
program atomically write the complete long table. A necessary correction after
outcome access stops the run and records what was persisted, printed,
summarized, or observed.

From the complete table write exactly 192 primary cell-mask diagnostic rows,
38 region-mask variance-contribution rows, 19 regional covariance rows, and
two total-estimate rows. Preserve deterministic schemas and LF endings.

## Frozen inference

Within dominant-region stratum `h`, use the issue #17 population and sample
counts `N_h` and `n_h`. For sampled primary outcome `y_his`, calculate

```text
T_hat_s = sum_h N_h mean_h(y_his).
v_hs = N_h^2 (1 - n_h/N_h) sample_variance_hs / n_h.
V_hat_s = sum_h v_hs.
SE_s = sqrt(V_hat_s).
RSE_s = SE_s / T_hat_s              when T_hat_s > 0.
```

Sample variance and glacier--PZI covariance use divisor `n_h-1`. Reconstruct
weights and counts from the complete frozen frame, never only the observed
sample. Verify within every stratum that the sample Horvitz--Thompson expansion
of unit constants equals `N_h`.

For positive non-census variance contributions use

```text
nu_s = (sum_h v_hs)^2 / sum_h[v_hs^2/(n_h-1)].
CI_s = T_hat_s +/- t(0.975, nu_s) SE_s.
```

The interval is untruncated. If every contribution is zero, set
`nu=infinity`, use 1.96, and report the degenerate interval. A nonpositive or
nonfinite total has undefined RSE and fails precision. Because every populated
stratum is sampled rather than censused, estimated `RSE=0` also fails the
conservative precision objective. Precision passes exactly when RSE is finite
and `0 < RSE <= 0.25`. The secondary mean is `T_hat_s/1826`.

For within-stratum sample covariance `s_h,GP`, estimate

```text
Cov_hat(T_G,T_P) =
  sum_h N_h^2 (1 - n_h/N_h) s_h,GP / n_h.
```

Census variance contributions are zero. Report every stratum total,
variance contribution, covariance contribution, degrees of freedom, interval,
RSE, and cell value. The Satterthwaite interval approximates sampling variation
only; it excludes product coverage, phase/resolution sensitivity, and source
error.

A mask total is numerically resolution/phase robust only if all 96 cell-mask
records have a positive reference, finite diagnostics, `D <= 0.20`, and `CV <=
0.10`. A joint label requires both masks. This intersection label does not
alter the `p00` total. Retain the no-gate frame-only balance result that zero of
56 multi-region frame cells were selected, whose registered design probability
is 0.0120688274. It does not alter the HT estimator but prevents a cross-region
subgroup estimate.

Preserve every result and the fixed prefix. Precision or numerical-quality
failure permits no added unit; expansion requires a future public protocol and
new randomization before outcomes are opened.

## Products, limits, and review

RGI 7 approximates year 2000, Copernicus source acquisitions span 2011--2015,
and PZI uses 1961--1990 air-temperature inputs. The calculation is not a
contemporaneous Earth state. RGI proximity does not demonstrate present
glacier contact or lost mechanical support. PZI does not measure local ground
temperature.

Commit the source records, 480 replay rows, 480 coverage rows, HT coverage
summaries, the 960-row long table, 192 primary diagnostics,
38 variance rows, 19 covariance rows, two estimates, quality summaries,
notebook, figure, manuscript, compiled PDF, and final manifest. The executed
notebook contains at most 60 code lines. A non-map figure shows (a) the two
separate totals with 95% design intervals and RSE; (b) cell contributions and
design weights together with regional total and variance contributions; and
(c) the 90 m departure and four-phase CV distributions. It must not combine
overlapping outcomes or portray hazard.

Handwritten source plus tests may not exceed 500 lines. Target about 140 lines
for source/staging, 150 for execution/inference, and 180 for tests. Add no
dependency or class. Tests emphasize estimator and source identity, PZI lower-
edge clipping, grid anchors, replay, boundary and synthetic antimeridian
geometry, exact masks, strict support, zero/missing distinctions, HT totals,
variance, covariance, degrees of freedom, probability identities, schemas,
and forbidden outcome-dependent inputs.

Independent source, numerical/statistical, mechanics, figure, and manuscript
audits must approve. Conclusions remain conditional terrain-screen totals for
the registered RGI/PZI frame, not physical susceptibility, incidence, climate
attribution, exposure, consequence, or hazard.

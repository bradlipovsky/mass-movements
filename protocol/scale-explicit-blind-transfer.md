# Blind transfer of the frozen equivalent steep-area estimator

Version 0.1. Registered in GitHub issue
[#15](https://github.com/bradlipovsky/mass-movements/issues/15) on 31 August
2026 before retrieving any new RGI attribute, DEM, or PZI value.

## Question and inferential boundary

Issue #11 rejected hard pixel-threshold area as a numerical denominator because
30-to-90 m departures exceeded 0.20 in two held-out windows. Issue #13 then
selected a nominal-support regression plane, continuous gradient weight, and
exact glacier-outline proximity representation using those exposed results.
This protocol asks whether that exact estimator meets fixed resolution and
phase criteria in previously unopened regions.

The test is confirmatory only for numerical transfer. It does not test whether
mapped terrain fails, whether the strata resemble event source areas, whether
warming changes incidence, or whether any place is hazardous. Even a passing
result does not estimate a global distribution: four hash-selected windows are
not probability samples of mountain terrain. Passing can motivate a separate
geographic sampling design; failure stops use of this estimator as a global
denominator in the present project.

No failure catalog, candidate, source-coordinate audit, event time,
reanalysis value, climate variable, deformation signal, damage report, or
consequence may enter selection, processing, or interpretation.

## Region freeze before inventory retrieval

Exclude every RGI region used by the terrain pilot or exposed method
development: 01, 03, 07, 08, 11, and 13. The unopened literal codes are

```text
02 04 06 09 10 12 14 15 16 17 18
```

Rank each code by the hexadecimal SHA-256 digest of the UTF-8 string
`susceptible-area-heldout-v1|RR`, reusing the issue #11 selector. The complete
order, calculated without inventory or terrain access, is

| rank | RGI code | digest |
|---:|:---:|---|
| 1 | 10 | `5b16eb47c0f2b54bea77eabd0dea16b33b9bdd8a9783f0c5049511d56a08cf9e` |
| 2 | 18 | `639be755f4b9273620eb69e3d29225955514d050c7b77f3564f5086fe65c4f60` |
| 3 | 15 | `69d3cfbe87ae15f42742f7a7fbd17c3b1d7b446bc522bee3793df72d0556719f` |
| 4 | 04 | `73ee9d1d5eecc4ea0cf63fe6fae52e0b8148ed6e5e463cb1e0da65d01e20bb47` |
| 5 | 12 | `86c171ea94690571e01af2467eea98e8acdf54a5f4089d03b4d479015343951f` |
| 6 | 14 | `a724c4a3f9cf086c93d020feddd6105744b120487c221a1a4c82f536eb59c1b8` |
| 7 | 09 | `aa966d03c2d1f57875d90d8aa6fad21e9e1f72222bc186f4d082e83a80f64db5` |
| 8 | 06 | `cb4cf243343e18258e43bf8e70f871aacd8bc287237e4854d052d523525ab113` |
| 9 | 02 | `de0f00939b8b4f18ca216800ae3130d720bb4cd2efa3da06704560135cd0f35f` |
| 10 | 16 | `ea8a3d9332666f32e9800ed5cc34d4d5734f2d6b129fbad4ff2d06d6f59aa24c` |
| 11 | 17 | `fcfeb3b6c1d57a5daecf2c8d2772771bf6de680272002ae985f57fbf226cd9b3` |

Fix the first four codes: 10 (North Asia), 18 (New Zealand), 15 (South Asia
East), and 04 (Arctic Canada South). No region replacement is allowed.

## Inventory-only window selection

After this protocol commit, retrieve only RGI 7.0 attributes and geometry for
the four fixed regions. Use the archived approximately central longitude and
latitude and inventory area fields. Wrap longitude to `[-180, 180)`, group
records by `(floor(latitude), floor(longitude))`, and retain a cell exactly
when it contains at least 10 records and at least 1 km2 of summed inventory
area. For each eligible cell construct

```text
rgi7.0|RR|south=SSS|west=WWWW
```

where south uses signed width 3 and west signed width 4, including leading
zeros. Hash the UTF-8 string
`susceptible-area-heldout-window-v1|<window-key>` and select the cell with the
smallest hexadecimal digest in each region.

Before retrieving or opening any DEM or PZI value, commit the downloaded RGI
object hashes, complete eligible-cell table, selected-window table, selector
code and tests, software versions, and selection manifest. A region with no
eligible cell stops the test. Sparse terrain, missing later source coverage,
or an unfavorable expected result cannot replace a selected cell.

## Estimator frozen by reference

The estimator is the issue #13 implementation approved before its first
execution:

```text
commit: acec6401bfa02b20d375e03d3eb82910148edf90
scripts/scale_explicit_steep_area.py
sha256: 15f7bff92b7ae44e5f64eac0db70598eb0f318f9a6ac5e2e689e5de9bc89e231
```

Retain without change:

1. the complete cell-center disk within a nominal 300 m radius and its
   vertical-residual plane coefficients;
2. the tangent-gradient weight that is zero at or below 25 degrees, linear to
   35 degrees, and one thereafter;
3. exact `dwithin(G, point, 100 m)` outside-glacier inventory-outline
   proximity;
4. the outside-glacier, finite PZI at least 0.1 stratum;
5. four independently warped 30 m DEM phase grids at offsets `(0,0)`, `(15,0)`,
   `(0,15)`, and `(15,15)` metres;
6. the aligned strict arithmetic mean of complete 3 by 3 unshifted DEM blocks;
7. local WGS84 Lambert azimuthal equal-area projection, 1 km processing halo,
   nearest-neighbor PZI sampling, and reporting-center rule;
8. equivalent steep area `E = r^2 sum(R I w)`; and
9. unshifted 30 m `E0`, fractional departures, population phase CV, and zero
   rules.

The validation wrapper must verify the estimator hash at start and call its
registered gradient, weight, exact-distance mask, integration, and comparison
functions directly. It may generalize only the issue #11 source loader to the
new frozen directory. Hash all imported project modules before execution.

Do not alter the radius, sampled stencils, ramp, masks, distance, threshold,
grid construction, aggregation, resampling, reporting polygon, integration,
or zero handling after a new terrain value is read. A necessary implementation
correction must stop execution, preserve the attempted version, and document
whether any validation output was already inspected.

## Source freeze after window selection

Only after the selected-window commit, retrieve the same products and fields
as issue #11:

- Copernicus DEM GLO-30 elevation tiles under the same attribution and access
  terms;
- the Gruber global PZI grid, with WGMS as source, Gruber as creator, and UZH
  as publisher; and
- RGI 7.0 outlines with official collection and attribute metadata.

Record URL, retrieval UTC, HTTP status, response metadata, bytes, and SHA-256
for every remote and local object. Retain missing-tile records. Independently
replay each stored DEM phase array from its source tiles and each PZI subset
from the frozen global object. Report coverage at reporting centers separately
for DEM support, PZI, glacier proximity, and PZI intersection. Product epochs
remain distinct and cannot be described as contemporaneous terrain.

Freeze all local sources, coverage records, replay tables, loader/wrapper code,
tests, environment versions, and a pre-output manifest before calculating the
first equivalent-area value. No validation summary or partial region result is
printed until all four regions and five variants have completed.

## Confirmatory decisions

For region `j` and stratum `s`, let `E0` be the unshifted 30 m equivalent area,
`E90` the aligned 90 m value, and `E1,...,E4` the four 30 m phase values. Define

```text
D_js = abs(E90 - E0) / E0
CV_js = population_sd(E1,...,E4) / mean(E1,...,E4).
```

An ordinary window passes exactly when `E0 > 0`, `D_js <= 0.20`, and
`CV_js <= 0.10`. If every variant is zero, record `structural_zero=yes` and
`usable_transfer=no`; this does not pass. If `E0=0` and any variant is
positive, departures are undefined and the window fails. Any other undefined
diagnostic fails.

A stratum passes only if all four of its windows pass. The estimator passes
the transfer gate only if both strata pass. Report all eight window decisions,
the two stratum decisions, and the overall decision without replacement.
There is no multiplicity adjustment because this is one intersection-union
gate with every registered condition required. Do not add component ablations,
alternative tuning choices, or replacement regions after opening output.

## Outputs, checks, and budget

Write a 40-row long table, eight window decisions, two stratum decisions, and
one overall decision. The executed notebook and manuscript figure show all
phase ratios and decision diagnostics, including structural zeros or failures.
No event marker or mapped failure appears.

Tests must verify the literal region ranking, prefixed window digests,
eligibility thresholds and longitude wrapping, the issue #13 program hash,
loader grid anchors, strict aggregation, exact diagnostic equations, zero
rules, ordered output schemas, source hashes, replay agreement, line endings,
and rejection of catalog, candidate, audit, event, climate, reanalysis,
deformation, damage, and consequence input paths.

The pull request may add at most 500 handwritten source and test lines,
including changes to downstream tests. Notebook code has a separate target of
at most 60 lines. Stop and simplify rather than weaken the physical or
provenance definition. Generated tables, manifests, figures, notebooks, and
the manuscript are excluded from the handwritten source/test count.

## Stopping and reporting

Preserve a failed or structurally unusable transfer result. Do not describe a
passing numerical gate as susceptibility validation. Do not start a global
inventory, incidence calculation, or hazard map in this issue. Any geographic
scaling requires a new public sampling protocol, including a target population
and inclusion probabilities or an explicitly non-probability estimand.

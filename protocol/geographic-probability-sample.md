# Probability sample for near-global equivalent-area scaling

Version 0.1. Registered in GitHub issue
[#17](https://github.com/bradlipovsky/mass-movements/issues/17) on 31 August
2026 before retrieving any new RGI region for the geographic frame.

## Question and boundary

Issue #15 found that the frozen scale-explicit equivalent steep-area estimator
met its registered resolution and phase bounds in four hash-selected windows.
Those windows had no known inclusion probabilities. This protocol constructs a
finite geographic population and gives every unit a known, nonzero probability
of selection before any sampled-unit elevation or permafrost value is opened.

The target is not all mountain terrain. It is a near-global finite frame of
one-degree cells that intersect RGI 7 geometry and lie inside the Gruber PZI
latitude domain. The calculation will estimate the total of a frozen numerical
terrain functional over that frame. It will not validate susceptibility,
failure probability, present glacier support, climate association, runout,
exposure, consequence, or hazard.

This issue freezes the frame and probability sample only. It may use RGI
outlines and attributes to define the frame, but it may not retrieve or open
any selected-cell DEM or PZI value, including a value cached by an earlier
issue. Event fields, climate fields, deformation signals, damage reports, and
consequence fields are also forbidden. A later issue must register source and
execution details and pass an independent sample audit first.

## Finite target population

Let an integer-degree cell be the half-open WGS84 polygon

```text
[west, west + 1) x [south, south + 1),
```

where longitude is normalized to `[-180, 180)` and a value of `+180` belongs
to `-180`. The literal cell key is

```text
rgi7.0|global|south=SSS|west=WWWW
```

with signed, zero-padded integer coordinates.

The finite population `U` contains a cell exactly when:

1. its polygon has positive-area intersection with at least one RGI 7 outline
   from first-order regions 01--20; and
2. its integer south edge is from -60 through 89, inclusive, so all reporting
   centers lie in the intrinsic PZI domain `[-60, 90)`.

The second rule follows the PZI dimensions of 18,000 rows from 60$^\circ$S at
the product's nominal 1/120-degree spacing; it does not open the PZI
floating-point values. The literal header rounds the spacing to six decimal
places, so the frame uses the same exact 1/120-degree transform already frozen
in the source-replay code. Record cells removed by the latitude rule and their
intersecting RGI area. A polygon that only touches a cell boundary has zero
intersection area and does not establish eligibility. There is no minimum
glacier count or inventory-area threshold. RGI 7 defines region 20 for the
Antarctic Mainland but currently assigns it no glaciers and publishes no
region-20 outline archive. Retain the official region definition, distribution
index, and explicit zero contribution rather than inventing an empty package
or silently omitting the code.

Each geographic cell occurs once even when it intersects multiple RGI regions.
This avoids the spatial duplication that would result from treating a
region--cell pair as a sampling unit. For cell `u` and region `h`, form the
geometric union of all valid region-`h` RGI outlines, intersect that union with
the cell polygon, and calculate the absolute WGS84 geodesic area `A_uh` of the
intersection. Union area, not the sum of individually clipped outline areas,
defines the contribution. For stratification only, assign the cell to the
region with greatest `A_uh`; break an exact tie by the smallest literal
two-digit region code. The later glacier mask must nevertheless contain every
outline capable of affecting the cell, regardless of assigned region.

The RGI center coordinate does not determine membership. Frame membership is
based on outline intersection. RGI 7 is approximately a year-2000 inventory;
its geometry is not present-day glacier contact, retreat, unloading, or
buttressing. Cells have unequal geodesic areas. Record those areas and retain
them as auxiliary information, but define the primary estimand as a total of
the frozen per-cell functional rather than an equal-cell mean.

## Geometry ownership and topology

Candidate cells are enumerated from every RGI outline, then intersected with
half-open ownership implemented by unique integer keys. A reporting boundary
is not duplicated in the frame. The positive-area predicate makes inclusion
insensitive to a zero-area shared edge.

For an antimeridian-crossing outline or cell collar, unwrap longitudes about
the reporting-cell center before intersection or projection. Split remote
source requests at `-180/+180` and deduplicate features by `rgi_id`. Preserve
the original coordinates and record every unwrap or split. Tests must cover
cells with west `179` and `-180`, a polygon crossing the antimeridian, a polygon
touching but not entering a cell, and a cross-region cell.

Use the WGS84 ellipsoid through `pyproj.Geod` to calculate polygon and cell
areas. Apply Shapely 2 linework `make_valid` only when an input geometry is
invalid. Record the RGI ID, original validity explanation, input/output type,
geodesic areas, and relative change. Stop if a repair is non-polygonal, remains
invalid, duplicates an RGI ID, or changes absolute geodesic area by more than
`1e-10` relative. No buffered eligibility or area tolerance may turn a
zero-area contact into a population unit.

## RGI source freeze

Retrieve the available RGI 7 outline, attribute, and metadata packages for
first-order regions 01--19 only after this protocol commit. Separately retain
the official definition of empty first-order region 20 and evidence that the
regional distribution publishes no region-20 package. NASA CMR and DOI
`10.5067/F6JMOVY5NAVZ` define the authoritative collection identity. If an
authentication-protected NSIDC object cannot be retrieved, a consortium-author
mirror may supply bytes only when the filename, embedded version, region,
member metadata, URL, HTTP response, byte count, and SHA-256 are recorded. Do
not assert byte identity with the inaccessible authoritative object.

Before randomization, commit:

- all archive and extracted-member identities and hashes;
- the exact PZI header and hash used only for its latitude bounds;
- the complete unique-cell frame and latitude-exclusion ledger;
- cell area and RGI intersection area by contributing region;
- invalidity, repair, antimeridian, and duplicate-ID ledgers;
- dominant-region assignments and population counts `N_h`;
- fixed sample allocations `n_h` calculated below;
- selector source, tests, environment versions, and a pre-randomization
  manifest.

An independent audit must reconstruct the frame and allocation from the frozen
RGI members before a beacon value is used.

Handwritten source and tests in this pull request may total at most 500 lines.
The executed frame notebook may contain at most 60 code lines. Generated frame,
manifest, figure, notebook-output, and manuscript files are excluded from the
source/test count. Tests must emphasize geographic ownership, probability
identities, limiting cases, and byte-level artifact reconstruction.

## Fixed allocation

The total sample size is

```text
n = min(96, N),
```

where `N` is the number of eligible cells. Within each nonempty dominant-region
stratum `h`, start with

```text
n_h = min(4, N_h).
```

If these initial allocations sum to less than `n`, assign one remaining slot
at a time to a non-census stratum that maximizes `N_h / (n_h + 1)`. Resolve a
tie by the smallest literal region code. Stop when the allocations sum to `n`.
This rule is fixed before `N_h` is known and ensures four observations in each
non-census stratum whenever `N_h >= 4`. If `N <= 96`, every unit has inclusion
probability one.

## Future public randomization

The NIST Randomness Beacon 2.0 publishes a signed 512-bit output every 60
seconds and exposes time-indexed REST endpoints
(https://csrc.nist.gov/projects/interoperable-randomness-beacons/beacon-20).
It remains labeled a beta service; this protocol therefore defines a stopping
rule rather than an alternate seed.

After pushing the exact frame-freeze commit, post exactly one issue #17 comment
whose complete body is `Frame freeze: <40-character commit SHA>`. The named
commit must exist on the remote and contain the canonical frame and its
pre-randomization manifest. Preserve the comment ID and raw API response before
requesting the pulse. Require the complete body to remain exact and the GitHub
server fields `created_at` and `updated_at` to be identical; otherwise stop.
Let `t_public` be that `created_at` timestamp. Set

```text
t_target = t_public + 3,600,000 milliseconds.
```

Request the first available pulse at or after `t_target` through the NIST
`pulse/time/next/<t_target - 1 millisecond>` endpoint. The one-millisecond
subtraction is necessary because the `next` endpoint is strictly after its
argument. Accept the response only when all of the following hold:

1. `version` is `2.0`, `period` is `60000`, and `statusCode` is zero;
2. `outputValue` is exactly 128 hexadecimal characters;
3. the signed pulse timestamp is at least `t_target` and no more than 24 hours
   later; and
4. the response URI, chain and pulse indices, certificate identifier,
   signature, and previous-value link are present; and
5. the pulse signature verifies against the retrieved certificate under the
   NIST Beacon 2.0 canonical message definition, the certificate is valid at
   the pulse time, and the fetched previous pulse `outputValue` equals the
   response's `previous` list value.

Retain the exact request URL, retrieval UTC, headers, raw JSON bytes, SHA-256,
certificate response, verification command and result, and the prior pulse
referenced by the chain. If the certificate or signature cannot be verified,
or if no qualifying pulse is archived in the 24-hour interval, stop without a
fallback beacon, locally generated seed, changed frame, or delayed target.

Define `frame_sha256` as the lowercase hexadecimal SHA-256 of the canonical
committed `frame.csv` bytes, including its header and LF line endings.
Interpret `bytes.fromhex(outputValue)` as the 64-byte HMAC-SHA256 key. For each
frame unit calculate

```text
HMAC-SHA256(key=bytes.fromhex(outputValue),
            message=UTF8(frame_sha256 + "|" + cell_key)).
```

Stop if any two frame units have the same HMAC digest. Otherwise, within each
dominant-region stratum, order by hexadecimal digest and select the first
`n_h`. Commit the full randomized order, not only the selected prefix. No
outcome, coverage, expected terrain, earlier study-window identity, or
source-availability value may enter this order. Previously studied cells remain
eligible; if sampled, later source bytes may be reused only after identity and
processing equality are established.

## Inclusion probabilities

This is one-stage stratified simple random sampling without replacement.
Every reporting-center grid inside a selected cell is a deterministic census,
not a second sampling stage. For unit `i` in stratum `h`, record

```text
pi_i = n_h / N_h.
```

For two distinct units `i` and `j` in the same stratum, record or verify

```text
pi_ij = n_h (n_h - 1) / [N_h (N_h - 1)].
```

For units in different strata, `pi_ij = pi_i pi_j`. Census-stratum
probabilities equal one. Tests must verify that every target unit has positive
first-order probability, the selected row count is `min(96,N)`, there are no
duplicates, each selected count equals `n_h`, and all formulas use the frozen
frame counts.

## Frozen later outcomes and inference

For cell `u` and terrain stratum `s`, let `E_us` be the issue #15 unshifted
30~m (`p00`) equivalent steep area. The two outcomes are:

1. glacier-outline-proximity equivalent steep area; and
2. PZI-intersection equivalent steep area.

Their masks can overlap. Estimate and report them separately; never add the two
totals. A future execution must also calculate their overlap directly if a
combined measure is scientifically required. Their design covariance is
reportable without defining a union.

The finite-population total and stratified Horvitz--Thompson estimator are

```text
T_s     = sum_u E_us,
T_hat_s = sum_h N_h mean_sample_h(E_us).
```

For each non-census stratum with `n_h >= 2`, define sample variance with divisor
`n_h - 1`:

```text
s_hs^2 = sum_i (E_ihs - mean_hs)^2 / (n_h - 1).
```

Let `f_h=n_h/N_h` and `v_hs=N_h^2 (1-f_h) s_hs^2/n_h`. Use

```text
V_hat(T_hat_s) = sum_h v_hs,
SE_s            = sqrt(V_hat(T_hat_s)),
RSE_s           = SE_s / T_hat_s,
nu_s            = (sum_h v_hs)^2 / sum_h [v_hs^2 / (n_h - 1)].
```

Only non-census strata with positive `v_hs` enter the degrees-of-freedom sums;
a census stratum contributes zero. If every variance contribution is zero, set
`nu_s=infinity`, use the standard-normal 1.96 critical value, and report the
degenerate interval when `SE_s=0`. Otherwise report the untruncated interval
`T_hat_s +/- t_(0.975,nu_s) SE_s`. Define RSE only for a positive finite
`T_hat_s`; a zero, negative, or nonfinite total makes RSE undefined and fails
the precision objective. The secondary population mean is `T_hat_s/N`.

For the glacier-proximity (`G`) and PZI (`P`) outcomes, define within-stratum
sample covariance and its design estimator explicitly:

```text
s_h,GP = sum_i [(E_ihG - mean_hG)(E_ihP - mean_hP)] / (n_h - 1),
Cov_hat(T_hat_G,T_hat_P) = sum_h N_h^2 (1-f_h) s_h,GP / n_h.
```

Census strata contribute zero to this covariance estimator.

An RSE above 0.25 for either total fails the registered precision objective.
Preserve the 96-cell prefix and require a separately registered expansion; do
not add units after inspecting outcomes. Do not substitute a model-assisted or
ratio estimator for the primary result after seeing the sample. Such estimators
may be registered later as separate analyses.

The later calculation must retain the complete issue #15 estimator: four 30~m
phases, aligned 90~m grid, support radius, ramp, masks, distance predicate,
integration, comparisons, and zero rules. The primary total uses `p00`. A
resolution-and-phase-robust label additionally requires every sampled positive
reference to meet `D <= 0.20` and population phase `CV <= 0.10`. A structural
zero with adequate source coverage contributes zero to the total but fails the
numerical-quality label because it supplies no positive transfer evidence. A
zero reference with any positive variant or an undefined comparison also fails
that label. Regardless of this label, preserve and report the grid-specific
design estimate.

## Missingness and coverage

No sampled unit may be replaced. A source object with a missing tile, nodata,
or incomplete support remains part of the record. PZI staging at cells with
south `-60` or `89` must clip the former symmetric angular collar to the source
domain; no PZI value is required outside the reporting cell. Later processing
must report DEM complete-support, finite PZI, glacier-predicate, and
outside-glacier finite PZI coverage at reporting centers for every phase.

A selected cell that cannot be computed under the frozen sources stops the
full-frame total. Available-case reweighting is not a design-unbiased fallback.
Internal nodata that the frozen estimator excludes remains part of its
source-supported numerical functional and is summarized by design-weighted
coverage; it is never recoded as physical zero. Any coverage threshold or
partial-identification bound beyond these rules must be registered in the
later source protocol before opening a selected-cell value.

## Stopping and reporting

Stop before randomization if the frame, geometry ownership, source hashes,
topology rules, allocation, or independent reconstruction fails. Stop before
outcome access if the NIST response, certificate record, randomized order,
sample counts, or inclusion probabilities fail audit.

The frame notebook and figure must show the entire population and selected
cells without a terrain, event, or hazard value. The manuscript may describe a
probability sample for the frozen equivalent-area functional. It may not call
the frame all mountain terrain, call the PZI result global permafrost terrain,
add the two overlapping outcomes, or describe the later estimate as observed
susceptibility or hazard.

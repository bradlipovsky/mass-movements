# Blind native GLO-90 source-substitution gate

## Question and scope

This calculation asks whether replacing Copernicus DEM GLO-30 with the
separately processed native GLO-90 product preserves the frozen equivalent
steep-area functional within inherited numerical bounds in 18 previously
unevaluated, availability-conditioned terrain windows. It is a numerical
source-substitution gate, not a global estimator, physical validation, or
hazard analysis.

The functional remains a local plane-gradient screening integral. Its
25--35 degree ramp is not a failure law, and its output is not literal
susceptible area. RGI 7 outlines approximate year 2000, PZI represents a
1961--1990 air-temperature zonation, and Copernicus DEM acquisitions span
2011--2015. RGI-outline proximity is not present glacier contact or lost
support; PZI is not local ground temperature or measured permafrost.

## Eligible population frozen before selection

Begin with the 1,826-cell RGI-intersecting one-degree frame. Eligibility uses
only already sealed object-inventory metadata, prior sample identities, and
prior terrain-window identities:

1. require all nine cataloged objects for both GLO-30 and GLO-90, leaving
   1,411 cells;
2. exclude the 68 Issue 19 selected cells within those 1,411; and
3. exclude the eight previously terrain-exposed windows within those 1,411.

The result is exactly 1,335 cells. Counts for dominant RGI regions 01--18 are
103, 128, 139, 58, 220, 7, 22, 33, 33, 127, 18, 13, 225, 37, 47, 48, 75,
and 2. Region 19 has no cell satisfying dual full-halo support. The population
cannot test cells with missing cataloged objects, so it cannot show that
GLO-90 repairs GLO-30 gaps.

No DEM value, PZI value, derived array, mapped outcome, catalog event,
reanalysis result, climate variable, or case-study attribute may enter
eligibility or ranking. Commit and independently approve the exact candidate
table, upstream hashes, selector, tests, and preselection manifest before the
future pulse below is released.

## Future public randomness and selection

Use the first NIST Randomness Beacon version 2 pulse strictly after
2026-09-02T05:59:59.999Z, requested at the already published endpoint
`/beacon/2.0/pulse/time/next/1788328799999`. Require the returned time to be
exactly 2026-09-02T06:00:00.000Z, chain 2, cipher suite 0, 60,000 ms period,
and zero pulse and external status.

Retain the exact JSON response, preceding pulse, and certificate. Require the
already committed NIST signing-certificate identifier
`528943a555f5f8ca54423be6dfb95925a35c7b552046420e7d7cd072058a14d6536ad3a8e9754b6582f164a90b0cd86a65d659f5426a2659a947595d1c816c8c`
as SHA-512 of the leaf DER, verify the retained DigiCert intermediate against
the system root bundle at the target epoch, confirm certificate validity at
that epoch, and require the canonical NIST chain-2 URI. Verify the
preceding-pulse signature and output link;
require its precommitment to equal SHA-512 of the target local random value;
verify the target RSA PKCS#1 v1.5 SHA-512 signature over fields 1--19; and
verify `outputValue` as SHA-512 of that serialized message followed by the
raw signature. The deployed chain-2 wire
encoding uses big-endian integers, four-byte length prefixes for string and
hash fields, a four-byte external status, and no signature-length prefix in
the output hash. This exact encoding is frozen in the selector.

Use the 64-byte `outputValue` as the HMAC-SHA256 key. For each candidate,
hash UTF-8 `candidate_windows_sha256|cell_key`. Within each dominant region,
rank by ascending HMAC digest and then ascending cell key, and select rank 1.
The selection command must receive and match the independently approved
preselection-manifest SHA-256, require the exact closed manifest fields, and
reject any collision among all 1,335 HMAC digests. Retain all 1,335 ranks and
the 18 selected rows. Conditional on treating the
beacon output as random, each cell has first-order inclusion probability
1/N_h; same-region pair inclusion is zero. With one cell per region there is
no within-region design-variance estimate, confidence interval, or basis for
treating mask and phase repeats as independent observations.

## Functional and registered decision

For each selected cell, retain the inherited densified one-degree reporting
polygon, 1 km processing envelope, local WGS84 Lambert azimuthal equal-area
CRS, complete center disk of nominal radius 300 m, plane-gradient estimate,
25--35 degree tangent-gradient ramp, closed distance no greater than 100 m
outside relevant RGI 7 outlines, and outside-RGI finite PZI at least 0.1 mask.
Equivalent area remains spacing squared times the sum of screening weights at
registered reporting centers satisfying the mask and support rule.

Retain six variants for each of two masks: GLO-30 `p00`; strict complete 3 by
3 aggregated-GLO-30 `r90`; and native GLO-90 on `n00`, `nx45`, `ny45`, and
`nxy45` target-grid phases. Native GLO-90 is a separate source product, not
the strict GLO-30 aggregate. The three shifted native grids translate the
primary origin by (45,0), (0,45), and (45,45) m without adding information.

For every cell--mask pair define native primary departure as
`abs(E_native_n00-E_glo30_p00)/E_glo30_p00` and native phase CV as the
population standard deviation of the four native areas divided by their
mean. The primary gate requires complete DEM and mask support for `p00` and
all four native phases; missing secondary `r90` alone does not change it. A
pair passes only with a positive GLO-30 reference, departure no greater than
0.20, and phase CV no greater than 0.10. With complete primary support, a
zero reference and any positive primary variant is `FAIL`; if all five
primary areas are zero, record a structural zero and `INDETERMINATE` because
no relative transfer was tested. Incomplete primary support is likewise
`INDETERMINATE`, never a pass or evidence of source failure. Missing PZI at
any outside-RGI reporting center is incomplete because the missing value
could enter the mask; it is not imputed or treated as mask-false. A resolved
positive-reference bound exceedance is `FAIL`. Overall `PASS` requires all 36
pairs to pass. Any pair-level `FAIL` makes the overall result `FAIL`; only
when none fails does one or more unresolved pair make it `INDETERMINATE`.

Report strict aggregated-GLO-30 departure, signed native and aggregate ratios,
and `(E_native_n00-E_r90)/E_p00` as secondary paired diagnostics. There is no
registered margin for native versus aggregate, and native need not outperform
aggregation.

## Staged access and outputs

After selection, freeze and approve exact window-keyed GLO-30, GLO-90, PZI,
and RGI incidences; unique requests and authenticated reuse records; runtime
and import hashes; ordered schemas; and a pre-access manifest. No new request
or selected-window raster open may precede that approval. Acquisition may not
import Rasterio. It writes each response to a temporary path, closes and
hashes it, atomically renames it, retains status and headers, and publishes an
atomic ledger and raw manifest. Reuse is allowed only through an exact prior
manifest chain. Orphaned, unlisted, corrupt, reordered, or incomplete records
stop the action.

Approve the exact raw commit and manifest before Rasterio decodes a payload.
Then stage and replay grids, PZI, and RGI subsets; freeze coverage and support
before calculating the functional. The registered result contains 216 long
rows (18 cells by two masks by six variants), 36 pair decisions, two mask
summaries, and one overall status. Publish multiple outputs atomically and
never expose a partial summary. Handwritten new source plus tests may not
exceed 500 lines; add no class or scientific dependency.

After independent result review, retain an executed notebook with at most 50
code lines, a non-map numerical figure, updated manuscript source and PDF,
and a terminal manifest. All stages require three independent exact-commit
approvals recorded on Issue 31.

## Claim boundary

A pass would mean only that the registered functional met inherited numerical
bounds in these 18 source-complete, region-balanced cells. It cannot erase an
exposed development exceedance, authorize substitution in the stopped Issue
19 estimator, estimate global area, identify unstable slopes, validate
permafrost or glacier contact, or support susceptibility, incidence, hazard,
trigger, or climate-attribution claims.

## Registered sources

- NIST Randomness Beacon 2.0 and API:
  https://csrc.nist.gov/projects/interoperable-randomness-beacons/beacon-20
- NISTIR 8213 draft reference:
  https://doi.org/10.6028/NIST.IR.8213-draft
- Copernicus DEM Product Handbook, version 5.0:
  https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf
- Registry of Open Data on AWS, Copernicus DEM:
  https://registry.opendata.aws/copernicus-dem/

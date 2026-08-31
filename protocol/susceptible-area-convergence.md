# Held-out susceptible-area convergence test

Version 0.2. Version 0.1 was registered in GitHub issue
[#11](https://github.com/bradlipovsky/mass-movements/issues/11) on 30 August
2026, after the denominator pilot was frozen and before any held-out RGI,
Copernicus DEM, or permafrost-index value was read. Version 0.2 corrects the
RGI point-field description after inventory selection and before any DEM or
permafrost-index value was read; it does not change the calculation.

## Question and inferential boundary

The denominator pilot showed that changing the terrain grid from 30 to 90 m
changes connected-component counts by factors of about 1.3--3. This test asks
whether total mapped area under the same geometrical screens is less sensitive
to DEM resolution and grid phase in regions not used by the pilot.

A passing area measure could later support an incidence density per susceptible
square kilometre-year. It would not count independent slopes, estimate failure
probability, or define hazard. A failed stratum cannot be used for global
incidence scaling without a new physical representation and protocol.

No failure catalog, source-coordinate audit, event climate, reanalysis value,
deformation anomaly, damage report, or downstream consequence may enter
selection or analysis. Connected components may be carried as a diagnostic,
but they cannot select the preferred statistic or alter a pass/fail result.

## Held-out regions and windows

The eligible RGI 7.0 regions are 02, 03, 04, 06, 07, 08, 09, 10, 12, 14,
15, 16, 17, and 18. Regions 01, 11, and 13 formed the pilot. Regions 05 and 19
are excluded because this test concerns mountain terrain outside the Greenland
and Antarctic peripheral inventories.

For every eligible two-digit region code `RR`, encode the UTF-8 key

```text
susceptible-area-heldout-v1|RR
```

and calculate its SHA-256 digest. Choose the three regions with the
lexicographically smallest digests. Stable ties are resolved by increasing
region code. Freeze all 14 keys and digests before retrieving any selected
regional inventory.

Within each chosen region, reproduce the pilot's one-degree window rule using
only RGI 7.0. Normalize the archived `cenlon` field to `[-180, 180)`. A
candidate has integer west and south edges, contains at least 10 archived RGI
`cenlon`, `cenlat` points, and has at least 1 square kilometre of summed catalog
`area_km2` among those points. The RGI metadata describes this point as an
approximately central point within an outline, not a geometric centroid.
Encode the candidate key as

```text
rgi7.0|RR|south={south:+03d}|west={west:+04d}
```

and calculate the SHA-256 digest of the UTF-8 string formed by prepending
`susceptible-area-heldout-window-v1|`. Choose the candidate with the smallest
digest, resolving a digest tie by its candidate key. Preserve every eligible
key, digest, glacier count, and summed catalog area before reading DEM or
permafrost values. Stop if a selected region has no eligible window.

This deterministic holdout is not a random sample of global mountain terrain.
The three windows test transfer from the pilot but do not estimate a global
terrain distribution.

## Source products and geometry

Reuse the exact versions, access terms, nodata rules, citations, and manifest
fields frozen by the denominator pilot for:

1. RGI 7.0 glacier outlines;
2. Copernicus DEM GLO-30, 2021 release; and
3. the Gruber (2012) Global Permafrost Zonation Index.

No new product or software dependency is allowed. Record exact source URLs,
access times, lengths, available ETags, SHA-256 digests, coordinate reference
systems, transforms, nodata representations, epochs, citations, and licences.
Derived permafrost subsets retain the archived CC BY 3.0 dataset record and do
not imply byte identity between the source representations.

For each one-degree window, use the pilot's local WGS84 Lambert azimuthal
equal-area projection, densified boundary, 1 km processing buffer, and
pixel-center reporting rule. The geographic reporting polygon is identical
for every grid variant.

## Fixed terrain screens

Keep two ice-free rock-terrain strata separate:

1. **Glacier contact:** slope at least 30 degrees and outside-glacier edge
   distance at most 100 m.
2. **Permafrost zonation:** slope at least 30 degrees and PZI at least 0.1.

The first stratum is contact geometry, not a calculation of buttressing,
unloading, or damage. The second is a coarse climatological intersection, not
measured ground temperature or pixel-scale failure probability. Neither stratum
is a claim that a mapped pixel will fail.

Use the pilot's centered-difference slope, valid-neighbor requirement,
pixel-center glacier rasterization, outside-glacier edge-distance equation, and
nearest-neighbor PZI sampling without modification.

## Grid variants and area

Let the reference 30 m grid have lower-left projected anchor `(x0, y0)`, where
both coordinates are integer multiples of 30 m and the grid covers the buffered
domain in complete cells. Construct three further 30 m grids with lower-left
anchors shifted by `(15, 0)`, `(0, 15)`, and `(15, 15)` m. Extend every shifted
grid by complete cells to cover the same buffered domain.

Independently warp the native DEM and independently sample glacier and PZI
masks on each phase. Do not translate the reference arrays. Calculate the
aligned 90 m DEM from complete 3 by 3 blocks of the reference 30 m DEM, using
the pilot's aggregation and mask-sampling rules.

For spacing `r`, susceptible area is

\[
A = r^2 \sum_{i,j} I_{i,j},
\]

where `I` equals one only when the target-cell center lies in the unbuffered
reporting polygon, all required source values are valid, the cell is ice-free,
and the stratum screen is satisfied. Source nodata and an observed zero area
remain distinct.

The reference area `A0` is the unshifted 30 m result. For every variant `v`,
report

\[
R_v=A_v/A_0, \qquad D_v=|A_v-A_0|/A_0.
\]

Calculate the population coefficient of variation across the four 30 m phase
areas as their population standard deviation divided by their arithmetic mean.
If `A0=0` and every registered variant is zero, set all departures and the
phase coefficient of variation to zero and record `structural_zero=yes`. If
`A0=0` and any variant is positive, leave ratios undefined and the stratum
fails convergence for that window.

A stratum passes practical convergence only when, in every held-out window:

- the 90 m fractional departure is at most 0.20; and
- the four-phase 30 m coefficient of variation is at most 0.10.

These bounds are post-pilot design choices fixed before held-out values were
read. Each stratum receives its registered result without replacement or a
second threshold chosen from the held-out output.

## Registered sensitivities

Repeat area calculations at slope thresholds of 25 and 35 degrees. For glacier
contact, also repeat maximum edge distances of 0 and 300 m. For permafrost
terrain, also repeat PZI at least 0.5. These calculations show geometric
threshold sensitivity. They are not additional pass/fail opportunities.

## Outputs and expected artifact

Write a long area table with region, window, stratum, grid spacing, phase,
slope threshold, contact distance or PZI threshold, valid source area,
susceptible area, ratio, departure, and coverage fields. Freeze a separate
table containing the two stratum-level pass/fail decisions and the contribution
of each window.

The executed notebook and manuscript figure will show area ratio versus
resolution or phase for both strata and all three regions, together with
separate threshold-sensitivity curves. They contain no event marker or failure
label. Source bytes, tables, notebook, figure, and freeze manifest receive
SHA-256 digests.

## Checks, code budget, and stopping rules

Tests must verify the region and window selectors, stable tie handling, shifted
grid transforms, pixel-center reporting area, exact 3 by 3 aggregation, nodata
propagation, zero-area handling, area ratios, coefficient of variation, and the
fixed decision rule. A repository-level test must reject catalog, audit, event,
and reanalysis inputs in the analysis program and notebook.

Target about 200 handwritten analysis lines, 100 test lines, and 60 notebook
code lines, with a hard ceiling of 420 handwritten source, test, and notebook
code lines. Reuse the pilot functions. Stop and simplify if the implementation
becomes more complicated than the convergence question. Stop before product
retrieval if source versions or registered fields cannot be matched. After the
first held-out source value is read, preserve this version and record any
necessary correction in an amendment log before recomputing.

## Amendment log

- 30 August 2026: replace "glacier centroid" with the exact RGI 7.0 fields
  `cenlon` and `cenlat`. The product metadata defines them as an approximately
  central point within the glacier outline. This correction was made after the
  RGI-only window calculation and before any selected DEM or PZI value was
  read. It changes no field, eligibility condition, digest, or selected window.

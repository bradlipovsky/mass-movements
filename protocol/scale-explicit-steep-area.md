# Scale-explicit equivalent steep-area development

Version 0.1. Registered in GitHub issue
[#13](https://github.com/bradlipovsky/mass-movements/issues/13) on 30 August
2026 before calculating the new metric.

## Question and development boundary

The held-out test in issue #11 found four-phase population coefficients of
variation below 0.004, but 30-to-90 m departures of 26.7--37.4% in Arctic
Canada North and Svalbard. The resolution change simultaneously altered DEM
smoothing, slope support, mask sampling, contact discretization, reporting
centers, and cell area. The hard pixel-scale slope threshold therefore failed
as a numerical denominator.

This protocol asks how a nominal fixed-radius regression-plane support,
continuous steepness weight, and vector-distance glacier-outline proximity
mask change that scale dependence. It uses the already exposed regions 03, 07,
and 08. The support radius, ramp, and composite representation were selected
after the issue #11 output was known: this is explicitly post-outcome method
development, not an uninformed or external validation. It cannot establish a
global terrain distribution, incidence, failure probability, or hazard. Any
blind transfer requires a new issue that freezes this method before new region
values are read.

No failure catalog, source-coordinate audit, event time, reanalysis value,
climate variable, deformation signal, damage report, or consequence may enter
this calculation.

## Frozen inputs

Reuse without modification the issue #11:

1. selected windows and densified reporting polygons;
2. four independently warped 30 m Copernicus DEM phase grids and the aligned
   strict 3 by 3 mean used for 90 m;
3. projected RGI glacier geometries;
4. nearest-neighbor PZI samples;
5. local WGS84 Lambert azimuthal equal-area projections, 1 km processing
   buffer, and pixel-center reporting rule; and
6. product identities, access terms, nodata rules, source hashes, and coverage
   records.

Retrieve no new scientific product. Source epochs and physical limitations
remain those frozen by issue #11.

## Fixed-support local-plane gradient

Let target spacing be `r`. Around every target-cell center, form the symmetric
disk of cell-center offsets

```text
S_r = {(u, v): u = i r, v = j r, u^2 + v^2 <= (300 m)^2}.
```

Require a finite elevation at every offset in `S_r`. With elevations `z`, fit
the plane gradient by

```text
a = sum(u z) / sum(u^2)
b = sum(v z) / sum(v^2)
beta = atan(sqrt(a^2 + b^2)).
```

The disk symmetry gives zero sums of `u`, `v`, and `u v`, so these equations
are the ordinary-least-squares plane coefficients with an unconstrained
intercept. The nominal radius is 300 m on both grids, but the 30 and 90 m
stencils contain different resolution-dependent cell-center samples and
quadrature; the 90 m axis samples reach only 270 m. The result is the
inclination of a vertical-residual regression plane over the included centers.
It is not a mean facet slope, failure-plane orientation, rock-mass thickness,
stress measure, or resolution-independent physical kernel. The radius was
selected during this post-outcome development after the issue #11 resolution
failure was known.

Cells lacking complete support receive nodata. The registered 1 km processing
halo is retained, so reporting-boundary cells can have complete support.

## Continuous steepness weight

Use the 25, 30, and 35 degree bracket already fixed for the issue #11
hard-threshold sensitivity. Define `q = tan(beta)`, `q25 = tan(25 degrees)`, and
`q35 = tan(35 degrees)`, then

```text
w(beta) = 0                         if beta <= 25 degrees
w(beta) = (q - q25) / (q35 - q25) if 25 < beta < 35 degrees
w(beta) = 1                         if beta >= 35 degrees.
```

The interpolation is linear in surface gradient. This mapping is an arbitrary
but frozen numerical regularization, not a constitutive or stability relation.
The former 30 degree threshold has no operative role, and the ramp does not
preserve the hard-threshold susceptible-area estimand. The bounded weight is
not a probability.

## Fixed masks

Validate every projected glacier geometry and their union; stop without
repairing a geometry if either is invalid. Let `G` be the valid union of
projected inventory glacier polygons. The glacier-outline-proximity band is

```text
C = {p outside G: distance(p, G) <= 100 m}.
```

A target center `(x, y)` belongs to the proximity mask exactly when
`dwithin(G, point(x, y), 100 m)` is true and `intersects_xy(G, x, y)` is false.
The exact distance predicate includes the closed outer 100 m boundary and the
intersection predicate excludes glacier interiors and boundaries, without a
directional rasterization tie rule or a polygonal approximation of the rounded
offset. It is center-sampled planar distance to an inventory outline and
remains coarsely sampled on a 90 m lattice. It is defensible as outline
proximity, not physical contact, buttressing, unloading, damage, or a
glacier-history calculation.

The permafrost mask contains target centers outside `G` with a finite PZI at
least 0.1. It remains a coarse climatological intersection, not ground
temperature or local failure probability.

## Equivalent steep area

For stratum mask `I`, spacing `r`, reporting-center mask `R`, and finite
fixed-support slope, calculate

```text
E = r^2 sum(R I w(beta)).
```

`E` has square-metre units but is equivalent steep area, not literal
susceptible area. The unshifted 30 m result `E0` is the reference. For every
variant `v`, report

```text
ratio_v = E_v / E0
departure_v = abs(E_v - E0) / E0.
```

Calculate the population coefficient of variation across the four 30 m phase
values. If `E0=0` and every variant is zero, set departures and phase CV to
zero and record `structural_zero=yes`. If `E0=0` and any variant is positive,
leave ratios and departures undefined. Calculate phase CV only when the four
phase values have a positive mean; if their mean is zero while another variant
is positive, leave phase CV undefined.

The former issue #11 bounds, 0.20 for 90 m departure and 0.10 for phase CV,
may appear as common reference lines only. They do not create a confirmatory
pass/fail result in these exposed windows.

The support, ramp, and proximity calculation change together. Any departure
difference relative to issue #11 describes this one composite representation;
it cannot be attributed to a component or physical mechanism. No component
ablation is registered.

## Outputs

Write one long table containing region, window, stratum, variant, spacing,
phase, support radius, ramp bounds, mask definition, reporting count, complete
slope-support count, mask count, equivalent steep area, ratio, departure, and
structural-zero fields. Write a paired comparison with the frozen issue #11
hard-threshold primary departures.

The executed notebook and manuscript figure will show equivalent-area ratios
and paired 90 m departures for all three regions and both strata. The notebook,
caption, manuscript, and pull request must identify the calculation as
known-window method development. They contain no event marker or failure
label.

## Checks, code budget, and stopping rules

Tests must verify:

1. exact local-plane recovery for translated planar DEMs at 30 and 90 m;
2. strict nodata support and disk construction;
3. weight values below 25 degrees, at both endpoints, within the ramp, and
   above 35 degrees;
4. center-sampled vector-distance proximity at 99, 100, and 101 m;
5. constant-weight area integration and phase transforms;
6. zero-reference handling; and
7. rejection of catalog, candidate, audit, event, climate, and reanalysis input
   paths in the analysis program and notebook.

Target about 160 handwritten analysis lines, 100 test lines, and 50 notebook
code lines. The hard ceiling is 400 handwritten source, test, and notebook code
lines. Reuse issue #11 geometry and comparison functions and add no dependency.
Stop and simplify if the implementation becomes longer than the physical
definition.

Before reading the first equivalent-area output, pass the synthetic tests and
commit a pre-output manifest containing the protocol, analysis-program, and
test hashes; inherited input-manifest hash; software versions; and handwritten
line count. Execute the real-window calculation only from that committed state.

Do not change the 300 m radius, ramp endpoints, vector contact distance, PZI
threshold, masks, or output calculation after the first equivalent-area value
is read. If an implementation correction becomes necessary, preserve this
version, document an amendment, and state whether any output had already been
inspected. Report an unfavorable or numerically unstable result without
replacement.

## Amendment log

- 30 August 2026, before any equivalent-area value was calculated: replace the
  inherited center-rasterization boundary rule for the vector contact band with
  the then-registered closed buffer-boundary center predicate. A synthetic
  boundary check showed that the rasterization tie rule can differ by edge
  direction. The 100 m distance, outside-glacier condition, and every other
  registered choice were unchanged; the later amendment below supersedes the
  polygonal-buffer implementation.
- 30 August 2026, before any equivalent-area value was calculated: clarify
  after mechanics review that the two resolutions use different center
  quadrature within a nominal radius; the regression inclination is not a mean
  facet slope or stress measure; the ramp is an arbitrary numerical mapping
  with no operative 30 degree threshold; inventory-outline proximity is not
  mechanical contact; and all three changes form one post-outcome composite.
  These clarifications change no calculation.
- 30 August 2026, before any equivalent-area value was calculated: an
  independent implementation audit found that GEOS's default rounded buffer is
  a polygonal approximation and can exclude a center at exactly 100 m from an
  oblique convex vertex. Replace the buffer predicate with exact `dwithin` and
  retain `intersects_xy` to exclude the glacier and its boundary. The same audit
  found that an all-zero four-phase mean paired with a positive 90 m value had
  been assigned a phase CV of zero; register that CV as undefined instead. No
  radius, distance, ramp, stratum, input, or favorable result motivated either
  correction.

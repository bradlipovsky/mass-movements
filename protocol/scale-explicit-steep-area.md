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

This protocol asks whether a fixed physical slope support, continuous
steepness weight, and vector-defined contact band reduce that scale dependence.
It uses the already exposed regions 03, 07, and 08. The calculation is method
development, not external validation. It cannot establish a global terrain
distribution, incidence, failure probability, or hazard. Any blind transfer
requires a new issue that freezes this method before new region values are
read.

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
intercept. The radius is 300 m on both the 30 and 90 m grids. This defines a
600 m-diameter mean topographic gradient; it is not a mapped failure plane,
rock-mass thickness, or smoothing scale inferred from the known results.

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

The interpolation is linear in surface gradient. The bounded weight is a
numerical terrain-exposure weight, not a probability or a stability model.

## Fixed masks

Validate every projected glacier geometry and their union; stop without
repairing a geometry if either is invalid. Let `G` be the valid union of
projected glacier polygons. The glacier-contact band is

```text
C = buffer(G, 100 m) minus G.
```

A target center `(x, y)` belongs to the contact mask exactly when
`intersects_xy(buffer(G, 100 m), x, y)` is true and `intersects_xy(G, x, y)` is
false. This topological predicate includes the closed outer 100 m boundary and
excludes glacier interiors and boundaries without relying on a directional
rasterization tie rule. It replaces raster cell-count distance with a fixed
projected distance. The band remains contact geometry, not buttressing,
unloading, damage, or a glacier-history calculation.

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
leave ratios undefined.

The former issue #11 bounds, 0.20 for 90 m departure and 0.10 for phase CV,
may appear as common reference lines only. They do not create a confirmatory
pass/fail result in these exposed windows.

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
4. vector contact inclusion and exclusion at fixed physical distances;
5. constant-weight area integration and phase transforms;
6. zero-reference handling; and
7. rejection of catalog, candidate, audit, event, climate, and reanalysis input
   paths in the analysis program and notebook.

Target about 160 handwritten analysis lines, 100 test lines, and 50 notebook
code lines. The hard ceiling is 400 handwritten source, test, and notebook code
lines. Reuse issue #11 geometry and comparison functions and add no dependency.
Stop and simplify if the implementation becomes longer than the physical
definition.

Do not change the 300 m radius, ramp endpoints, vector contact distance, PZI
threshold, masks, or output calculation after the first equivalent-area value
is read. If an implementation correction becomes necessary, preserve this
version, document an amendment, and state whether any output had already been
inspected. Report an unfavorable or numerically unstable result without
replacement.

## Amendment log

- 30 August 2026, before any equivalent-area value was calculated: replace the
  inherited center-rasterization boundary rule for the vector contact band with
  the exact closed `intersects_xy` center predicate above. A synthetic boundary
  check showed that the rasterization tie rule can differ by edge direction.
  The 100 m distance, outside-glacier condition, and every other registered
  choice are unchanged.

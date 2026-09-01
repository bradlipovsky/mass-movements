# Glacier-proximity relevance of absent DEM objects

## Question and claim boundary

This protocol asks whether a nominal Copernicus DEM delivery unit absent from
the 1 September 2026 object inventory is disjoint from a conservative
geometric screen around the registered glacier-outline-proximity continuum.
Disjointness places the absent delivery unit outside that conservative screen;
intersection remains unresolved. Neither state proves whether a grid center
has finite elevation support.

This is not a DEM-completeness or terrain calculation. It does not open an
object or raster, inspect elevation or nodata, calculate a slope or equivalent
area, evaluate PZI, substitute GLO-90, change the probability sample, revise
the Issue 19 stop, or estimate susceptibility, hazard, or climate attribution.
GLO-90 is a separate inventory; it is not the Issue 19 `r90`, which was a
strict aggregation of the GLO-30 p00 grid.

## Frozen population and geometry

Use all 1,826 cells in the exact Issue 17 frame and all full RGI 7 outlines
from the 19 retained, hash-verified archives. Dominant RGI region is a grouping
field only and never filters geometry. Retain the exact Issue 23 nine-object
candidate identities for each cell, but remove the duplicated product code
during the geometry stage. No object inventory or selected-sample identity may
be read before the geometry screen is sealed.

For cell \(i\), densify the WGS84 reporting-cell edges at 0.01 degree and
project them to the registered local Lambert azimuthal equal-area coordinate
system. Load every complete RGI outline intersecting the inverse-projected
1,100 m reporting-cell envelope. Repair a geometry made invalid by projection
only with Shapely linework `make_valid`, require polygonal valid output and
projected relative area change no greater than \(10^{-8}\), and retain a
source-outline-identified repair ledger. Invalid source-WGS84 geometry stops.

Let \(R_i\) be the reporting polygon and \(G_i\) the union of these projected
outlines. The registered glacier-proximity continuum is outside \(G_i\),
inside \(R_i\), and at closed distance no greater than 100 m from \(G_i\).
Approximate it conservatively with an outward 101 m buffer. Buffer that region
outward by 1,001 m, using exactly 32 segments per quadrant for both buffers.
The minimum radial reach of the latter polygon is
\(1001\cos(\pi/128)=1000.699\) m, so it contains the exact 1,000 m continuum.
This deliberately broad screen contains the registered 300 m plane-support
disk, phase shifts, and aligned aggregation footprint. It does not model the
bilinear source interpolation kernel and therefore does not establish exact
source dependence or computability.

Densify every nominal one-degree delivery-unit edge at 0.01 degree, project it
to the same local coordinates, and use closed intersection with the dependency
envelope. All screened identities must remain within the frozen three-by-three
candidate set. A cell with an empty continuous proximity region is
`not_applicable`, not vacuously supported.

## Staged execution

Before geometry execution, commit the protocol, code, tests, frozen input
hashes, software versions, output schemas, and a pre-geometry manifest. The
geometry action may read the frame, Issue 23 expected identities, RGI source
manifest, and 19 local archives only. It writes a 16,434-row spatial
`object_screen.csv`, a projection-repair ledger, and a geometry manifest.

After independent review of that sealed screen, the join action verifies the
Issue 23 final-manifest hash and its bound inventory hash. It expands the
spatial screen to 32,868 product incidences and labels each row:

- `listed` when the exact product object is in the inventory;
- `absent_outside_conservative_screen` when absent and disjoint from the
  conservative screen; or
- `absent_relevance_unresolved` when absent and intersecting it.

Aggregate 3,652 cell-instance rows and exact counts by dominant region and
10-degree latitude band. These are finite-population enumerations without a
sampling standard error. No summary uses the 96 selected identities.

## Review and outputs

Handwritten analysis plus tests may not exceed 300 lines. Tests cover frozen
identities, conservative buffers, interior exclusion, delivery-unit boundary
contact, antimeridian projection, state conservation, product-independent
geometry, inventory-join separation, and forbidden raster/PZI/sample access.
After staged and final independent approval, retain a final manifest, an
executed notebook with at most 40 code lines, a non-map figure, and updated
manuscript source and PDF.

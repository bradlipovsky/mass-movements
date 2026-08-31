# Susceptible-terrain denominator pilot

Version 0.2. Version 0.1 was registered on 30 August 2026 before any RGI,
Copernicus DEM, permafrost-index, or ITS_LIVE product value was read. The
access amendment below was registered after Earthdata authentication failed
and before any product value was read. GitHub issue
[#9](https://github.com/bradlipovsky/mass-movements/issues/9) is the public
registration record.

## Question and inferential boundary

This pilot asks whether source-like alpine terrain can be enumerated without
using known failures, event climate, or downstream consequences. The resulting
objects are candidate denominator units for a later incidence calculation.
They are not predicted failures, and this pilot does not estimate failure
probability.

Three partly overlapping strata represent distinct geometrical conditions:

1. glacier polygons large enough to supply a prescribed conditional volume;
2. steep, ice-free terrain in contact with a glacier outline; and
3. steep, ice-free terrain intersecting a coarse permafrost zonation index.

The second stratum measures glacier contact, not loss of buttressing. Inferring
support or stress change would require glacier-history and boundary-stress
calculations that are outside this pilot. The third stratum is an intersection
with a climatological index, not a local ground-temperature measurement or a
failure-probability map. Because the strata can overlap, their counts and areas
must not be added to form a single denominator.

No failure catalog, source-time audit, reanalysis output, event name, or
event-centered coordinate may be loaded by the selection or analysis code.
Case overlays require a later protocol amendment made only after the baseline
tables and checksums are frozen.

## Blind validation regions and windows

Use RGI 7.0 regions 01 (Alaska), 11 (Central Europe), and 13 (Central Asia).
They provide three separated mountain settings and all have corresponding
ITS_LIVE regional products. This small validation sample does not estimate a
regional or global terrain distribution.

Choose one 1 degree by 1 degree WGS84 analysis window per RGI region using only
the RGI 7.0 inventory. Normalize longitude to `[-180, 180)`. A candidate cell
has integer west and south edges, contains at least 10 RGI glacier centroids,
and has at least 1 square kilometre of summed catalog `area_km2` among those
centroids. Encode its key as
`rgi7.0|RR|south={south:+03d}|west={west:+04d}`, where `RR` is the two-digit
region. Choose the candidate whose UTF-8 key has the lexicographically smallest
SHA-256 digest. Record all eligible keys and digests. If any field name differs
from the RGI guide or a region has no eligible cell, stop before reading a DEM.

Retrieve enough surrounding data to construct a 1 km processing buffer, but
report only pixels whose centers lie inside the unbuffered analysis window.
The buffer limits edge effects; it is not extra sampled area. Objects that
touch the analysis boundary are retained with `edge_truncated=yes` and reported
separately from objects wholly contained in a window. Window-level results
must not be extrapolated to the full RGI regions.

## Registered source products

Record the exact URL or object key, access time in UTC, content length, source
ETag when available, and SHA-256 of every downloaded object and generated
table. Record each product's CRS, grid transform, nodata representation,
acquisition or climatology interval, citation, and license or access terms.
Source epochs remain separate metadata; they do not constitute a simultaneous
Earth snapshot.

- **Glacier outlines:** Randolph Glacier Inventory 7.0, NSIDC-0770,
  DOI `10.5067/F6JMOVY5NAVZ`. Use the glacier product in WGS84. The inventory
  targets a nominal epoch near 2000, with outline dates retained per object.
  Version 0.2 permits the identically named regional archives in the
  `rgi70_official` directory on the RGI production team's Bremen server, which
  is linked from the GLIMS-RGI generation repository. Record this as an access
  copy, not as proven byte identity with the inaccessible NSIDC object. Require
  the registered 7.0 names and internal metadata and record a local SHA-256.
- **Surface elevation:** Copernicus DEM GLO-30, 2021 release, from the public
  `copernicus-dem-30m` AWS registry. Use the native 1 arc-second COG values,
  not web-map overviews. This is a digital surface model; its gradient is not
  assumed to be a measured bedrock-plane slope.
- **Permafrost index:** Gruber (2012) Global Permafrost Zonation Index, 30
  arc-second WGS84 grid, numeric WCS coverage
  `cryogis__Permafrost-Global-PFI`. Use GeoTIFF coverage subsets. The source
  documentation defines modeled PZI values from 0.1 to 1.0, an uncertainty
  fringe of 0.01, and background 0.
- **Velocity observability:** ITS_LIVE regional glacier and ice-sheet surface
  velocities, NSIDC-0776 version 2, DOI `10.5067/JQ6337239C96`. Read only the
  `count` variable in the 2014--2022 climatological file. It is the number of
  image pairs entering the climatological mean. Do not read velocity,
  acceleration, trend, or seasonal-amplitude variables.

ITS_LIVE coverage never changes window or object membership. For each glacier
polygon, report the fraction of overlapping 120 m pixels with `count > 0` and
the median positive count. Report `not_covered` if the selected window lies
outside a version-2 regional product. These fields describe observability only.

If Earthdata authentication for RGI or ITS_LIVE is unavailable, stop that
source retrieval and record `authentication_unavailable`; do not substitute a
mirror or an earlier product version without an amendment. Copernicus tiles
absent from the public GLO-30 bucket and failed numeric PZI WCS subsets are
likewise explicit coverage failures, not zeros.

## Equal-area grids and source masks

For each selected window, define a local Lambert azimuthal equal-area CRS with
WGS84 datum and latitude and longitude of origin at the window center:

```text
+proj=laea +lat_0=<center_lat> +lon_0=<center_lon> +datum=WGS84 +units=m +no_defs
```

Store its canonical WKT and SHA-256. Densify each geographic window edge at
0.01 degree spacing before projection. Buffer the projected polygon by 1000 m.
Anchor a square 30 m grid at integer multiples of 30 m using the floor of the
working-domain minimum x and y. Extend it by whole cells to cover the buffered
domain. A pixel belongs to the reported window only when its center is inside
the unbuffered projected polygon.

Warp GLO-30 elevations once to this grid with bilinear interpolation. A target
cell is valid only when all contributing source support is valid. Rasterize
RGI outlines by pixel-center inclusion (`all_touched=false`). Reproject PZI and
ITS_LIVE `count` using nearest-neighbor sampling; preserve nodata separately
from numeric zero. Product-coverage fractions and nodata fractions are retained
for every window and object table.

Create the 90 m sensitivity DEM from non-overlapping 3 by 3 blocks of the
warped 30 m grid, aligned at its lower-left grid origin. A block is valid only
when all nine elevations are valid. Its value is their arithmetic mean. Masks
are newly sampled or rasterized on the aligned 90 m grid; they are not
majority-voted from the 30 m result.

For grid spacing `r`, calculate interior slope using centered differences,

\[
s=\tan^{-1}\left[\left\{\left(\frac{z_{i,j+1}-z_{i,j-1}}{2r}\right)^2+
\left(\frac{z_{i-1,j}-z_{i+1,j}}{2r}\right)^2\right\}^{1/2}\right].
\]

Report `s` in degrees. A slope is invalid if the center or any of the four
required neighbors is nodata. Primary calculations use 30 m slopes; repeat the
rock-slope strata on the aggregated 90 m grid as a resolution sensitivity.

## Object definitions

Glacier objects retain the RGI `rgi_id`. Clip their vector geometry to the
analysis window in the local equal-area CRS and calculate sampled area there.
Do not apply a surface-slope threshold to this stratum. Record the catalog area,
clipped area, outline date, window truncation, DEM coverage, and ITS_LIVE
coverage separately.

Rock-slope objects are four-neighbor connected components. Diagonal contact
does not join two components. Exclude glacier pixels before labeling. Retain
every component, including those below the conditional-volume cutoff, so that
later checks can reconstruct counts.

For glacier-contact terrain, compute outside-glacier edge distance from the
raster mask as
`max(0, (euclidean_distance_to_glacier_center - 0.5) * r)`. Thus an
edge-sharing outside cell has zero contact distance. Calculate all combinations
of slope threshold 25, 30, and 35 degrees and maximum contact distance 0, 100,
and 300 m. The registered primary combination is 30 degrees and 100 m.

For permafrost terrain, the primary mask is PZI greater than or equal to 0.1;
PZI greater than or equal to 0.5 is a sensitivity. PZI equal to 0.01 is the
uncertainty fringe and is reported as coverage but excluded from both masks.
Calculate both PZI masks at slope thresholds 25, 30, and 35 degrees. The
registered primary combination is PZI at least 0.1 and slope at least 30
degrees. Never describe PZI as a measured probability at a pixel.

For every object with sampled area `A`, calculate the conditional mobilized
volume

\[
V_d=A d
\]

for prescribed depths `d = 10, 30, 100 m`. An object is volume-eligible for a
depth scenario when `V_d >= 10^6 m^3`. These are geometric scenarios, not
estimates of glacier thickness, rock-slope failure depth, or mobilized volume.

## Outputs and comparisons

Write long object and summary tables. Object rows identify region, window,
stratum, source-product epoch fields, resolution, slope threshold, contact or
PZI threshold, component or RGI ID, area, boundary truncation, coverage flags,
and conditional-volume eligibility at all three depths. Summary rows report
object count and sampled area by every registered grouping, both including and
excluding boundary-truncated objects. Zero and missing coverage are distinct.

The executed notebook will contain:

1. a three-window map showing only DEM hillshade, glacier outlines, primary
   glacier-contact components, primary permafrost components, and nodata; and
2. object counts and sampled areas across depth, threshold, and 30 versus 90 m
   resolution, faceted by the three RGI regions.

Maps and figures contain no failure markers or event labels. Comparisons are
descriptive; no hypothesis test or incidence ratio is registered for this
pilot.

## Checks fixed before source retrieval

Synthetic and mechanical tests must verify:

- the SHA-256 window selector, coordinate normalization, and stable tie order;
- local-projection round trips and the 30 m grid anchor;
- constant and planar DEM slopes, including nodata propagation;
- exact 3 by 3 aggregation and 30 versus 90 m alignment;
- glacier pixel-center rasterization, contact distance, and four-neighbor
  component labeling;
- PZI fringe, primary, sensitivity, background, and nodata separation;
- `V=A d`, the inclusive volume cutoff, and boundary-truncation summaries;
- exact product versions, manifest hashes, and table uniqueness; and
- absence of catalog, audit, event, and reanalysis inputs from the analysis
  program and notebook.

Select a deterministic validation sample of five objects per stratum and
window from the primary 30 m result by increasing SHA-256 of
`region|stratum|object_id`. Inspect their source masks, connected geometry,
area, and coverage fields without consulting a failure catalog. Record every
disagreement; do not replace sampled objects.

## Dependencies, code budget, and stopping rules

Raster reprojection, vector clipping, and equal-area distances require
`rasterio`, `pyproj`, and `shapely`; pin these packages in the project analysis
requirements. This scientific need is the only registered reason for adding
them. Continue using NumPy and SciPy for arrays, distances, and connected
components.

Target approximately 280 lines of analysis code, 100 lines of tests, and 80
notebook code lines, no more than 480 handwritten lines total. Stop and
simplify before crossing that limit. Stop and amend before product-value
retrieval if the registered WCS does not return numeric PZI, GLO-30 cannot cover
all three windows, RGI fields cannot implement the blind selector, or a chosen
window was influenced by failure knowledge. After the first source value is
read, preserve this version and log any necessary change below before
recomputing.

## Amendment log

- 30 August 2026: the local Earthdata netrc and cookie flows both returned an
  OAuth 401 before any RGI record was read. Permit the RGI production team's
  version-matched `rgi70_official` access copy for regions 01, 11, and 13.
  Preserve the NSIDC-0770 version and citation, record the access-copy URLs and
  hashes, and stop on any filename or internal-metadata mismatch. This changes
  the access route only; the selection rule and all endpoints are unchanged.

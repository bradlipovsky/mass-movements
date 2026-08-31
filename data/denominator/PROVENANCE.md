# Denominator source staging record

This directory freezes the analysis-ready inputs used by protocol v0.4. The
analysis itself is reproduced by `make denominator`; source staging was a
one-time, climate- and case-blind operation. `source_manifest.json` is the
machine-readable authority for remote URLs, response metadata, local hashes,
and parent IDs. The recipes below explain each transformation without claiming
that every remote service will remain available.

## Blind RGI selection and clipping

The three regional version-7.0 glacier archives were downloaded and checked
against the hashes in the manifest. Their `*-attributes.csv` tables were read
with Python's standard CSV parser. Longitude was normalized to `[-180,180)`;
centroids were grouped by `floor(latitude), floor(longitude)`; counts and
`math.fsum(area_km2)` were calculated; cells failing either registered
eligibility condition were removed; and every remaining key and SHA-256 is in
`eligible_windows.csv`. Its minimum digest per region reproduces `windows.csv`.
The matching glacier shapefile was clipped to the selected window plus the
registered 1 km projected processing halo and written as GeoJSON without
simplifying feature geometry.

## Equal-area elevation grids

Each window edge was densified at 0.01 degree, projected to the registered
local LAEA CRS, buffered by 1 km, and covered by a 30 m grid whose x/y anchors
are integer multiples of 30 m and whose dimensions are divisible by three.
The exact CRS WKT, affine transform, height, and width are in `windows.csv` and
the GeoTIFF headers. The nine named GLO-30 COGs per region in the manifest were
read at native resolution and bilinearly reprojected to that grid with nodata
propagation. No web-map overview was used.

## PZI raw byte ranges

The source header fixes 43,200 little-endian Float32 columns, 18,000 rows,
30-arc-second cells, lower-left `(-180,-60)`, and nodata `-9999`. Source row
zero therefore begins at 90 degrees north. For every subset cell `(row,col)`,
the byte offset is `4 * (row * 43200 + col)`. Contiguous row ranges were read
from the official `PZI.flt` URL and written without value resampling; subset
bounds, dimensions, and values are preserved by the TIFF headers. The earlier
WCS responses and their sidecars are retained only as rejected inputs because
that service mapped documented background zero to nodata.

Edinburgh DataShare DOI `10.7488/ds/1877` archives the same Global Permafrost
PZI dataset, identifies Gruber as creator and UZH as publisher, links the UZH
source page and 2012 derivation paper, and assigns the data CC BY 3.0. Its
official API rights fields are preserved in `source/pzi_rights_metadata.json`.
The DataShare copy uses an ESRI File Geodatabase, so no byte identity with the
UZH raw Float32 representation is claimed. The committed window subsets are
treated as attributed adaptations of the licensed PZI data.

## ITS_LIVE observability

Only the `count` subdataset was window-read from each named version-2 static
NetCDF mosaic and written on its native 120 m grid. The accompanying source
JSON bytes are retained. No velocity, trend, acceleration, or seasonal field
was opened by the analysis. Glacier summaries use every native pixel touched
by the clipped polygon; zero means no contributing pair and remains distinct
from spatial noncoverage.

## Timing limitation

The first archived source completed at 2026-08-31T04:17:28Z and the manifest
was completed at 2026-08-31T04:35:56.731389Z. Individual HTTP request times
were not logged. This deviation is stated rather than back-filling invented
timestamps; URLs, HTTP validators, sizes, downloaded archive hashes, and all
analysis-ready local hashes remain recorded.

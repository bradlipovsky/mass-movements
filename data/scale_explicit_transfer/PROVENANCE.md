# Blind-transfer source provenance

This directory freezes the inputs for protocol version 0.1. Selection commit
`ad64acdc80611d443bfa46c941de1ff241d9b5c3` and its independent audit preceded
all access to the selected-window elevation, PZI, and outline geometries. The
initial selection manifest's estimator-hash typo was corrected publicly before
this access; the selected rows did not change.

`source/source_manifest.json` records every URL, retrieval response, byte size,
SHA-256 digest, derivation, access term, runtime version, and local artifact.
Ignored raw objects remain locally replayable but are identified by hash rather
than committed. All derived analysis inputs, response headers, replay records,
and coverage records are committed.

## RGI outlines

NASA CMR identifies NSIDC-0770 Version 7, DOI
`10.5067/F6JMOVY5NAVZ`, and the authoritative NSIDC distribution. Exact archive
bytes came from the same version-labelled RGI consortium-author mirror used in
the preceding pilots because NSIDC object retrieval requires Earthdata Login.
The filenames, schemas, metadata, and regional counts agree, but byte identity
with the authentication-protected NSIDC objects was not established.

After the inventory-only windows were frozen, each selected regional archive
was spatially filtered to the reporting cell expanded by 0.2 degrees. Full
geometries of intersecting features were retained; no outline was clipped or
simplified. This margin exceeds the registered 1 km processing halo. RGI 7 is
licensed CC BY 4.0 with due citation.

## Copernicus elevation grids

The deterministic 3 by 3 native-tile set surrounding every selected cell was
requested from the public GLO-30 COG endpoint. Thirty-five COGs were downloaded
in full. `dem_18_S45_E172` returned HTTP 404 and remains an explicit unavailable
ocean tile; it was not represented as zero elevation.

Four equal-area 30 m grids per region use lower-left phase offsets `(0,0)`,
`(15,0)`, `(0,15)`, and `(15,15)` m. The densified reporting cell was projected
to its local WGS84 Lambert azimuthal equal-area CRS and buffered by 1 km. The
unshifted dimensions were extended to multiples of three. Native COGs were
bilinearly warped in increasing integer latitude and numeric longitude order;
only finite values replaced an earlier tile in an overlap.

Every stored Float32 phase grid was reconstructed again from the retained full
COGs. Registered transforms and little-endian C-order value hashes matched,
cell for cell; all maximum absolute differences are zero. The replay criterion
is the grid metadata and raw Float32 array, not GeoTIFF container serialization.

The adapted grids were produced using Copernicus WorldDEM-30 © DLR e.V.
2010--2014 and © Airbus Defence and Space GmbH 2014--2018, provided under
COPERNICUS by the European Union and ESA; all rights reserved. The organisations
in charge of the Copernicus programme by law or delegation incur no liability
for use of Copernicus WorldDEM-30.

## Permafrost zonation

The UZH header defines 43,200 little-endian Float32 columns, 18,000 rows,
30-arc-second cells, lower-left `(-180,-60)`, and nodata `-9999`. One exact HTTP
byte range of 144 complete global rows was retained for each region, then the
144 registered columns from `west-0.1` through `west+1.1` were copied without
value resampling. Each stored TIFF was reconstructed from its range object with
identical transform and value hash; all maximum differences are zero.

Edinburgh DataShare DOI `10.7488/ds/1877` identifies the Global Permafrost PZI
dataset and assigns CC BY 3.0. Attribution is to WGMS as source, Gruber as
creator, and the University of Zurich as publisher. The Edinburgh archive is a
File Geodatabase, so byte identity with the UZH Float32 distribution is not
claimed.

## Coverage and epoch limits

`source_coverage.csv` contains 20 region-variant rows. DEM, PZI, and the binary
glacier predicate cover every reporting center except for fewer than one part
per million of some New Zealand grids next to the explicit ocean-tile gap. The
outside-glacier finite-PZI coverage ranges from about 95.1% in Arctic Canada
South to 99.8% in North Asia; these are coverage diagnostics, not steep-area
or susceptibility results.

The products are not contemporaneous: RGI is an approximately year-2000
inventory, Copernicus source acquisitions span 2011--2015, and PZI uses
1961--1990 air-temperature inputs. Glacier proximity does not establish loss of
mechanical support. PZI intersection does not measure local ground temperature,
failure probability, or hazard.

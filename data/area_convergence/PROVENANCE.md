# Held-out area source staging record

This directory freezes the case- and climate-blind inputs used by protocol
version 0.2. `source_manifest.json` records the exact remote objects, HTTP
response dates and validators, downloaded-object hashes, derivations, local
hashes, licences, and unavailable coverage. Source staging was completed only
after the region and window tables were committed.

## RGI selection and outlines

The official RGI 7.0 regional archives for regions 03, 07, and 08 were
downloaded from the same version-matched release directory as the pilot. Their
attribute tables were grouped by integer cells using the archived `cenlat` and
longitude-normalized `cenlon` fields. These fields locate an approximately
central point inside each outline; they are not geometric centroids. Counts,
`math.fsum` catalog areas, prefixed SHA-256 keys, and stable ranks produced the
200 rows in `eligible_windows.csv`.

The selected shapefiles were spatially filtered to a geographic box extending
0.2 degrees beyond each analysis window. This margin exceeds the registered 1
km projected processing halo in all three windows. Full geometries of features
intersecting the filter were retained in GeoJSON; outlines were not simplified
or clipped at the filter boundary. The exact archive metadata member is stored
beside each GeoJSON.

## Copernicus elevation phases

Every available GLO-30 COG intersecting each window plus margin was downloaded
in full. The manifest records each source URL, response date, Last-Modified,
ETag, size, and SHA-256. S3 returned HTTP 404 for two ocean tiles south of the
Svalbard window; these remain explicit unavailable coverage rather than zero
elevation.

The local equal-area reporting boundary was densified as in the pilot and
buffered by 1 km. Four 30 m grids used lower-left phase offsets `(0,0)`,
`(15,0)`, `(0,15)`, and `(15,15)` m. The reference dimensions were extended to
multiples of three. Each phase was bilinearly warped directly from the native
COGs. Source tiles were applied by increasing integer latitude and then
increasing numeric longitude; a later finite source value replaced an earlier
value only in a tile overlap. This order matters for a few shared-edge pixels
west of Greenwich and is therefore fixed explicitly.

The 12 grids first produced from remote COG range reads were replayed from the
fully downloaded source objects. Every replayed GeoTIFF was byte-identical.
Thus the committed grids are reproducible from the exact source-object hashes,
without treating an intermediate web overview or resampled geographic mosaic
as native data.

The elevation products were produced using Copernicus WorldDEM-30
© DLR e.V. 2010--2014 and © Airbus Defence and Space GmbH 2014--2018,
provided under COPERNICUS by the European Union and ESA; all rights reserved.
The organisations in charge of the Copernicus programme by law or by
delegation do not incur any liability for any use of Copernicus WorldDEM-30.

## Permafrost zonation subsets

The PZI header defines 43,200 little-endian Float32 columns, 18,000 rows,
30-arc-second cells, lower-left `(-180,-60)`, and nodata `-9999`. One contiguous
full-row HTTP byte range was downloaded per window, and exact columns covering
the window plus 0.1 degrees were copied without value resampling. Each local
144 by 144 array was independently compared with its archived range bytes and
matched exactly. The range URL, response date, byte interval, ETag, size, and
SHA-256 are in the manifest.

Edinburgh DataShare DOI `10.7488/ds/1877` identifies this Global Permafrost PZI
dataset, assigns it CC BY 3.0, and requests attribution to the World Glacier
Monitoring Service (WGMS) as the data source. We credit WGMS as source, Gruber
as creator, and the University of Zurich as publisher. The exact rights and
bitstream fields are preserved in `source/pzi_rights_metadata.json`. The
DataShare archive uses a File Geodatabase, so no byte identity with the UZH
Float32 distribution is claimed. The committed TIFFs are attributed
adaptations of the licensed PZI data.

## Frozen limitations

Source epochs remain separate and do not describe a simultaneous Earth state.
The RGI is a near-2000 inventory, Copernicus DEM source acquisitions span
2011--2015, and PZI uses 1961--1990 air-temperature inputs. Glacier adjacency
does not establish loss of mechanical support. PZI intersection does not
measure local ground temperature or failure probability. The three windows
test numerical transfer from the pilot; they are not a global terrain sample.

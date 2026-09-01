# Held-out area source staging record

This directory freezes the case- and climate-blind inputs used by protocol
version 0.2. `source_manifest.json` records the exact remote objects, HTTP
response dates and validators, downloaded-object hashes, derivations, local
hashes, licences, and unavailable coverage. Source staging was completed only
after the region and window tables were committed.

## RGI selection and outlines

The selected region 03, 07, and 08 bytes came from the same version-labelled
RGI consortium-author mirror used by the pilot. NASA CMR identifies
NSIDC-0770 Version 7, DOI `10.5067/F6JMOVY5NAVZ`, and the authoritative NSIDC
distribution directory in the frozen `rgi_nsidc_collection_metadata.json`.
The mirror filenames, schemas, metadata, and complete regional counts are
internally consistent with that identity and the
[RGI 7 product documentation](https://www.glims.org/rgi_user_guide/03_data_decription.html),
but the NSIDC objects require Earthdata Login and were not downloaded here. No
archive-level byte-equivalence claim is made. This bounds the remaining
identity limitation while preserving the exact mirror URLs and hashes actually
analyzed.

The attribute tables were grouped by integer cells using the archived
`cenlat` and longitude-normalized `cenlon` fields. These fields locate an
approximately central point inside each outline; they are not geometric
centroids. Counts, `math.fsum` catalog areas, prefixed SHA-256 keys, and stable
ranks produced the 200 rows in `eligible_windows.csv`.

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

The 12 grids first produced from remote COG range reads were independently
replayed from all 25 fully downloaded native COGs. The replay used Rasterio
1.5.1, GDAL 3.12.4, PROJ 9.8.1, PyProj 3.7.2, and NumPy 2.5.2. For each region
and phase, it performed these exact operations:

1. verify every native COG against its manifest SHA-256;
2. parse signed integer latitude and longitude from each manifest ID and sort
   by `(latitude, longitude)`;
3. construct the target with `local_crs`, a 1 km buffer around the densified
   `window_geometry`, and `phase_grid`, using `multiple=3` only for `p00`;
4. initialize one Float32 NaN array per source and call
   `rasterio.warp.reproject` with the source transform, CRS, and nodata,
   registered target transform and CRS, `dst_nodata=np.nan`, and
   `Resampling.bilinear`;
5. replace the combined target only where the current source array is finite,
   so the later numeric tile wins in an overlap; and
6. compare the grid metadata and SHA-256 of the little-endian, C-order raw
   Float32 array with the committed analysis input.

`dem_replay.csv` freezes the 12 source orders, combined source-hash digests,
transforms, finite-cell counts, expected and replayed value hashes, and maximum
absolute differences. All arrays are cell-for-cell identical and every
maximum difference is zero. GeoTIFF container bytes are not the replay
criterion because equivalent tag serialization can change without changing
the grid values or metadata used by the analysis.

Each `source_set_sha256` is SHA-256 over the UTF-8 encoding of the ordered
records `source_id`, tab, `download_sha256`, joined by newline without a final
newline. Each value hash uses the little-endian Float32 C-order bytes described
above.

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

## Coverage fields

`source_coverage.csv` reports DEM and PZI validity before slope support or ice
exclusion. DEM and PZI coverage is complete in regions 03 and 08. In Svalbard,
the two HTTP-404 ocean tiles leave 452 of 2,998,350 unshifted reporting centers
without a finite DEM (99.9849% coverage); the other phases omit 414--451
centers. PZI coverage is complete in all 12 phase grids.

By contrast, `area_long.csv` `coverage_fraction` is the fraction of reporting
centers valid for the named stratum after slope support, glacier exclusion,
and, for the permafrost stratum, PZI validity. It is not a source-coverage
measure.

## Frozen limitations

Source epochs remain separate and do not describe a simultaneous Earth state.
The RGI is a near-2000 inventory, Copernicus DEM source acquisitions span
2011--2015, and PZI uses 1961--1990 air-temperature inputs. Glacier adjacency
does not establish loss of mechanical support. PZI intersection does not
measure local ground temperature or failure probability. The three windows
test numerical transfer from the pilot; they are not a global terrain sample.

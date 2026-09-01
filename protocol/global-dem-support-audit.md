# Full-frame Copernicus DEM asset-support audit

## Question and boundary

This protocol asks whether the public Copernicus DEM GLO-30 and GLO-90 object
inventories contain every 1 degree source object required by the frozen 1,826
cell reporting frame and its registered 1 km processing halos. It measures
asset metadata only. It does not open a raster payload, inspect elevation or
quality values, calculate steepness or equivalent area, select a replacement
sample, amend the issue 19 result, or estimate physical susceptibility or
hazard.

Before this protocol, its code, tests, expected identities, and a pre-access
manifest are committed and independently approved, do not list either public
bucket, query either STAC inventory by geocell, request an object, or inspect a
grid-specific key. Documentation pages and examples may be read only to define
the source products and key syntax.

## Frozen population and source definitions

The audit population is every row in the issue 17 frame:

- frame commit `0ff1c327468b5fb874ef2f87b1d64107838418e5`;
- `data/geographic_sample/frame.csv` SHA-256
  `482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879`;
- 1,826 cells in 19 nonempty dominant-RGI strata; and
- the issue 19 1 km processing halo, which requires the reporting geocell and
  its eight latitude-longitude neighbors.

The 96 issue 17 selected identities are retained only as a fixed annotation.
They cannot define, filter, weight, or choose an object or summary.

The Copernicus DEM product handbook defines WGS84 geographic 1 degree by
1 degree delivery units. GLO-30 has 1 arc-second latitude spacing and GLO-90
has 3 arc-second latitude spacing; both use latitude-dependent longitude
spacing. The Registry of Open Data on AWS defines the anonymous
`copernicus-dem-30m` and `copernicus-dem-90m` buckets. It describes GLO-30
Public as omitting some unreleased tiles, GLO-90 as worldwide at 90 m, and both
as omitting ocean-only geocells. These descriptions do not guarantee the
presence or raster validity of any expected object.

Freeze the native COG stem as

`Copernicus_DSM_COG_RR_NSLL_00_EWLLL_00_DEM`,

where `RR=10` for GLO-30, `RR=30` for GLO-90, latitude has two zero-padded
digits, and longitude has three. The object key must be exactly
`stem/stem.tif`. Normalize longitude to the half-open interval
[-180 degrees, 180 degrees). Candidate order is GLO-30 then GLO-90.

## Expected identities

For a reporting cell with integer south edge `s` and west edge `w`, enumerate
latitudes `s-1`, `s`, and `s+1`. Enumerate longitudes `w-1`, `w`, and `w+1`,
normalize each, then sort numerically. The object at `(s,w)` is the core object;
the other eight are halo objects. Cross all nine objects with both DEM
instances and all 1,826 frame cells. Preserve one row per cell, instance, and
object, even when several cells share the same object.

The expected table therefore has 1,826 x 2 x 9 = 32,868 rows, exactly one core
row per cell and instance, and nine unique identities within every cell and
instance. No bucket result may alter this table.

## Metadata acquisition

After independent approval only, use anonymous S3 `ListObjectsV2` requests
against each frozen bucket. Set `prefix` to the frozen instance stem prefix and
`max-keys=1000`. Follow only returned continuation tokens. Retain every XML
response byte, request URL, page number, retrieval time, byte count, SHA-256,
truncation flag, and next token. Stop on a malformed page, a repeated token, a
missing next token for a truncated page, a non-200 response, or a duplicate
exact DEM key.

Parse only keys matching `stem/stem.tif` with equal stems and the frozen
instance pattern. Retain key, object identity, byte size, ETag, and
last-modified metadata. Listing XML is source metadata. Do not send `GET`,
`HEAD`, or byte-range requests to an object key and do not follow a key or
asset link.

## Support summaries

Join expected and listed objects by exact instance and object identity. For
each frame cell and instance retain:

- required, present, and absent object counts;
- JSON-sorted absent identities;
- core-object presence; and
- full-halo presence, true only when all nine required objects are present.

Aggregate exact cell counts by dominant RGI region and by 10 degree band of the
reporting-cell south edge. Also report the two instance-wide counts. These are
finite-population enumerations and have no sampling standard error. Selected
membership is descriptive annotation only and is excluded from every group
definition and decision.

Object presence is necessary but not sufficient for calculation. A present
object can contain invalid values, radar artifacts over snow and ice,
vegetation or structures, and source-epoch mismatch. An absent ocean-only
object cannot be assumed irrelevant to a PZI-intersection center without a
separate frozen mask-support calculation. Accordingly, use `object present`,
`core-object present`, and `full-halo object support`; do not use `terrain
present`, `DEM complete`, `source complete`, `zero elevation`, `zero area`, or
`susceptible`.

This audit does not authorize a GLO-90 substitution, a mixed GLO-30/GLO-90
mosaic, reuse of the issue 17 sample, or a new probability design. Any terrain
calculation requires a later public protocol after this asset result is frozen.

## Outputs and review

Commit the protocol, expected table, code, tests, and pre-access manifest
before metadata acquisition. After approval, commit the retained listing XML,
page ledger, parsed inventory, cell table, regional and latitude summaries,
summary JSON, final manifest, an executed notebook with at most 40 code lines,
a non-map publication figure, and updated manuscript source and PDF.

Handwritten analysis plus tests may not exceed 300 lines. Tests cover hashes,
row counts, coordinate formatting, antimeridian normalization, core/halo role,
strict XML parsing, exact stem equality, pagination stops, duplicate rejection,
support counts, and independence from selected membership. Independent source,
numerical, code/design, and mechanics/manuscript audits must approve the
pre-access boundary and final result.

## Sources fixed before access

- Copernicus DEM Product Handbook, version 5.0:
  https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf
- Registry of Open Data on AWS, Copernicus DEM:
  https://registry.opendata.aws/copernicus-dem/
- Copernicus Data Space DEM access documentation:
  https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html


=== readme version 1.0, 25 Feb 2012 ===

This file documents the binary data made avaialbe together with the
Global Permafrost Zonation Map published in the reference given below.
Please make sure you understand the limitation of this data as outlined
in that paper befor you use it.

Data link: http://www.geo.uzh.ch/microsite/cryodata/pf_global/


=== REFERENCE ====
The derivation of tthis data is described and referenced in detail here:

Gruber, S. 2012: Derivation and analysis of a high-resolution estimate of global permafrost 
zonation, The Cryosphere, 6, 221-233. doi:10.5194/tc-6-221-2012.

Publication link: http://www.the-cryosphere.net/6/221/


=== RAW FILES ====
The files described here are 32-bit floating point binaries that 
cover the entire globe north of 60 degrees South and have a grid
spacing of 30 arc-senconds latitude and longitude, WGS 1984. For
each data layer, one data file (*.flt) of about 3.1 GB size and
one very small header file (*.hdr) as shown below.

--- Permafrost Zonation Index ---
PZI.flt (3.1 GB) Terrain Ruggedness Index
PZI.hdr (0.2 KB) Header file
The PZI is scaled from 0.1 to 1.0. The fringe of uncertainty has a uniform value of 0.01,
the background value is 0.

--- Terrain ruggedness ---
ruggedness.flt (3.1 GB) Terrain Ruggedness Index
ruggedness.hdr (0.2 KB) Header file

--- Air temperature ---
MAAT_MEAN.flt (3.1 GB) MAAT average on CRU TS2.0 and NCEP/NCAR and SRTM30
MAAT_MEAN.hdr (0.2 KB) Header file

MAAT_CRU30.flt (3.1 GB) MAAT based on CRU TS2.0 and SRTM30
MAAT_CRU30.hdr (0.2 KB) Header file

MAAT_NCEP30.flt (3.1 GB) MAAT based on NCEP/NCAR TS2.0 and SRTM30
MAAT_NCEP30.hdr (0.2 KB) Header file

--- Headers ---
ncols         43200
nrows         18000
xllcorner     -180.000000
yllcorner     -60.0000000
cellsize      0.008333333
NODATA_value  -9999
byteorder     LSBFIRST+



=== HOW TO READ THIS DATA ====
Here are some sample instruction how this data can be read.

- In ArcGIS interactively
   * Arc Toolbox -> Conversion Tools 
                 -> To Raster 
                 -> Float to Raster
   * Arc Toolbox -> Data Management Tools 
                 -> Projections and Transformations 
                 -> Define Projection
     Then select projection :Define Coordinate System -> Select 
                                                      -> Geographic Coordinate Systems 
                                                      -> World 
                                                      -> WGS 1984.prj

- In ArcGIS scripting example:   
  FloatToRaster_conversion H:\ruggedness.flt H:\permafrost.gdb\ruggedness
  DefineProjection_management H:\permafrost.gdb\ruggedness GEOGCS['GCS_WGS_1984',
  DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],
  PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]]
   
- With IDL   
  ruggedness=rgridfloat("H:\ruggedness.flt",header=header)
  The function rgridfloat is also available for download with this data
  in pre-compiled format (rgridfloat.sav). To obtain help on this
  type a=rgridfloat() at the IDL prompt.
  IDL function: www.geo.uzh.ch/microsite/cryodata/pf_global/rgridfloat.sav

- With ENVI
  File -> Open Image File 
  Then, use these setting in the f
  Samples: 43200, Lines: 18000, Bands: 1
  File TYpe: ENVI Standard, Byte Order: Intel
  Data Type: Floating Point, Interleave: BSQ


=== DATA SOURCE ====
This data is available in differing formats:
- Web Mapping Service
- KMZ file for Google Earth
- Raw binary data

Find more details here:
www.geo.uzh.ch/microsite/cryodata/pf_global/


=== DISCLAIMER ====
The data are provided "as is" and University of Zurich makes no
representations or warranties, express or implied. By way of example,
but without limitation, University of Zurich makes no representations or
warranties of merchantibily or tness for any particular purpose or that
the data will meet your requirements or that the use of the data or
documentation will not infringe any third party's patents, copyrights,
trademarks or other rights. Furthermore, University of Zurich does not
warrant or make any representations regarding use of the data in terms
of correctness, accuracy, reliability, or otherwise or that defects in
the data will be corrected. University of Zurich will not be liable for
any consequential, incidental, or special damages, or any other relief,
or for any claim by any third party, arising from the use of the data.
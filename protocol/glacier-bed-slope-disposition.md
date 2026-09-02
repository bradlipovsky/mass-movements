## IceBoost bed-slope sensitivity disposition

The registered 300 m modeled-bed calculation is unavailable under the frozen
design and was not executed. A post-primary metadata-only pilot opened no raster
values but found that IceBoost v2 TIFF descriptions are ordered `thickness`,
`thickness_err`, `jensen_gap`, `h_wgs84`, and `n_geoid`, rather than the prose
order anticipated by the decoder. A valid future decoder must require these
descriptions and state whether surface elevation is `h_wgs84 - n_geoid` before
subtracting thickness.

There is also a design-level support failure. Forty of the 207 participating RGI
objects have catalog area below the 0.282743 km² area of a 300 m-radius disk, so
they cannot contain even one pixel after the registered 300 m erosion. Those
objects occur in four case-specific matched sets and three of five final
dependence components. Whole-component completeness would leave only three cases
in two components (Aru-1, Aru-2, and Flat Creek), below the primary completeness
gate. Selecting a smaller primary radius after seeing this support is not
permitted; 100 and 500 m were registered only as sensitivities to the 300 m
calculation.

IceBoost thickness also uses surface slope, air temperature, and other model
predictors. Any future bed result is modeled and predictor-coupled, not an
independent measurement of pre-event source geometry, and cannot alter the
primary RGI/ERA5 status.

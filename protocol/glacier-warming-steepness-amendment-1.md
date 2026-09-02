## Amendment 1: protocol v0.2

All three independent audits rejected v0.1 for outcome access. No systematic
case/background slope, ERA5 trend, or thickness outcome was opened. Outcome
access remains closed.

Version 0.2 makes the following prospective changes:

- restricts the primary frame to the ten initial-volume cases and unique RGI
  links, giving at most seven independent trigger/site clusters;
- caps the result at `DESCRIPTIVE_ONLY` and supplies an exhaustive completeness
  and directional-consistency rule;
- defines exact outcome-blind matching fields, inclusive calipers, missingness,
  deterministic hash ordering, and no control reuse across independent clusters;
- binds the ERA5 store, snapshot, group, variable, spatial weights, calendar
  completeness, OLS endpoint, and fixed-lag HAC calculation;
- defines case and cluster contrasts, shared-cell dependence merging, common
  endpoint completeness, midranks, conservative zero handling, and exact sign
  calibration;
- records RGI's mixed outline/DEM epochs and prevents claims about antecedent
  source-zone or bed geometry;
- requires per-member IceBoost metadata and uncertainty propagation, records
  predictor coupling, and makes bed products secondary;
- requires two distinct closed crosswalk reviews, enumerates same-GLIMS RGI
  candidates, and adds ordered output schemas and manifest bindings.

The access audit also records two incidental exposures: a prior diagnostic
printed Bering Glacier's RGI slope, and a later schema search printed generic
RGI slopes from already committed denominator files. Neither exposure identified
a study case or selected background; neither opened ERA5 or thickness values.

This amendment will be bound to an immutable commit and file hashes after exact
numerical, mechanics, and implementation re-review.

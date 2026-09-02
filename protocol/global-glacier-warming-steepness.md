# Antecedent warming and glacier steepness

Version 0.2, amended in GitHub Issue 33 before systematic access to the
case-glacier slope and temperature outcomes. Version 0.1 was rejected for
outcome access by independent numerical, mechanics, and implementation audits;
this version makes their required closure and decision rules executable.

## Physical question and claim boundary

This calculation tests whether documented large glacier detachments and
collapses had larger matched contrasts in each of two catalog attributes: a
strictly antecedent regional air-temperature trend and RGI mean-slope value.
Sustained atmospheric warming can modify glacier thermal and
hydrologic conditions, while geometry contributes to gravitational loading.
This catalog screen does not identify either process and neither attribute is
a sufficient failure law.

The statistical null is that at least one of the two case-background
contrasts--warming or surface slope--is non-positive. The alternative requires
both contrasts to be positive. This is not a test of a seven-day trigger
anomaly. The Issue 29 short-window result remains a separate assignment and
timing diagnostic.

The event catalog is neither a complete failure census nor a probability
sample. Its background glaciers may include undocumented failures. The
analysis can therefore describe contrasts among discovered catalog cases,
not failure probability, absolute risk, global susceptibility, causation,
anthropogenic attribution, or an operational forecast.

## Frozen primary case frame

The screened frame is derived mechanically from the already frozen discovery
table. A row enters it if and only if it has
`consensus_decision=include`, `analysis_role=event_candidate`, and
`initial_failure` in `{glacier_detachment, glacier_collapse}`. The rule gives
14 rows:

`eqip-sermia-2014`, `tinguiririca-2007`, `flat-creek-2013`,
`shuraki-kapali-2017`, `sedongpu-2018`, `marmolada-2022`,
`bukadaban-2022`, `dykhtau-2023`, `kunlun-b2-2001`,
`kunlun-k2-2001`, `kunlun-b4-2001`, `aru-1-2016`, `aru-2-2016`, and
`petra-dp19`.

The primary case frame further requires `threshold_quantity=initial_volume`.
It contains ten rows: `tinguiririca-2007`, `flat-creek-2013`,
`shuraki-kapali-2017`, `bukadaban-2022`, `kunlun-b2-2001`,
`kunlun-k2-2001`, `kunlun-b4-2001`, `aru-1-2016`, `aru-2-2016`, and
`petra-dp19`. This common qualification prevents travel distance or tsunami
runup, which can depend on slope and cascade geometry, from defining the
primary cases. The complete 14-row screened frame is retained as a sensitivity.

The case is the source glacier, not a receiving glacier, a glacier that only
gave the place name, or ice entrained after bedrock failure. Each row must be
crosswalked to the RGI 7 glacier that contained the failed ice before its event.
The crosswalk is retained as `unique`, `lineage_union`, `ambiguous`,
`no_rgi_object`, or `unresolved`. Only a final `unique` link with two agreements
enters the primary calculation. A `lineage_union` is retained only as a
sensitivity because its attributes are not defined by a single inventory
object. All other rows remain visible with their exclusion reason. Two
distinct reviewers must independently record `agree` or `disagree` for every
row. No row may remain pending at preaccess freeze. An admitted link requires
two agreements; any disagreement is adjudicated to exclusion unless a revised
assertion receives two new agreements. GLIMS identifiers are not globally
unique, so all RGI objects sharing a cited GLIMS identifier are enumerated and
the identifier alone cannot establish uniqueness.

Crosswalk evidence is ranked as follows: a published source polygon and RGI or
GLIMS identifier; a published source polygon; an event-specific glacier name
and reconstruction; or a source-locating point whose glacier membership is
unambiguous. Nearest-outline distance may generate candidates but cannot
establish a link. Store the evidence source and locator, mapping method,
distance or overlap, inventory date, lineage members, and reviewer decisions.

Distinct source glaciers remain distinct cases. Initial dependence clusters
are derived, not typed freely, from the frozen `trigger_cluster` and
`site_group` rows in `data/candidate_clusters.csv`; all other cases are
singletons. Repeated failures of one source glacier use its earliest qualifying
event as the index date. Aru-1 and
Aru-2 form one site-dependence cluster, while the three Kunlun failures form
one common-earthquake cluster. Other literature-supported shared triggers or
sites are clustered before outcomes are opened.

Glacier detachments, in which a substantial glacier tongue loses basal or
lateral resistance, and hanging-glacier or ice-cliff collapses do not share a
single force balance. They are reported as separate mechanism strata. Their
pooled primary comparison is only a catalog-morphology screen and receives no
mechanical interpretation. Rock, rock-ice, and ice-rock source failures are a
separate future cohort and cannot be pooled to increase sample size.

## Global glacier frame and matched backgrounds

The glacier frame is the complete RGI 7 glacier product already retained in
19 source archives: 274,531 glacier outlines targeted approximately to the
year 2000. RGI glaciers are comparison objects, not verified nonfailures.
Exclude every nonempty RGI identifier in the frozen 14-row crosswalk. No other
catalog exclusion can be added after feature access.

For each admitted primary case, form a pool without writing, logging, comparing,
or otherwise using `slope_deg`, any thickness field, or any climate value. The
source CSV parser necessarily tokenizes the complete row; its only permitted
operation is an immediate projection to this exact outcome-blind matching
schema: `rgi_id`, `o1region`, `o2region`, `glims_id`, `src_date`, `cenlon`,
`cenlat`, `area_km2`, `conn_lvl`, `zmed_m`, `aspect_sec`, `dem_source`, and
`rgi_grid_spacing_m=min(100,14*sqrt(area_km2)+10)`. The first eligible matching
level requires:

1. the same RGI second-order region and connectivity class;
2. glacier area within a factor of four of the case area;
3. median elevation within 500 m; and
4. aspect in the same or an immediately adjacent 45-degree sector.

The area interval is inclusive `[0.25,4]` and the elevation difference is
inclusive at 500 m. Aspect sectors 1 and 8 are adjacent. Sector 9 or any missing
aspect is ineligible at level 1 but may enter after the aspect restriction is
removed. Other missing matching attributes are ineligible at every level and
are never imputed.

If this contains fewer than 20 glaciers, remove the aspect restriction. If it
still contains fewer than 20, use the first-order rather than second-order
region while retaining connectivity, area, and elevation restrictions. A case
with fewer than 20 glaciers after this ordered relaxation is `unmatched`.
No outcome-dependent caliper change or replacement is permitted.

From the first level containing at least 20 glaciers, select exactly 20 by the
ascending SHA-256 value of
`glacier-warming-steepness-v1|case_id|rgi_id`, with `rgi_id` resolving a hash
tie. This is an outcome-blind deterministic ordering, not a literal random
sample with a design inclusion probability. Retain the complete pools, hashes,
ranks, and selected rows. Process dependence clusters in ascending cluster ID
and cases in ascending case ID. Once selected in one dependence cluster, a
background glacier is unavailable to later independent clusters; cases within
one cluster may share it. If this leaves fewer than 20 controls, advance down
the already frozen hash ranking within the same pool. Thus independent cluster
contrasts do not share background glaciers.

The primary background estimand weights glaciers equally within each matched
set. Glacier-area weighting and the full unmatched global RGI distribution are
descriptive sensitivities because they answer different questions.

## Primary exposure endpoints

### Antecedent warming

For every case and its matched background glaciers, use the 20 complete
calendar years ending on 31 December of the year before the case event.
Controls inherit the case index year. This places every primary temperature
value before failure and keeps the earliest cases within 1981 onward.

Use ERA5 2-m air temperature from
`s3://earthmover-icechunk-era5/icechunkV2`, immutable snapshot
`T9H8SG2PVXWNY0QNJPJG`, group `single/temporal`, variable `t2m`. Access is
limited to frozen unique cells and calendar years 1981--2022. Treat each ERA5
coordinate as the center of its regular 0.25-degree cell; convert RGI longitudes
to the store's 0--360 convention, wrap cells periodically at 0 degrees, and
clip latitude bounds at the poles. Retain only positive-area outline--cell
intersections. The primary geodesic-area weight is
`w_gc=A(outline_g intersect cell_c)/sum_c A(outline_g intersect cell_c)`.
Small glaciers wholly within one cell receive that cell. Freeze cell identities
and weights before temperature access. A central-point assignment and all four
bracketing grid points are spatial sensitivities.

Define `index_year=int(date_start[:4])`. For index year `Y`, calculate arithmetic
annual means for years `Y-20,...,Y-1`, with every unique UTC hour equally
weighted. Each cell-year must contain exactly 8,760 samples, or 8,784 in a leap
year, with no duplicate or missing timestamps; all 20 years must be complete.
For annual means `T_y`, fit `T_y=a+beta*x+epsilon_y` at `x=0,...,19` by ordinary
least squares. The primary warming rate is `10*beta` K per decade and the fitted
endpoint change is `19*beta` K. Use a Newey--West/Bartlett HAC covariance with
fixed lag 2 and the `n/(n-2)` finite-sample multiplier for the two fitted
coefficients. Theil--Sen slope is a registered
robust sensitivity. A constant lapse-rate correction changes
the intercept but not the trend, so no lapse correction is applied. ERA5 is a
regional atmospheric exposure at model orography, not measured glacier, bed,
rock, or permafrost temperature.

### Glacier surface slope

The primary geometry endpoint is RGI 7 `slope_deg`, the published glacier-wide
mean surface slope calculated from a size-dependent 11.4--100 m RGI-TOPO grid
and the approximately year-2000 outline. Retain `dem_source`, grid spacing,
source date, and missingness. Copernicus DEM acquired mainly during 2011--2015
supplies all but 128 RGI glaciers. The attribute therefore mixes outline and
DEM epochs and may use a post-failure surface for early cases. It is not a
failure-plane angle, an antecedent or source-patch slope, or necessarily the
geometry at the event date.

Using this mixed-epoch endpoint makes the initial catalog-level screen
reproducible across the global census. It cannot support a claim about
antecedent source geometry. A physical source-zone calculation requires a
demonstrably pre-event elevation model and the same product, epoch, support,
and resolution rule for controls; that calculation is outside this screen.

## Registered mechanics sensitivities

Bed elevation is modeled as

`b(x,y) = s(x,y) - h(x,y)`,

where `s` is surface elevation and `h` is modeled ice thickness. Bed slope is
therefore modeled rather than observed. Use the pinned IceBoost v2.0 RGI 7
five-band products only after their source hashes, band semantics, coordinate
reference systems, vertical datum, nodata rules, and case-independent coverage
are frozen. Zenodo exposes 19 RGI 7 regional archives totaling 3,694,204,303
bytes and supplies MD5 digests. Freeze their exact names, sizes, and MD5 values;
after byte-only retrieval compute SHA-256 and inventory every central-directory
member before any TIFF decode. Then verify each used member's CRS, resolution,
nodata, units, datum, mask, and five-band order: thickness, thickness error,
surface elevation, geoid elevation, and Jensen gap. The Zenodo record states
CC-BY-4.0; raw archives nevertheless remain external to Git because of their
size. IceBoost uses surface slope, air temperature, mass balance, and other
predictors; its bed result is not independent of the primary exposures.

For each used IceBoost product member, operate on its native documented grid;
100 m is expected but not assumed. Fit local planes to bed elevation over a
fixed 300 m radius after eroding the glacier mask by that radius. Report the
area-weighted median bed-gradient angle and its interquartile range. Repeat at
100 and 500 m as scale sensitivities. Also calculate surface slope on the same
grid and scale, mean thickness, and the pointwise leading driving-stress proxy

`tau_d(x,y) = rho_i g h(x,y) sin{alpha_s(x,y)}`,

with `rho_i=917 kg m^-3` and `g=9.80665 m s^-2`. Report its glacier-mask
median and interquartile range. Report the glacier-mask median and interquartile
range of the supplied pixelwise `sigma_H`, derived from 50 model/input
perturbation evaluations. The product releases `sigma_H`, not the ensemble or a
joint spatial covariance, so it is not propagated through bed gradients or
driving stress without a separately registered spatial error model. The
proxy omits longitudinal and lateral stress gradients, basal water pressure,
till strength, and thermal state. Bed-slope magnitude itself is not the slab
driving slope.

Along-flow bed grade, defined by projecting the modeled bed gradient onto the
smoothed surface-gradient flow direction, and residual bed roughness after the
300 m plane fit are morphology sensitivities. IceBoost uses surface slope and
temperature predictors, so none of its bed, surface, or stress results is an
independent corroboration of the primary attributes. Bed-gradient uncertainty
is reported as unavailable under this version rather than inferred from
independent pixel draws.

Farinotti et al. (2019) or Millan et al. (2022) is a registered independent-
method product sensitivity only after its own approved source and compatibility
manifest establishes exact RGI lineage and a compatible surface grid. A DOI
citation alone does not authorize download or decode under this gate. If
compatible surface elevation, datum, epoch, or
lineage is not established, report that sensitivity as unavailable rather
than subtracting unrelated grids. Opposite bed-contrast signs across products
make the bed interpretation indeterminate, but do not alter the primary
surface-slope test.

## Contrasts, dependence, and decision rule

For endpoint `q`, case `i`, and its frozen matched set `S_i`, calculate

`D_iq = q_i - median_{j in S_i}(q_j)`.

The case midrank percentile is `100*(L+0.5*E)/21`, where `L` and `E` are the
numbers of the 21 values strictly below and equal to the case value. For the
cases `I_c` in dependence cluster `c`, calculate the equally weighted
within-cluster contrast

`D_cq = |I_c|^-1 sum_{i in I_c} D_iq`.

Clusters receive equal weight. After ERA5 weights are frozen, merge trigger/site
clusters connected by any shared positive-weight ERA5 support cell among their
cases or controls; connected components are the final dependence clusters. A
background glacier cannot be shared across independent trigger/site clusters.
Both endpoints use the same paired-complete final clusters. A case is complete
only when both case endpoints and both endpoints for all 20 required controls
are present. If one case is incomplete, exclude that case's entire final
cluster from both endpoint summaries. `complete_cases` is the sum of original
case counts over retained final clusters. Preserve every excluded case and its
endpoint-specific missing reason in a ledger.

For each primary endpoint, let `n` be the common number of paired-complete final
clusters, `K_q=sum_c 1(D_cq>0)`, and
`p_q=P{Binomial(n,0.5)>=K_q}`. This reference diagnostic assumes independent
final-component signs with `P(D_cq>0)<=0.5`; it is not design-based inference
from the event catalog. Zero contrasts count as nonpositive. Report the sample
median cluster contrast and the 95% interval obtained by inverting this binomial
sign reference; if no finite two-sided order-statistic interval exists at the
observed `n`, report both bounds as unavailable. As a secondary location
summary, report the one-sample Hodges--Lehmann estimate: the median of all Walsh averages
`(D_cq+D_dq)/2` for `c<=d`.
The joint intersection--union p-value is

`p_joint = max(p_warming, p_surface_slope)`.

The frozen ten primary cases contain at most seven independent trigger/site
clusters, before any shared-cell merging. The primary decision cap is therefore
`DESCRIPTIVE_ONLY` by design; the study cannot return `SUPPORTED` or
`NOT_SUPPORTED`. It is called *directionally consistent* only if at least eight
of ten primary cases are paired-complete, both sample median cluster contrasts
are positive, and the median across clusters of the within-cluster mean case
ERA5 trend is itself positive. The exhaustive rule is:

1. any failed completeness, common-set, protocol, or support gate gives
   `INDETERMINATE` with no direction label;
2. otherwise, three positive quantities--warming contrast median, slope
   contrast median, and absolute case-warming median--give
   `DESCRIPTIVE_ONLY, consistent`;
3. otherwise, two nonpositive contrast medians give
   `DESCRIPTIVE_ONLY, inconsistent`; and
4. every remaining sign combination gives `DESCRIPTIVE_ONLY, mixed`.

Unavailable or indeterminate secondary bed products do not alter this primary
status.

For calibration only, even 9 positive clusters out of 11 give one-sided
`p=0.0327`, with power 0.313 if the positive-sign probability is 0.7; 9 of 10
give `p=0.0107`, with power 0.149. Joint power is lower. The actual maximum of
seven primary clusters is weaker still, so exact p-values are diagnostic rather
than confirmatory evidence.

Bed slope, driving stress, the complete 14-row screen, Theil--Sen trends,
spatial ERA5 alternatives, area weighting, and any rock/mixed cohort are secondary.
They cannot rescue a failed primary result. No warming-by-slope interaction is
fit because the frozen sample is too small to identify it.

## Staged access and outputs

1. Commit this protocol, `output_schemas.json`, source metadata, and tests.
2. Build the outcome-blind RGI matching frame and review packet, then complete
   the two-reviewer case crosswalk. Commit a manifest sealing all 14 statuses,
   dependence clusters, complete matching pools, and the selected 20 controls
   per admitted matched primary case.
3. Freeze glacier-to-ERA5 cell weights and the IceBoost member inventory before
   opening either product's values.
4. In a separate sub-500-line change, commit and independently approve an exact
   outcome-analysis program, source, environment, and schema manifest binding
   protocol, schema, program, tests, requirements,
   frame, and access-audit hashes. Only then decode RGI slope, temperature, or
   thickness.
5. Seal background features before joining case labels. Publish derived tables
   atomically and preserve every missing reason.
6. Execute one concise notebook, make a non-map comparison figure, update the
   manuscript and PDF, and obtain independent numerical, mechanics, and claim
   reviews.

Raw source archives remain outside Git but are bound by URL, DOI or snapshot,
retrieval time, byte count, license, and cryptographic digest. Canonical
derived CSV partitions and manifests are committed. No approved access commit
may be rebased.

Before this version was frozen, one incidental code-path test printed the RGI
surface slope of Bering Glacier (`5.7436967` degrees). No systematic case or
background slope comparison and no new antecedent temperature or thickness
outcome had been opened. A later schema search also printed previously committed
generic RGI slope records from denominator GeoJSON; none identified a study case
or selected background and no temperature or thickness value was opened. Both
exposures remain in the audit record.

The strongest permissible result sentence is: "Among crosswalked documented
cases and matched RGI objects, cases had [larger/smaller] strictly antecedent
ERA5 trends and [larger/smaller] mixed-epoch RGI mean-slope attributes."
Neither a positive nor negative result permits inference about pre-event source
slope, bed failure, basal water pressure, till weakening, glacier thermal
state, or a warming-trigger mechanism.

## Registered sources

- RGI 7 glacier product and field definitions:
  https://www.glims.org/rgi_user_guide/products/glacier_product.html
- RGI 7 data DOI: https://doi.org/10.5067/F6JMOVY5NAVZ
- ERA5 single-level hourly data DOI: https://doi.org/10.24381/cds.adbb2d47
- Immutable Icechunk ERA5 public mirror:
  https://registry.opendata.aws/earthmover-era5/
- IceBoost method: https://doi.org/10.5194/gmd-18-2545-2025
- IceBoost v2.0 RGI 7 products: https://doi.org/10.5281/zenodo.17724512
- Farinotti et al. consensus thickness data:
  https://doi.org/10.3929/ethz-b-000315707
- Millan et al. thickness data: https://doi.org/10.6096/1007

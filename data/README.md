# Event catalog

The catalog separates event identity, quantitative measurements, and causal
claims. This prevents a modeled quantity or interpretation from being treated
as a direct observation.

`events.csv` contains one row per source failure, dependent episode, or
monitored unstable slope. `event_group_id` clusters failures at one site.
`analysis_role` distinguishes an `event_candidate` from a
`dependent_episode` and a `prospective_case`. The October 2023 Dickson
Fjord episode is dependent on the September site; Barry Arm is prospective.
Neither is an independent event-time attribution unit. Event dates and
coordinates have separate source fields so that these analysis-critical
values remain traceable.

`measurements.csv` contains one quantity per row. `value_relation` distinguishes
point values from approximations, lower bounds, upper limits, and ranges.
`uncertainty_type` states what a reported uncertainty means when the source
defines it; `reported_unspecified` preserves an uncertainty whose probability
semantics have not yet been verified. Observation periods and model scenarios
have separate columns. The allowed evidence kinds are:

- `observation`: a directly measured or enumerated quantity;
- `preliminary_observation`: an agency value subject to revision;
- `reconstruction`: a quantity derived from mapped geometry or combined data;
- `model_output`: a result conditional on stated model assumptions.

`claims.csv` records process and attribution statements. `claim_scope`
distinguishes `process_chain`, `immediate_trigger`,
`climate_preconditioning`, `precursor`, and `catalog_reconciliation`.
`published_inference` preserves a source author's interpretation;
`project_interpretation` is an inference made in this catalog and remains
explicitly labeled.

`evidence_strength` is independent of claim type. `direct` denotes geometry or
timing seen in measurements; `strong` denotes an inference supported by
multiple quantitative observations; `moderate` denotes a mechanically
consistent inference with unresolved alternatives; `weak` denotes a tentative
or indirect relation; and `unresolved` denotes insufficient evidence. These
levels describe support within the event literature, not formal attribution to
anthropogenic forcing.

Source keys resolve to `latex/references.bib`. `source_locator` identifies the
abstract, section, figure, supplement, or dated agency record. Run
`make check` after editing: the validator enforces exact headers, identifiers,
types, controlled vocabulary, value/bound consistency, provenance, grouping,
and process/trigger/preconditioning coverage.

This convenience seed is not a complete or climate-blind inventory and cannot
support a frequency trend or systematic climate association. The 2026 Nepal
entry should also be revisited when a peer-reviewed reconstruction becomes
available.

## Climate-blind discovery tables

`candidates.csv` is separate from the convenience seed. It records every
event promoted from the structured frames or independent searches to detailed
screening, including explicit exclusions and unresolved records. Each row has
two differently named reviewers, their independent decisions and controlled
reasons, a consensus decision, and the source passage supporting the
operational threshold. `event_group_id` identifies a shared source slope or
repeat-failure site. It does not merge distinct sources that share an
earthquake. Trigger, cascade, site, and common-tsunami dependence are recorded
explicitly in `candidate_clusters.csv`, allowing the later analysis to cluster
uncertainty at the level appropriate to each estimand.

The candidate table deliberately has no atmospheric anomaly, glacier-change,
permafrost, or asserted-cause field. `trigger_time_eligible=no` retains an
included event for site-level preconditioning analysis when its month-scale or
satellite-bracketed date is too imprecise for a short weather window.
`uncertain` means that the occurrence is plausible and may pass a threshold,
but primary-source identity, material taxonomy, or episode-specific threshold
evidence is unresolved. It is not a weaker form of inclusion.
`threshold_quantity=not_documented` prevents a downstream reach, deposit
volume, signal amplitude, or compound-row total from being mislabeled as an
operational source-failure threshold.

`discovery_searches.csv` logs the structured-frame enumeration and each
independent query suite. Exact individual queries are transcribed in
`protocol/discovery-search-transcript.md`; the eligibility, reconciliation,
and freeze rules are in `protocol/discovery.md`. Inventory trigger or cause
columns were ignored. The PANGAEA and High Mountain Asia datasets support
discovery, while final included values require a primary event reconstruction
or an authoritative agency record.

`frame_screening.csv` records the mechanical flow through the two enumerated
frames. The PANGAEA landing page reports 354 cases, while its downloaded table
contains 355 landslide rows because a tsunami can have multiple source
failures. `numeric_threshold_rows` is only a prefilter count. It neither
establishes the alpine rock/ice population nor substitutes for primary-source
screening. High Mountain Asia rows containing several occurrence dates receive
an included episode only when the qualifying measurement can be assigned to
that episode.

`candidate_provenance.csv` is the frame-reconciliation crosswalk. It gives a
visible candidate disposition for all 40 PANGAEA and 38 High Mountain Asia
rows that pass the numeric prefilter. One inventory row may map to several
candidate occurrences; this preserves compound events without assigning a
row-level volume or travel distance to every occurrence.

`source_frames/` preserves the two exact downloaded files, their SHA-256
checksums, and a 78-row qualifier manifest with immutable worksheet or TSV row
locators. The crosswalk must exactly match this manifest.

The validators check the preregistered numerical thresholds, value/bound
shape, units, occurrence window, date and coordinate bounds, reviewer
independence, decision-role coherence, trigger-time precision, exact frame
reconciliation, decision--reason consistency, and dependence-cluster links.
Their final lines report live counts, so documentation does not need a
separately maintained count.

## Climate- and case-blind susceptible terrain

`denominator/` is a three-window validation frame constructed without failure
locations or reanalysis. RGI 7.0 glacier centroids select one deterministic
one-degree window in Alaska, Central Europe, and Central Asia. The source
directory contains window-only glacier features, local equal-area Copernicus
DEM grids, raw-value PZI subsets, and ITS_LIVE climatological `count` subsets.
`source_manifest.json` records 39 remote objects, every local hash, source
ETag and size where available, derivation, product version, and the rejected
WCS PZI responses that encoded documented background zero as nodata. It also
records product-level access and licence terms. `eligible_windows.csv` retains
every eligible blind-selector key and digest, not only the three winners.
`PROVENANCE.md` records source-staging transformations and the known request-
timestamp limitation.

`objects.csv` retains all glacier polygons and every four-neighbor rock-slope
component, including objects below the conditional-volume cutoff.
`summary.csv` reports counts and areas by region, stratum, slope, glacier
contact or PZI threshold, grid spacing, prescribed depth, and boundary scope.
The strata overlap and cannot be summed. `windows.csv` records the registered
selector and local CRS hashes. `validation_sample.csv` is the deterministic
five-object-per-stratum sample; all 45 rows in `validation_review.csv` passed
area, connectivity, mask, boundary, and coverage checks.

RGI outlines target dates near 2000, the Copernicus surface model uses
2011--2015 acquisitions, PZI uses 1961--1990 air temperature, and ITS_LIVE
`count` covers its 2014--2022 climatology. These epochs remain separate fields.
The frame is a reproducibility and scale-sensitivity test, not a simultaneous
snapshot, regional population estimate, susceptibility model, or failure
probability. Run `make artifacts-denominator` with the pinned analysis
environment to regenerate tables, notebook figures, and the manuscript.

Edinburgh DataShare DOI `10.7488/ds/1877` identifies Gruber as creator and UZH
as publisher of the same Global Permafrost PZI dataset and assigns it CC BY
3.0. `pzi_rights_metadata.json` preserves the official API evidence. Its ESRI
File Geodatabase is not claimed byte-identical to the UZH raw grid; the
committed window subsets are attributed adaptations.

The adapted elevation grids were produced using Copernicus WorldDEM-30 © DLR
e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under
COPERNICUS by the European Union and ESA; all rights reserved. The
organisations in charge of the Copernicus programme by law or by delegation
do not incur any liability for any use of the Copernicus WorldDEM-30.

## Source-coordinate and UTC-onset audit

`event_audit/summary.csv` is a 53-row analysis layer over the frozen
trigger-time set; it does not amend `candidates.csv`. The two long assertion
tables preserve competing coordinates, clocks, pulse interpretations, source
locators, and independent review states. An inventory or catalog event point
does not become a source coordinate unless primary geometry establishes the
initiating scar or source-area centroid.

A checked source that reports no usable numeric point is encoded with blank
latitude and longitude, `geometry_role=not_reported`,
`evidence_method=not_available`, and uncertainty
`gt_5_km_or_unknown`. No other blank-coordinate combination is valid. A local
clock without a documented scale has `time_basis=unknown` and no UTC fields.
Each time assertion has `onset_role=source_failure`, `trigger_proxy`, or
`context_only`; station arrivals, report times, and generic catalog times stay
visible but cannot support accepted or conflicting onset summaries. The
validator rejects accepted summaries without an independently agreed,
target-eligible assertion and checks all half-open UTC conversions.

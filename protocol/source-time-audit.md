# Source-coordinate and onset-time audit

Version 0.1. Registered on 30 August 2026 before the audit tables were
populated. GitHub issue
[#7](https://github.com/bradlipovsky/mass-movements/issues/7) is the public
registration record.

## Question and inferential boundary

This audit asks where each frozen trigger-time-eligible failure initiated and
what UTC onset interval is supported by event-specific evidence. It repairs a
measurement and provenance gap exposed by the registered ERA5 pilot. It does
not test whether warm conditions promote failure, change event eligibility,
or estimate a failure probability.

The discovery inventory remains immutable. Audited values are an analysis
layer, so original and revised assertions remain side by side. A subsequent
temperature extraction must be separately registered after this layer is
frozen.

## Fixed occurrence set and order

At discovery freeze commit `35d392944fef43aeb4084e023bc1fa9470728fab`,
select every row of `data/candidates.csv` satisfying both
`consensus_decision=include` and `trigger_time_eligible=yes`. This rule selects
53 occurrences. Retain all 53 regardless of whether an auditable coordinate
or clock time is found.

Work in increasing `candidate_id` order. The review worksheet contains event
identity, catalog assertions, mechanics, and bibliographic provenance, but no
field from `data/reanalysis`. Neither temperature rank nor whether a coordinate
was used in the first pilot may determine effort, source choice, acceptance,
or review order.

## Coordinate target and assertions

The target is the initiating source scar or detachment zone. A deposit
centroid, tsunami gauge, dam, downstream impact, summit, glacier terminus, or
regional place label is not silently substituted. Store every checked
coordinate assertion in a long provenance table. Its fields include candidate
ID, latitude and longitude as published or digitized, geometry role, evidence
method, source URL or DOI, exact page/table/figure/map locator, verbatim label,
reviewer, and review status.

Allowed geometry roles are `initiating_source`, `source_area_centroid`,
`deposit`, `impact`, `named_feature`, `regional`, `unspecified`, and
`not_reported`. Only `initiating_source` and `source_area_centroid` may become
an accepted analysis coordinate. A published point described only as the
event location remains an `unspecified` assertion unless a figure, map, or
text establishes its source-scar meaning.

Evidence methods are `published_numeric`, `authoritative_gazetteer`,
`figure_digitized`, and `not_available`. Figure digitization is allowed only
when the source scar and georeferenced axes or control features are visible;
the audit records the digitization tool, control features, scale, and an
estimated horizontal uncertainty. Gazetteer coordinates may help locate a
figure but cannot alone establish the analysis coordinate.

For the accepted coordinate, report an explicit horizontal uncertainty in
metres when the source does. Otherwise use one registered conservative class:

- `le_100_m`: mapped scar or numeric source point supports at most 100 m;
- `le_1_km`: source zone is clear but the exact detachment point is not;
- `le_5_km`: only a bounded source sector is supportable;
- `gt_5_km_or_unknown`: insufficient for a unique local terrain or ERA5 cell.

Decimal places do not by themselves establish uncertainty. Select among
multiple source-coordinate assertions by event-specific primary evidence,
then authoritative event products, then the smallest documented uncertainty.
If equally ranked assertions conflict beyond their uncertainties, set the
summary status to `conflict` and retain both; do not average them.

## Onset target, intervals, and UTC conversion

The target is the earliest documented motion of the threshold-qualifying
source failure. Store every checked time assertion in a long provenance table,
including the verbatim string, described pulse, reported time zone or time
scale, source and exact locator, reviewer, and review status. Do not replace
failure onset with wave arrival, seismic detection at a distant station,
satellite acquisition, report time, or discovery time.

Represent an assertion as a half-open interval
`[onset_lower_utc, onset_upper_utc)`. A time reported to a second spans that
second; a time reported to a minute spans that minute. A day with a documented
civil time zone spans that local calendar day after UTC conversion. A clock
time stated as UTC, GPS, or another standard is converted with the published
scale and recorded conversion. Daylight-saving offsets must be verified for
the event date.

A local date with no documented time-zone basis is not converted using
longitude or a modern web time-zone guess. Its UTC bounds remain unresolved.
An earthquake origin time may define onset only when the event source states
that the audited failure was coseismic; otherwise it is a trigger assertion,
not a failure clock. Satellite brackets and multi-day ranges remain explicit
intervals and are not narrowed by narrative preference.

For a multi-pulse candidate, retain every pulse assertion. The summary onset
is the first pulse that the event reconstruction treats as part of the
threshold-qualifying source failure. If threshold support cannot be allocated
by pulse, summarize the full qualifying pulse interval rather than inventing
an event instant. Conflicting equally ranked clock assertions yield summary
status `conflict`.

## Source hierarchy and access

Use event-specific peer-reviewed reconstructions and their supplements first;
then authoritative geological, seismic, meteorological, or remote-sensing
agency products; then the structured discovery record. News and unsourced web
pages may locate primary evidence but cannot support an accepted analysis
value. An inaccessible cited source is recorded as `source_inaccessible`, not
reconstructed from a secondary paraphrase.

Record a stable URL or DOI, access date, and exact locator. When public source
files can legally be redistributed, store a checksum and source object path.
For copyrighted papers, store bibliographic and locator metadata rather than
the paper. Conflicting evidence is preserved even when consensus favors one
assertion.

## Independent review and consensus

One extractor records each assertion. A second reviewer independently checks
the cited locator, geometry or pulse interpretation, coordinate transcription,
and UTC arithmetic without seeing the extractor's acceptance recommendation.
Review states are `pending`, `agree`, and `disagree`. Summary states are
`accepted`, `conflict`, and `unresolved`.

Consensus is rule-based rather than a vote. A disagreement note must identify
the disputed assertion and the source passage or registered hierarchy that
resolves it. Controlled unresolved reasons are `not_reported`,
`source_inaccessible`, `geometry_ambiguous`, `time_basis_unknown`,
`pulse_allocation_unknown`, and `conflicting_primary_sources`.

## Checks fixed before population

Generate the empty audit keys mechanically from the frozen table. Automated
checks require exactly the 53 selected candidate IDs with no duplicates or
extras; preserve the catalog coordinate and date values byte for byte; enforce
latitude, longitude, interval, vocabulary, provenance, and reviewer-state
constraints; recompute UTC conversions from the recorded offset; and reject an
accepted summary without an agreed source assertion. Synthetic tests cover
positive and negative UTC offsets, daylight-saving conversion, leap days,
minute and second half-open intervals, interval conflicts, longitude range,
and uncertainty-class selection.

Before any later reanalysis extraction, hash the frozen candidate input, audit
tables, source manifest, protocol commit, and validator version. The audit
notebook may use a neutral geographic basemap but must not load or encode
temperature, glacier change, permafrost, or any pilot rank.

## Expected artifacts and summaries

Commit:

1. a 53-row summary table keyed by `candidate_id`;
2. long coordinate-assertion, time-assertion, and provenance tables;
3. a machine-checkable manifest with hashes and source access states;
4. validator tests; and
5. an executed notebook showing a climate-blind coordinate map, uncertainty,
   UTC precision, unresolved reasons, and completeness by discovery source.

Report old-versus-audited coordinate distances for the original 29 only after
the audit freezes, without reading new temperatures. Report the number of
events supporting an accepted source coordinate, an accepted UTC interval,
and both, including discovery-source-stratified rates. Completeness claims are
descriptive of the frozen discovery set, not estimates of global detection.

## Stopping and amendment rules

Stop and amend before population if the mechanical key set is not 53, the
review worksheet exposes reanalysis fields, or the schema cannot preserve
multiple assertions. Stop before accepting a digitized coordinate whose map
control does not support the registered uncertainty classes. Any change after
an audited coordinate or UTC interval is viewed must be logged below with its
reason and affected fields; result-contingent changes are prohibited.

## Amendment log

- 2026-08-30: after source review but before any new climate extraction, add a
  machine-linked `supporting_source_id` for the two earthquake-origin intervals
  whose event-specific coseismic statement and authoritative origin come from
  different sources. This changes provenance representation, not bounds.
- 2026-08-30: apply the preregistered multi-pulse rule to Aru-2 by retaining the
  full two-pulse interval; add the previously omitted Sedongpu 17/18 October
  alternative; and make the Mount Haast inclusive final second half-open.
  Affected fields are the named time assertions and the Aru-2 summary only.
- 2026-08-30: accept the Denali mainshock origin as a trigger-origin proxy for
  seven named avalanches after candidate-specific coseismic links were recovered
  and independently reviewed. Affected fields are those seven time assertions
  and summaries; no proxy is described as a measured detachment time.
- 2026-08-30: preserve the newly exposed two-second Paat primary-source conflict,
  withdraw Elliot Creek's catalog arrival as a source onset, and select Askja's
  more specific force-history source start. These changes follow source review
  and affect only the named assertions and summary fields.
- 2026-08-30: accept five independently reproduced Denali source-scar
  digitizations at the registered `le_1_km` class. Affected fields are the
  Black Rapids east, middle, and west and McGinnis north and south coordinate
  assertions and summaries; West Fork remains unresolved.
- 2026-08-30: an immutable-output review found that the EarthScope Pedersen
  time is a station arrival, not source onset. Add `onset_role` to distinguish
  `source_failure`, `trigger_proxy`, and `context_only` assertions; classify
  all time assertions; retain the Pedersen arrival as context; and select the
  independently reviewed USGS source-failure second. No exposure is read or
  changed. Affected fields are time-assertion roles and the Pedersen summary.

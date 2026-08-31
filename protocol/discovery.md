# Climate-blind event discovery protocol

Version 0.2. Eligibility rules were registered before screening on 30 August
2026; the reconciliation amendments listed below precede the inventory freeze.

## Estimand and separation from the seed catalog

This protocol constructs the sampling frame for later tests of whether large
alpine and fjord mass movements occupy unusual atmospheric or cryospheric
conditions. It does not estimate that association. The eight records in
`data/events.csv` developed the schema and hypotheses; they do not enter the
inference sample merely because they motivated the study. A record must be
rediscovered and pass the rules below.

Discovery and eligibility use event mechanics, size, mobility, setting, time,
location, and documentation. Search queries and screening fields do not use an
asserted warming cause or an event climate anomaly. Climate exposure is not
extracted until the candidate table and its search cutoff are frozen.

## Scope

- Occurrence window: 2000-01-01 through 2026-08-30 23:59 UTC.
- Source cutoff: public sources available by 2026-08-30 18:15:53
  America/Los_Angeles (2026-08-31 01:15:53 UTC), the final logged search time.
- Geography: global alpine terrain, glacierized source terrain, fjords, and
  alpine lakes. A named mountain, glacier, or fjord setting in the source is
  sufficient at screening; a terrain-mask check will follow before analysis.
- Source material: rock, glacier ice, or a documented rock--ice mixture.
- Process: rapid gravitational failure. Slow deformation without rapid failure
  is stored separately as a prospective case and is not part of this occurred-
  event inventory.

Snow avalanches without glacier-ice or rock failure, debris flows without a
documented initiating rock or glacier failure, submarine failures, volcanic
flank collapses, soil or loess slides, and mine or construction failures are
excluded. Earthquake-triggered rock or ice failures remain eligible because
trigger is not an exclusion rule.

## Operational geophysical threshold

An occurred event must have a documented source location and occurrence time
and meet at least one published threshold:

1. initial failed volume at least $10^6$ m3;
2. source-to-deposit travel at least 2 km; or
3. landslide-tsunami field runup at least 10 m.

Damage, fatalities, and infrastructure exposure do not determine inclusion.
A threshold estimate may be an observation or reconstruction, but a purely
hypothetical scenario is insufficient for an occurred event. A lower limit
equal to a threshold passes; an upper limit crossing a threshold is uncertain.

These thresholds are operational. They prioritize failures large enough to
have consistent regional or global documentation without selecting on social
consequence. They may be revised only before screening, in a committed protocol
change that explains the sensitivity of the candidate count.

## Discovery resources

Two structured catalogs form the initial frames:

1. the 354-record PANGAEA catalog of landslide-triggered tsunamis;
2. the 60-event High Mountain Asia rock and ice avalanche inventory on Zenodo.

The 51-event high-mountain process-chain review of Mani and colleagues is a
cross-check source. Its event descriptions are public, but automated access to
the linked spreadsheet returned HTTP 403 during this search. The inaccessible
spreadsheet is therefore not represented as an enumerated frame.

Every row in the occurrence window is considered from each frame before
material, setting, or threshold screening. Catalog cause fields are neither
imported nor used. Cause-blind web queries supplement regions and years not
covered by a structured frame, especially 2024--2026. Exact resources, queries,
execution times, result-page bounds, and reviewers are in
`data/discovery_searches.csv`. Multi-resource query suites have one recorded
batch execution time; every exact query in a batch is preserved verbatim in
`protocol/discovery-search-transcript.md`.

## Screening and reconciliation

Each candidate has two independent decisions. Reviewers see only identity,
time, location, setting, source material, threshold evidence, and provenance.
Allowed decisions are `include`, `exclude`, and `uncertain`. Decision reasons
are controlled: eligible; outside occurrence window or setting; excluded
material or process; below threshold; threshold, time, or location not
documented; duplicate; source inaccessible; or primary-source, taxonomy, or
setting review pending. An unassigned aggregate or downstream measurement is
stored as `threshold_quantity=not_documented`, not relabeled as source volume,
source-to-deposit travel, or field runup.

The consensus decision is not a majority vote. Disagreement requires a note
that identifies the disputed field and the source passage or registered rule
used to resolve it. Candidates sharing a source slope or repeat-failure site
receive one `event_group_id`. Shared triggers do not collapse distinct source
failures into one event: trigger, cascade, site, and common-tsunami dependence
are represented separately in `data/candidate_clusters.csv`. This separation
allows a later analysis to cluster uncertainty by earthquake, site, or cascade
without discarding individual failures.

Every structured-frame row that passes the cause-blind numeric prefilter has a
disposition. The many-to-many crosswalk in `data/candidate_provenance.csv`
links the 40 PANGAEA and 38 High Mountain Asia qualifying rows to candidate
records. The immutable downloads, checksums, source-row locators, and exact
qualifier manifest are in `data/source_frames`. Compound inventory rows are
expanded so that distinct source failures remain visible even when a row-level
size estimate cannot be allocated; those occurrences remain uncertain rather
than inheriting the aggregate threshold. Multiple pulses remain one candidate
only when the reconstruction treats them as stages of one source failure.

An included event with day-scale timing is `trigger_time_eligible=yes`.
Month-scale or satellite-bracketed timing can contribute to the site-level
preconditioning analysis but is `trigger_time_eligible=no`. This distinction
prevents imprecisely dated events from diluting a short-window weather test.

## Source hierarchy

Primary event reconstructions and authoritative agency records support final
threshold and timing fields. Inventory datasets support discovery but do not
replace their cited primary derivations. If only a secondary catalog is
available, the decision remains `uncertain` until the primary source is checked.
Conflicting values are retained in notes; screening uses the most conservative
relation that the primary source supports.

## Freeze and later amendments

The candidate inventory freezes when both screens, disagreement resolutions,
and the search log pass `make check` and the pull request commit is recorded.
No atmospheric, glacier-change, or permafrost exposure may be added before that
freeze. Later-discovered events enter a versioned prospective extension and do
not silently alter the original analysis set. Corrections to identity or source
values receive a documented amendment and a sensitivity analysis.

## Known coverage limitations

The structured catalogs have different purposes and regional biases. High
Mountain Asia has a dedicated avalanche inventory, whereas other ranges rely
more heavily on case literature. Tsunami catalogs overrepresent failures that
entered water; satellite-era studies overrepresent large, cloud-free scars;
and reporting increased through the study period. The later observation model
must retain discovery frame, publication year, timing precision, and sensor
coverage. This protocol improves traceability but does not make detection
complete or stationary.

## Pre-freeze amendment log

- 30 August 2026: set the source cutoff equal to the final logged search time
  in both the project timezone and UTC.
- 30 August 2026: added explicit frame-to-candidate provenance after an
  adversarial audit found qualifying rows without visible dispositions.
- 30 August 2026: separated source-site identity from common-trigger and
  cascade dependence, and split compound Iliamna and Morsar entries.
- 30 August 2026: retained exact-threshold upper limits and unallocated
  compound values as uncertain instead of treating them as below threshold.
- 30 August 2026: committed the exact downloaded frames and qualifier manifest;
  split the Siachen and Amney Machen compounds and retained the disputed 2021
  Hailuogou assertion explicitly.

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

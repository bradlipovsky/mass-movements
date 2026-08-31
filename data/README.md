# Event catalog

The catalog separates event identity, quantitative measurements, and causal
claims. This prevents a modeled quantity or an interpretation from being
mistaken for a direct observation.

`events.csv` contains one row per source failure or monitored unstable slope.
The two Aru collapses are separate events because they occurred on different
dates and had different precursor behavior. Barry Arm is retained as an
`active_slope`; its modeled tsunami is not an observed event.

`measurements.csv` contains one traceable number per row. Bounds and
uncertainties are blank when the source does not report them. The
`evidence_kind` field uses:

- `observation`: a published measurement or reconstruction;
- `preliminary_observation`: an agency value explicitly subject to revision;
- `model_output`: a result conditional on stated model assumptions.

`claims.csv` records process and attribution statements. The `claim_scope`
field distinguishes `process_chain`, `immediate_trigger`,
`climate_preconditioning`, `precursor`, and `catalog_reconciliation`.
`published_inference` preserves a source author's causal interpretation;
`project_interpretation` is an inference made in this catalog and must remain
explicitly labeled.

`evidence_strength` is assessed independently of claim type. `direct` denotes
geometry or timing seen in measurements; `strong` denotes a causal inference
supported by multiple quantitative observations; `moderate` denotes a
mechanically consistent inference with unresolved alternatives; `weak` denotes
a tentative or indirect relation; and `unresolved` denotes insufficient
evidence. These levels describe support within the cited event literature, not
formal attribution to anthropogenic forcing.

Source keys resolve to `latex/references.bib`. `source_locator` identifies the
abstract, section, figure, or dated agency finding used for the row. The
catalog is a seed, not a complete global inventory. Values for the 2026 Nepal
event are provisional and should be revisited when a peer-reviewed
reconstruction becomes available.

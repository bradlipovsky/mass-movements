# Scale-explicit equivalent steep-area provenance

These artifacts are post-outcome method-development diagnostics for the three
issue #11 windows. They are not a new holdout, regional samples, predicted
failures, or a basis for global scaling.

The real-window program was executed once at 2026-08-31T13:55:49Z from clean,
pushed commit `acec6401bfa02b20d375e03d3eb82910148edf90`:

```sh
.venv/bin/python scripts/scale_explicit_steep_area.py
```

That commit binds the pre-output protocol, exact-distance implementation,
synthetic tests, software versions, inherited-input hashes, and 326-line
pre-execution budget in `preoutput_freeze.json`. Two independent-review
findings---polygonal buffer distance at convex corners and zero phase-mean CV
handling---were corrected and re-frozen before this execution. No regional
equivalent-area value had then been read or calculated.

The analysis reuses only `data/area_convergence/` inputs. Their source
identities, access records, coverage, DEM replay, and hashes remain in that
directory's `source_manifest.json`, `freeze_manifest.json`, and
`PROVENANCE.md`; no scientific source was retrieved or changed for issue #13.

The program wrote 30 rows to `equivalent_area_long.csv` and six rows to
`diagnostics.csv`. All areas are finite and nonnegative; neither table contains
a pass column, structural zero, or positive variant with a zero reference.
The four-phase CV range is 0.000115--0.003474 and the 90 m departure range is
0.026226--0.134349. Paired departure is smaller than the frozen hard-threshold
diagnostic in five of six cases and larger for Scandinavia glacier proximity
(0.007163 to 0.036904). This comparison describes the registered composite;
it does not identify a responsible operation or validate the method.

The executed notebook reads only the two derived tables and creates the PDF
and PNG figure. The manuscript PDF was compiled with `latexmk -pdf -cd
latex/main.tex`. A final machine-readable manifest is added only after
independent review of the committed result state.

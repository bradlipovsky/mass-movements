# Hazardous alpine mass movements

This project tests whether recent rock, ice, and mixed-material collapses in
high mountains and fjords are systematically associated with a warming
climate. The central difficulty is attribution: long-term thermal
preconditioning must be distinguished from immediate meteorological triggers
and from non-climatic controls such as geometry and material structure.

The work proceeds in three stages:

1. Build a literature catalog that preserves observations, uncertainty, and
   published interpretations.
2. Compare event histories with atmospheric reanalysis, including topographic
   downscaling where global products are inadequate.
3. Apply the inferred conditions to glaciers and permafrost terrain to assess
   global susceptibility.

The protocol manuscript is in `latex/`, the frozen discovery inventory is in
`data/candidates.csv`, and the registered ERA5 pilot is in
`notebooks/era5_pilot.ipynb`. The convenience seed demonstrates provenance and
mechanics fields; it is not an inference sample. Run `make check` to validate
the catalog and `make` to compile `latex/main.pdf`.

The climate-blind source-coordinate and UTC-onset audit is registered in
`protocol/source-time-audit.md`; its separate analysis-layer tables are in
`data/event_audit/`. Run `make check-event-audit` for its synthetic and
artifact tests. Run `make notebook-event-audit` to re-execute its climate-blind
map and completeness summaries. The frozen discovery table is not amended by
this audit.

The point-history pilot uses a modern isolated environment because its public
ERA5 source is an Icechunk/Zarr store:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-reanalysis.txt
make check-reanalysis
```

`make reanalysis` repeats the registered remote extraction only while the
public store remains at the frozen snapshot. The retrieval manifest records
that snapshot and hashes every committed derived table. `make
notebook-reanalysis` re-executes the committed notebook from the derived
tables and regenerates its figures. `make artifacts-reanalysis` runs the
remote extraction, notebook execution, and PDF build in that order. Each
target accepts `PYTHON_REANALYSIS=/path/to/venv/bin/python` when the virtual
environment is not named `.venv`.

Project decisions and review are tracked in
[GitHub issues](https://github.com/bradlipovsky/mass-movements/issues).

The held-out susceptible-area convergence test is registered in
`protocol/susceptible-area-convergence.md`. Run `make
artifacts-area-convergence` to regenerate its 225-row area table, six fixed
window decisions, executed notebook, figure, tests, and manuscript. Both
terrain screens presently fail the registered all-window resolution criterion;
the repository therefore does not extrapolate them to global incidence or
hazard.

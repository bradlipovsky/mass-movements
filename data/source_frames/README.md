# Immutable discovery frames

These files preserve the exact source bytes used for the registered screen.
They are not analysis-ready derivatives, and their trigger or cause fields
must not be imported into the candidate table.

- `pangaea_ltt_979839.tsv`: PANGAEA dataset
  [10.1594/PANGAEA.979839](https://doi.org/10.1594/PANGAEA.979839), downloaded
  30 August 2026. SHA-256
  `c3fe591a5fffa9b1124dd50c401092c99f953512e5428064251fff2f1e78ad57`.
- `hma_rock_ice_10458200.xlsx`: High Mountain Asia supplementary inventory
  [10.5281/zenodo.10458200](https://doi.org/10.5281/zenodo.10458200), downloaded
  30 August 2026. SHA-256
  `96361f7490d9684d874f6a38273050fbe654e1f1dd11ac078ed66679d3c94151`.

`frame_qualifiers.csv` records the exact source row and cause-blind numeric
prefilter basis for each of the 40 and 38 qualifying rows. The validator checks
the source-file hashes and requires exact equality between this manifest and
`candidate_provenance.csv`.

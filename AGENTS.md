# Project instructions

## Scientific and writing style

- Follow `docs/brad-lipovsky-academic-style-guide.md` in manuscripts, issues,
  pull requests, documentation, and code comments.
- Use mechanics-first language. Separate observation, calculation, published
  inference, and project interpretation.
- Prefer quantitative scales and bounded claims to generic statements about
  hazard or climate change.
- Define necessary terms and avoid new jargon when direct continuum-mechanics
  language is sufficient.

## Coding philosophy

- This repository contains research code for understanding physics, not a
  production service. Keep code simple, direct, and readable.
- Prefer functions and plain data over custom classes.
- Before coding, state the physical question, expected figure or notebook, and
  approximate amount of handwritten code.
- Do not add more than 500 lines of handwritten source and tests in one pull
  request without explicit approval. Generated notebook outputs, manuscript
  PDFs, and analysis results are excluded.
- Do not introduce dependencies without explaining the scientific need in the
  issue and pull request.
- Any pull request claiming a physical or numerical result must include an
  executed notebook, figure, or concise quantitative comparison.
- Tests should focus on equations, conservation, limiting cases, and
  time/space convergence when those checks apply.
- If the implementation becomes larger or harder to understand than the
  physical idea being tested, stop and simplify.

## Research records

- Trace each catalog value and scientific claim to a primary paper, data
  product, or authoritative agency source.
- Preserve uncertainty and source disagreements rather than silently selecting
  one estimate.
- Commit notebooks with figures and outputs embedded.
- Compile and commit the manuscript PDF whenever its source changes materially.

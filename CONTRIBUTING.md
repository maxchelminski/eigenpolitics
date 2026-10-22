# Contributing

Eigenpolitics combines an archived Master's thesis with a maintained research companion. Contributions should preserve the distinction between the submitted work and newly computed results.

## Development

Follow [the development guide](docs/DEVELOPMENT.md) to run the site and data pipeline. Open an issue or pull request describing the question, the behavior you observed, and the proposed change. Include the Congress number and the data retrieval timestamp when discussing a result.

For interface changes, include a desktop and mobile screenshot. For analytical changes, explain the mathematical definition, why it is appropriate, and how the results change on a small, inspectable example.

Before submitting:

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts eigenpolitics
node --check site/app.js
```

The JavaScript check requires Node.js; running the site itself does not. For interface changes, also follow [the browser verification instructions](docs/DEVELOPMENT.md) to install the optional Playwright tooling with `npm ci`, run the browser checks, and regenerate screenshots when the visible result changes.

## Research conventions

- Preserve `2026 Master's Thesis.pdf`, `2026 Master's Thesis.docx`, `senate_clean.py`, and `senatelinearalgebra.py` as original artifacts. Make new work in `scripts/`, `site/`, or a separately named analysis.
- Document vote encoding, missing-vote treatment, graph construction, normalization, and eigenvector orientation when changing the method.
- Do not label a refreshed calculation an exact thesis replication. Historical input files and execution details must support that claim.
- Include upstream sources and retrieval information for new datasets. Do not infer ideology, motive, or causation from a visualization alone.
- Keep generated public data in `site/data/`; keep downloaded source caches, virtual environments, and local credentials out of Git.
- Add focused regression tests for changes to mathematical behavior or data validation.

## Rights and attribution

Original software and project documentation are licensed under the [MIT License](LICENSE). The thesis manuscripts and website PDF are excluded from that grant and retain their reserved rights. Third-party data and dependencies retain their own rights and attribution requirements; see [Licensing and rights](LICENSING.md) for the complete scope. Only contribute material you have the right to provide under the applicable license.

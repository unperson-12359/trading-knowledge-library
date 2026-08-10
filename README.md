# Pakupai Trading Knowledge Library

A machine-readable library of 1,500 trading concepts across 29 domains. This
is Phase 1 of Pakupai: the knowledge foundation that later AI skills,
workflows, research playbooks, and products build on.

## What this is

- `concepts/*.json` is the single source of truth.
- Each entry includes definitions, mechanics, failure modes, misconceptions,
  examples, relationships, and citations.
- `exports/` and `docs/` are generated and must not be edited by hand.
- `sources/master_v1.txt` is the original imported catalog and remains a
  read-only historical reference.
- `collections/core-perps.json` fixes the 50-concept generic-perpetual core;
  each core concept has at least two citations and an explicit regime note.

## AI disclosure

This project is built and maintained with AI systems. AI is used to research,
draft, organize, and update the material. The content may contain errors or
omissions; inspect the cited sources and verify critical information
independently. Nothing here is financial advice, a recommendation, or evidence
that a trading setup is profitable.

## Source policy

Prefer sources in this order:

1. Regulators, central banks, exchanges, clearing organizations, protocol
   specifications, and original technical documentation.
2. Original academic papers and canonical peer-reviewed research.
3. Recognized professional standards and original indicator publications.
4. High-quality secondary sources when direct sources are unavailable.

A citation supports a definition or mechanism. It does not establish that a
pattern, indicator, or strategy is profitable.

## Layout

```text
concepts/<domain>.json   one file per domain, array of entry objects
collections/             focused operational concept collections
regimes/taxonomy.json    controlled market-state vocabulary
playbooks/                five untested research-hypothesis templates
research/specs/           frozen machine-executable research contracts
research/datasets/        immutable normalized market-data snapshots
schemas/                  machine-readable structured-data schemas
scripts/status.py       validate the complete catalog
scripts/export_master.py generate exports/master_v2.txt
scripts/build_site.py   generate the GitHub Pages site in docs/
exports/                 generated text output
docs/                    generated website
sources/                 read-only import reference
```

The generated regime API is available at `docs/api/v1/regimes.json` (and at
the matching path on GitHub Pages). Regime tags are descriptive research
context, not forecasts, signals, or evidence of expected return.

Five generic perpetual-futures playbooks are generated into `docs/playbooks/`
and `docs/api/v1/playbooks.json`. Every playbook is explicitly untested and
requires caller-supplied risk constraints plus realistic execution, fee,
impact, and funding models before evaluation.

## Static query API

The dependency-free browser query is generated at `docs/query.html`. It filters
concepts and playbooks by text, record type, domain, core membership, required
input, and regime; filters are retained in the URL for sharing.

Versioned JSON endpoints live in `docs/api/v1/`:

- `manifest.json` describes counts, endpoints, and relationship resolution.
- `concepts.json` provides all public concept fields, stable URLs, resolved
  relationship IDs, core membership, and core regime annotations.
- `core-perps.json`, `regimes.json`, and `playbooks.json` expose the focused
  collection and its research layer.
- `research-specs.json` exposes frozen executable rules separately from the
  conceptual playbooks.
- `dataset-manifests.json` and `datasets/<dataset-id>/` expose hashed,
  AI-readable market-data snapshots used by published research.

Unambiguous relationship names and aliases become internal links. Ambiguous or
unresolved terms remain visible as plain text and are reported in the manifest.

## Workflow

Edit canonical JSON, then validate and regenerate outputs:

```bash
python scripts/status.py
python scripts/export_master.py
python scripts/build_site.py
python scripts/research.py fetch
```

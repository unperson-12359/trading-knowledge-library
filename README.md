# Pakupai Trading Knowledge Library

A machine-readable library of 1,438 canonical trading concepts across 29 domains. This
is the canonical knowledge foundation for Pakupai's AI skills, workflows,
research playbooks, and future trading IDE.

## What this is

- `concepts/*.json` is the single source of truth.
- Each entry includes definitions, mechanics, failure modes, misconceptions,
  examples, relationships, and citations.
- `exports/` and `docs/` are generated and must not be edited by hand.
- `sources/master_v1.txt` is the original imported catalog and remains a
  read-only historical reference.
- `collections/core-perps.json` fixes the 50-concept generic-perpetual core;
  each core concept has at least two citations and an explicit regime note.
- `.agents/skills/tkl-concept-router/` is the one automatically discoverable
  repository skill. It searches the catalog instead of loading 1,438 skill
  descriptions into every model context.
- `skills/concepts/` contains individually installable, self-contained concept
  packages. Each has human-readable instructions and JSON evidence tied to the
  canonical concept by SHA-256.

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
research/results/         deterministic metrics and headline trade logs
skills/architecture.json  machine-readable router/catalog design decision
skills/manifest.json      generated concept-skill catalog
skills/concepts/          organized installable concept packages by domain
aliases/                  compact machine-readable compatibility mappings
.agents/skills/            small auto-discovered repository router
schemas/                  machine-readable structured-data schemas
scripts/status.py       validate the complete catalog
scripts/build_skills.py build or validate the complete skill catalog
scripts/export_master.py generate exports/master_v2.txt
scripts/build_site.py   generate the GitHub Pages site in docs/
exports/                 generated text output
docs/                    generated website
sources/                 read-only import reference
audits/                  committed machine-readable evidence-health ledger
relationships/           typed external relationship vocabulary
```

The generated regime API is available at `docs/api/v1/regimes.json` (and at
the matching path on GitHub Pages). Regime tags are descriptive research
context, not forecasts, signals, or evidence of expected return.

Five generic perpetual-futures playbooks are generated into `docs/playbooks/`
and `docs/api/v1/playbooks.json`. Every playbook is explicitly untested and
requires caller-supplied risk constraints plus realistic execution, fee,
impact, and funding models before evaluation.

## Consolidated library and static API

The dependency-free public catalog is generated at `docs/index.html`. It
filters all 1,438 canonical concepts by text, domain, core membership, regime, and first
letter, with sorting and pagination retained in the URL for sharing. The former
A-Z, structured-query, skill-catalog, and domain pages are compatibility routes
that forward visitors to this catalog or directly to the relevant unified page.

Versioned JSON endpoints live in `docs/api/v1/`:

- `manifest.json` describes counts, endpoints, and relationship resolution.
- `concepts.json` provides all public concept fields, unified canonical URLs,
  legacy compatibility URLs, resolved relationship IDs, core membership, and
  core regime annotations.
- `core-perps.json`, `regimes.json`, and `playbooks.json` expose the focused
  collection and its research layer.
- `research-specs.json` exposes frozen executable rules separately from the
  conceptual playbooks.
- `dataset-manifests.json` and `datasets/<dataset-id>/` expose hashed,
  AI-readable market-data snapshots used by published research.
- `research-results.json` and `results/<run-id>/` expose deterministic study
  metrics and the headline-scenario trade log. The human-readable reports in
  `docs/research/` are generated from these same JSON records.
- `skills.json`, `concept-aliases.json`, and `skill-architecture.json` expose
  the installable skill catalog, compatibility mappings, and design decision.
  Individual profiles live under `skills/<skill-name>.json`.
- `citation-audit.json`, `source-policy.json`, and `relationship-vocabulary.json`
  expose citation accessibility, source-quality policy, and typed external
  relationship terms for automated consumers.

The former 2-period through 64-period simple-return concepts resolve to one
`N-period simple return` concept with an explicit `periods` parameter. Alias
records preserve old IDs, skill names, and URLs without counting them as
canonical concepts.

Every concept has one unified page under `docs/skills/<skill-name>/`. Its
default tab is the human-readable trading concept; adjacent tabs switch in
place to copyable usage, `SKILL.md`, `skill.json`, canonical `concept.json`, the
packaged reference, and `agents/openai.yaml`. GitHub remains the canonical
package source.

Unambiguous relationship names and aliases become internal links. Other useful
terms remain visible and are emitted as typed `external-term` references through
the relationship vocabulary; they are not silently presented as missing links.

## Workflow

Edit canonical JSON, then validate and regenerate outputs:

```bash
python scripts/status.py
python scripts/build_skills.py build
python scripts/build_skills.py validate
python scripts/export_master.py
python scripts/build_site.py
python scripts/audit_citations.py
python scripts/research.py fetch
python scripts/research.py run
```

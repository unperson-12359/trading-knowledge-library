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
scripts/status.py       validate the complete catalog
scripts/export_master.py generate exports/master_v2.txt
scripts/build_site.py   generate the GitHub Pages site in docs/
exports/                 generated text output
docs/                    generated website
sources/                 read-only import reference
```

## Workflow

Edit canonical JSON, then validate and regenerate outputs:

```bash
python scripts/status.py
python scripts/export_master.py
python scripts/build_site.py
```

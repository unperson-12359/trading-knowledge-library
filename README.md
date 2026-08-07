# Pakupai Trading Knowledge Library

A machine-readable, source-verified knowledge base of trading concepts. This is
Phase 1 of Pakupai: the knowledge foundation that every later layer (AI skills,
workflows, product) builds on.

## What this is

- 1,500 trading concepts across 29 domains, stored as structured JSON in `concepts/`.
- `concepts/*.json` is the **single source of truth**. Text exports in `exports/`
  are generated and never edited by hand.
- `sources/master_v1.txt` is the original imported catalog (read-only reference).

## Trust levels

| Level | Meaning |
|---|---|
| `candidate` | Concept identified, not researched. |
| `provisional` | Working definition; exact citation still required. |
| `reviewed` | Definition checked against an authoritative source with an exact citation attached. |
| `trusted` | Exact source + independent/human review record. **Not granted to AI-generated content alone.** |
| `disputed` | Competing definitions or schools explicitly represented. |

## Source policy (preferred order)

1. Regulators, central banks, exchanges, clearing organizations, official
   protocol specifications, original technical documentation
   (SEC, CFTC, CME, BIS, OCC, FINRA, Federal Reserve, U.S. Treasury, NFA, FSB,
   exchange rulebooks, blockchain protocol specs).
2. Original academic papers and canonical peer-reviewed research.
3. Recognized professional standards and original indicator publications.
4. High-quality secondary sources only when primary sources are unavailable.

A source is evidence for a **definition**, not proof that a pattern, indicator,
or strategy is profitable.

## Layout

```
concepts/<domain>.json   one file per domain, array of entry objects
scripts/import_master.py master_v1.txt -> concepts/*.json (already run)
scripts/export_master.py concepts/*.json -> exports/master_v2.txt
exports/                 generated outputs
sources/                 read-only import references
```

## Workflow

Edit JSON (usually via a verification pass), then regenerate the export:

```bash
python scripts/export_master.py
```

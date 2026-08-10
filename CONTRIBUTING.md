# Contributing

## AI-assisted workflow

This project is built and maintained with AI systems. AI-assisted changes must
remain inspectable through exact citations, small commits, validation, and Git
history. AI output is not evidence that a trading claim is correct or
profitable.

## Content batches

Work in small, recoverable batches:

- One batch contains no more than 50 entries; source-deepening work uses batches
  of 10.
- Read `SCHEMA.md`, this file, and the assigned concept files before editing.
- Write JSON atomically through a temporary file and rename it over the target.
- Never delete or drop entries. Every `master_index` from 1 through 1500 must
  remain present exactly once.
- Validate the complete library after each batch with `python scripts/status.py`.

## Source rules

- Never invent URLs or citations. Fetch every new citation before adding it.
- Prefer regulators, exchanges, protocol specifications, original technical
  documentation, and canonical research.
- Use multiple venue specifications for generic perpetual-futures mechanics so
  a venue-specific convention is not presented as universal.
- A citation supports a definition or mechanism, not profitability.

## Generated files

- Never edit `exports/` or `docs/` by hand.
- Never edit `sources/master_v1.txt`; it is an immutable import reference.
- After canonical changes, run:

```bash
python scripts/status.py
python scripts/export_master.py
python scripts/build_site.py
```

Commit and publish only after all three commands succeed.

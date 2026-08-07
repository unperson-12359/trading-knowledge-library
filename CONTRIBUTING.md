# Contributing / Review Process

## Promoting an entry

1. **Candidate → Provisional**: a real working definition is written.
2. **Provisional → Reviewed**: definition verified against an authoritative
   source; at least one exact citation (`source`, `url`, `section`, `accessed`)
   is attached; `intuition`, `mechanics`, `failure_modes`, `misconceptions`,
   and `example` are filled.
3. **Reviewed → Trusted**: a human or independent reviewer confirms the
   definition and citation, and is recorded in `reviewed_by` / `review_date`.
4. **Any → Disputed**: when authoritative sources or schools of thought
   genuinely disagree; both positions are recorded in `review_note`.

## Verification passes

Work is organized in **small batches, one agent at a time**:

- **ONE AGENT → ONE BATCH (≤ 50 entries) → VALIDATE THAT BATCH → STOP.**
  Never run many verification agents in parallel — a quota cutoff strands
  them mid-write and destroys work (this happened: 2 files corrupted,
  3 files truncated, 259 entries lost and had to be restored).
- A batch is a whole domain file, or a master_index sub-range if the domain
  has more than 50 unverified entries.
- A batch agent reads only: SCHEMA.md, CONTRIBUTING.md, and its assigned
  concept file. It does not read other domains or previously completed files.

## Atomic incremental writes (mandatory)

- Write to `<file>.json.tmp`, then rename over `<file>.json`. Never write the
  JSON file in place — a kill mid-write must never corrupt existing work.
- Flush after every ~10 completed entries, not once at the end. A cutoff may
  then lose at most ~10 entries of new work and zero existing work.
- Never delete or drop entries. Only update fields of existing entries. Every
  `master_index` 1–1500 must remain present exactly once.
- After the final flush, validate: file parses as JSON, entry count unchanged,
  `python scripts/status.py` shows the batch's entries as reviewed.

## Hard rules

- Never invent URLs or citations. Every citation URL must have been fetched
  during review.
- Never edit `exports/` by hand; run `python scripts/export_master.py`.
- Never edit `sources/master_v1.txt`.
- Definitions describe what a concept **is**, not whether it is profitable.
  Profitability claims require reproducible evidence, stated assumptions,
  costs, and out-of-sample evaluation — and belong in strategy research,
  not in concept definitions.

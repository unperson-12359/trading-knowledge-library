# Entry Schema

## Concept fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | `<domain-slug>/<name-slug>`, unique across the library |
| `name` | string | yes | canonical name |
| `aliases` | string[] | yes | alternative names and abbreviations; may be empty |
| `domain` | string | yes | one of the 29 canonical domains |
| `definition` | string | yes | precise description; never a placeholder |
| `intuition` | string | yes | plain-language explanation |
| `mechanics` | string | yes | how it works or is computed/applied |
| `formula` | string | no | canonical formula with variable meanings |
| `relationships` | string[] | yes | related or parent/child concept names; may be empty |
| `failure_modes` | string | yes | when the concept misleads or breaks down |
| `misconceptions` | string | yes | common wrong beliefs about it |
| `example` | string | yes | short concrete worked example |
| `citations` | object[] | yes | one or more `{source, url, section, accessed}` objects |
| `source_hint` | string | yes | import-time source family; not exported by the public query API |
| `master_index` | number | yes | position in the original 1,500-concept master |

The catalog intentionally carries no review, trust, or provenance label per
entry. Citations are retained so readers can inspect source material directly.
The project-wide AI disclosure is documented in the README and on the generated
About & Methodology page.

## Core collection annotations

`collections/core-perps.json` contains exactly 50 concept IDs. Its
`annotations` object must cover those same IDs exactly. Each annotation has a
non-empty `regime_relevance` array of controlled tags and a concise
`behavior_note` explaining why the concept matters in those states.

Valid tags come only from `regimes/taxonomy.json` and use the form
`<dimension>.<state>`. The controlled dimensions are trend, volatility,
liquidity, and positioning. These labels describe observed context; they do not
claim predictive power or profitability.

## Research playbooks

Files in `playbooks/` conform to `schemas/playbook.schema.json`. They bind core
concepts into testable 15-minute generic-perpetual research configurations with
1-hour and 4-hour context, explicit data requirements, parameters, long/short
conditions, invalidation, exits, regime context, costs, risk constraints,
failure modes, and chronological validation plans. Their classification and
warning are fixed: they are untested hypotheses, not recommendations or proof
of profitability.

## Public API projection

`docs/api/v1/concepts.json` is generated from canonical concepts. It omits the
import-only `source_hint` and `master_index` fields and adds `type`, `url`,
`core`, `regime_annotation`, and `relationship_ids`. A relationship ID is
included only when its name or alias resolves to exactly one concept; the
original relationship text is always preserved.

## Executable research contracts

Conceptual playbooks remain descriptive research hypotheses. Files in
`research/specs/` are separate frozen contracts that turn one playbook into
deterministic data, signal, execution, cost, and evaluation rules. Dataset
manifests, trade logs, and research results each have their own JSON Schema so
AI consumers can distinguish an idea, a runnable specification, its evidence,
and its reported output.

`research/results/<run-id>/result.json` contains the frozen spec and dataset
hashes, classification, cost scenarios, aggregate and sliced metrics, data
quality, and warnings. Its sibling `trades.json` contains the headline-cost
scenario's event-level trades and cost decomposition. Generated HTML reports
are projections of these JSON records, never the canonical evidence.

## Concept skill packages

`schemas/concept-skill.schema.json` defines each package's machine-readable
`skill.json`: identity, trigger phrases, supported intents, context needs,
workflow, constraints, output contract, batch, canonical source/hash, and
resolved related concept IDs. `references/concept.json` is a self-contained
projection of canonical knowledge, not a second editable source of truth.

The package `SKILL.md` contains only focused usage instructions and its YAML
frontmatter contains only `name` and `description`. `agents/openai.yaml` keeps
individual catalog packages out of implicit discovery. The repository exposes
one implicit router at `.agents/skills/tkl-concept-router/`; this progressive
disclosure design prevents 1,500 descriptions from consuming the host's skill
metadata budget.

`skills/progress.json`, `skills/manifest.json`, and every file in
`skills/batches/` are machine-readable rollout records. Generation order is
the 50 core perpetual-futures concepts by `master_index`, followed by all
remaining concepts by `master_index`, in exact batches of 20.

## Rules

- Every entry must contain the full explanatory fields and at least one valid
  HTTP(S) citation with a source, section, and ISO access date.
- Never invent URLs or citations.
- Technical-analysis patterns are analytical frameworks or hypotheses, never
  proven predictive laws.
- Definitions describe what a concept is; strategy profitability belongs in
  reproducible research with costs and out-of-sample evidence.
- Placeholder text such as "A trading concept within X..." is invalid.

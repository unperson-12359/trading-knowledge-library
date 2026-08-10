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

## Rules

- Every entry must contain the full explanatory fields and at least one valid
  HTTP(S) citation with a source, section, and ISO access date.
- Never invent URLs or citations.
- Technical-analysis patterns are analytical frameworks or hypotheses, never
  proven predictive laws.
- Definitions describe what a concept is; strategy profitability belongs in
  reproducible research with costs and out-of-sample evidence.
- Placeholder text such as "A trading concept within X..." is invalid.

# Entry Schema

## v1 fields (present in every entry now)

| Field | Type | Required for `reviewed` | Notes |
|---|---|---|---|
| `id` | string | yes | `<domain-slug>/<name-slug>`, unique across the library |
| `name` | string | yes | canonical name |
| `aliases` | string[] | no | alternative names, abbreviations |
| `domain` | string | yes | one of the 29 canonical domains |
| `definition` | string | yes | precise, source-grounded; never a placeholder |
| `intuition` | string | yes | plain-language explanation |
| `mechanics` | string | yes | how it works / how it is computed or applied |
| `formula` | string | if applicable | canonical formula with variable meanings |
| `relationships` | string[] | no | related or parent/child concept names |
| `failure_modes` | string | yes | when the concept misleads or breaks down |
| `misconceptions` | string | yes | common wrong beliefs about it |
| `example` | string | yes | short concrete worked example |
| `citations` | object[] | yes (>= 1) | `{source, url, section, accessed}`; URL must be real and fetched |
| `source_hint` | string | no | source family noted at import; hint only, not a citation |
| `status` | string | yes | `candidate` / `provisional` / `reviewed` / `trusted` / `disputed` |
| `reviewed_by` | string | yes | who/what performed the review |
| `review_date` | string | yes | ISO date |
| `review_note` | string | no | caveats, disagreements, gaps |
| `master_index` | number | yes | position in the original 1,500-concept master |

## Full target schema (later passes — documented, not yet populated)

Aliases; domain and subdomain; definition; plain-language intuition; purpose;
mechanics; inputs; outputs; formulas; variable definitions; assumptions;
preconditions; relationships; confused concepts; trading implications; valid
uses; invalid uses; failure modes; misconceptions; worked example;
counterexample; asset applicability; timeframe applicability; data
requirements; test questions; machine-readable tags; exact citations; trust
status; reviewer; review date; version history.

## Rules

- No entry may be labeled `reviewed` without at least one real citation that
  was actually fetched during review.
- No entry may be labeled `trusted` without a human or independent review
  record. AI-generated content alone never reaches `trusted`.
- Technical-analysis patterns are analytical frameworks or hypotheses, never
  proven predictive laws. Definitions must say so where relevant.
- Placeholder text ("A trading concept within X…") is never acceptable in a
  final definition.

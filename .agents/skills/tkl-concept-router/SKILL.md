---
name: tkl-concept-router
description: Find and apply concepts from the Pakupai Trading Knowledge Library. Use for trading definitions, comparisons, setup analysis, market-mechanics questions, and misconception diagnosis when the answer should be grounded in the repository's structured concept catalog.
---

# Trading Knowledge Library Router

Use the repository catalog as evidence for research and decision support. Do not treat a retrieved concept as a trade signal.

## Route the request

1. Identify the user's intent: explain, compare, apply, or diagnose a misconception.
2. Run `python scripts/search.py "<query>" --limit 5` from this skill directory. Add `--core-only` for perpetual-futures workflow questions when appropriate. The router resolves retired identifiers and binds numbered requests such as “20-period simple return” to the canonical N-period skill with `periods=20`.
3. Select at most three concepts whose definitions and mechanics directly address the request. If the top matches represent materially different meanings, state the ambiguity before continuing.
4. Read each selected package's `skill.json`, `SKILL.md`, and `references/concept.json`. Treat `references/concept.json` as a generated projection; its `canonical_sha256` must match the package profile.
5. Apply the selected concept workflows. Keep sourced facts, analytical inferences, and missing live context visibly separate.
6. Cite the sources carried in each concept reference and name the concept IDs used.

## Answer contract

Include the relevant concept, the practical implication, important failure modes, common misconceptions, and unresolved context. For application questions, explain what observations would support or weaken the interpretation. Return JSON when requested, following `references/response-contract.json`.

Never invent prices, positions, venue rules, or other live inputs. Never promise profitability, place orders, or present educational analysis as personalized financial advice.

## Catalog locations

- Local manifest: `../../../skills/manifest.json`
- Compatibility aliases: `../../../aliases/concept-aliases.json`
- Concept packages: `../../../skills/concepts/`
- Public catalog fallback: `https://unperson-12359.github.io/trading-knowledge-library/api/v1/skills.json`

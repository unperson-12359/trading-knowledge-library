# Implementation Roadmap

This file records resumable production checkpoints for the AI-native trading
knowledge rollout.

| Checkpoint | State |
|---|---|
| Remove provenance metadata and add AI disclosure | Complete |
| Build and source-audit the 50-concept core | Complete |
| Add regime taxonomy and core annotations | Complete |
| Add five generic-perpetual research playbooks | Complete |
| Add structured query/API and relationship links | Complete |

## Phase 2: Executable research

| Checkpoint | State |
|---|---|
| Add research schemas and frozen ATR-breakout specification | Complete |
| Add Hyperliquid adapter and immutable BTC/ETH dataset snapshot | Complete |
| Add deterministic engine and canonical research results | Complete |
| Generate report/API and deploy the completed research slice | Complete |

Every completed checkpoint is validated, committed to `main`, pushed, and
verified on GitHub Pages before the next checkpoint begins.

## Phase 3: GitHub-first concept skills

| Checkpoint | State |
|---|---|
| Research and document the router-plus-catalog architecture | Complete |
| Add router, schemas, generator, validation, API, and review catalog | Complete |
| Generate the complete GitHub-first concept-skill catalog | Complete |
| Consolidate public browsing into one catalog and unified concept pages | Complete |
| Consolidate numbered simple returns into one parameterized concept | Complete (1,438 canonical + 63 aliases) |

The authoritative catalog is `skills/manifest.json`, generated from canonical
concept JSON. Compatibility aliases preserve retired identifiers without
duplicating concept or skill packages.

## Core source-audit batches

| Batch | Focus | State |
|---|---|---|
| A | Contract foundation | Complete |
| B | Funding and liquidation | Complete |
| C | Execution and microstructure | Complete |
| D | Signals and context | Complete |
| E | Risk and research | Complete |

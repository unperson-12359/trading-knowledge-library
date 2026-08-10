"""Validate and summarize the trading knowledge library.

Usage: python scripts/status.py

The command exits non-zero when the catalog is structurally incomplete,
contains a placeholder, lacks required content, or has malformed citations.
"""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

try:
    from build_skills import validate_catalog
except ModuleNotFoundError:  # allows unit tests to import scripts.status as a package
    from scripts.build_skills import validate_catalog

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_CONCEPT_COUNT = 1438
PLACEHOLDER = "A trading concept within"
REQUIRED_TEXT = (
    "id", "name", "domain", "definition", "intuition", "mechanics",
    "failure_modes", "misconceptions", "example",
)
REQUIRED_LISTS = ("aliases", "relationships", "citations")
REQUIRED_CITATION = ("source", "url", "section", "accessed")
REMOVED_PROVENANCE_FIELDS = {
    "status", "reviewed_by", "review_date", "review_note", "source_hint",
}
EXPECTED_REGIME_DIMENSIONS = {
    "trend": {"uptrend", "downtrend", "range", "transition"},
    "volatility": {"compressed", "normal", "expanded", "shock"},
    "liquidity": {"deep", "normal", "thin", "dislocated"},
    "positioning": {"balanced", "long-crowded", "short-crowded", "deleveraging"},
}
PLAYBOOK_WARNING = (
    "Untested research hypothesis. Not financial advice, a recommendation, "
    "or evidence of profitability."
)
PLAYBOOK_REQUIRED = {
    "id", "title", "version", "classification", "market_type",
    "signal_timeframe", "context_timeframes", "hypothesis", "concept_ids",
    "required_data", "parameters", "entry_conditions", "invalidation",
    "exit_logic", "regime_profile", "cost_model", "risk_constraints",
    "failure_modes", "validation_plan", "warning",
}
RESEARCH_SPEC_REQUIRED = {
    "$schema", "id", "version", "classification", "playbook_id", "market_type",
    "data_source", "assets", "timeframes", "indicators", "signal_rules",
    "execution", "costs", "evaluation", "warning",
}
RESEARCH_WARNING = (
    "Preliminary limited-window research. Not validated, not financial advice, "
    "and not evidence of profitability."
)


def _valid_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def entry_errors(entry):
    errors = []
    forbidden = REMOVED_PROVENANCE_FIELDS.intersection(entry)
    if forbidden:
        errors.append("removed provenance fields present: " + ", ".join(sorted(forbidden)))

    for field in REQUIRED_TEXT:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"missing {field}")

    definition = entry.get("definition", "")
    if isinstance(definition, str) and definition.startswith(PLACEHOLDER):
        errors.append("placeholder definition")

    for field in REQUIRED_LISTS:
        if not isinstance(entry.get(field), list):
            errors.append(f"{field} is not an array")

    citations = entry.get("citations")
    if isinstance(citations, list):
        if not citations:
            errors.append("entry has no citations")
        for number, citation in enumerate(citations, 1):
            if not isinstance(citation, dict):
                errors.append(f"citation {number} is not an object")
                continue
            for field in REQUIRED_CITATION:
                value = citation.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"citation {number} missing {field}")
            url = citation.get("url", "")
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"citation {number} has invalid URL")
            if citation.get("accessed") and not _valid_date(citation["accessed"]):
                errors.append(f"citation {number} accessed is not ISO-8601")

    if not isinstance(entry.get("master_index"), int):
        errors.append("master_index is not an integer")
    return errors


def main():
    entries = []
    failures = []
    rows = []
    print(f"{'domain':44} {'n':>4} {'bad':>4}  state")
    for path in sorted((ROOT / "concepts").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"{path.stem:44} CORRUPT")
            failures.append(f"{path.name}: invalid JSON: {exc}")
            continue
        if not isinstance(data, list):
            failures.append(f"{path.name}: top-level value is not an array")
            continue
        bad = 0
        for entry in data:
            errors = entry_errors(entry)
            if errors:
                bad += 1
                label = entry.get("id") or entry.get("name") or "<unknown>"
                failures.append(f"{path.name}: {label}: " + "; ".join(errors))
        state = "VALID" if bad == 0 else "INVALID"
        rows.append((path.stem, len(data), bad, state))
        entries.extend(data)

    for row in rows:
        print(f"{row[0]:44} {row[1]:>4} {row[2]:>4}  {row[3]}")

    ids = [entry.get("id") for entry in entries]
    names = [str(entry.get("name", "")).casefold() for entry in entries]
    indexes = [entry.get("master_index") for entry in entries]
    if len(entries) != EXPECTED_CONCEPT_COUNT:
        failures.append(
            f"expected {EXPECTED_CONCEPT_COUNT} canonical entries, found {len(entries)}"
        )
    if len(set(ids)) != len(ids):
        failures.append("duplicate or missing IDs exist")
    if len(set(names)) != len(names):
        failures.append("duplicate or missing names exist")
    if not all(isinstance(index, int) for index in indexes):
        failures.append("all master_index values must be integers")
    elif sorted(indexes) != list(range(1, EXPECTED_CONCEPT_COUNT + 1)):
        failures.append(
            f"master_index must cover 1..{EXPECTED_CONCEPT_COUNT} exactly once"
        )

    source_policy_path = ROOT / "sources" / "source-policy.json"
    source_policy = None
    if not source_policy_path.exists():
        failures.append("sources/source-policy.json is required")
    else:
        try:
            source_policy = json.loads(source_policy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"sources/source-policy.json: invalid JSON: {exc}")
        else:
            allowed_tiers = {"primary", "canonical-technical", "secondary"}
            if (source_policy.get("schema_version") != 1
                    or source_policy.get("default_tier") not in allowed_tiers
                    or not isinstance(source_policy.get("host_tiers"), dict)
                    or not set(source_policy["host_tiers"].values()).issubset(allowed_tiers)):
                failures.append("sources/source-policy.json has an invalid tier policy")

    relationship_vocab_path = ROOT / "relationships" / "vocabulary.json"
    if not relationship_vocab_path.exists():
        failures.append("relationships/vocabulary.json is required")
    else:
        try:
            relationship_vocab = json.loads(relationship_vocab_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"relationships/vocabulary.json: invalid JSON: {exc}")
        else:
            terms = relationship_vocab.get("terms")
            if relationship_vocab.get("schema_version") != 1 or not isinstance(terms, list):
                failures.append("relationships/vocabulary.json has an invalid structure")
            else:
                labels = [item.get("label") for item in terms if isinstance(item, dict)]
                external_ids = [item.get("id") for item in terms if isinstance(item, dict)]
                if (len(labels) != len(terms) or len(set(str(label).casefold() for label in labels)) != len(labels)
                        or len(set(external_ids)) != len(external_ids)
                        or any(not isinstance(item, dict) or item.get("kind") != "external-term"
                               or not isinstance(item.get("id"), str) or not item["id"].startswith("external/")
                               for item in terms)):
                    failures.append("relationships/vocabulary.json has invalid external terms")
                candidates = {}
                for entry in entries:
                    for term in [entry["name"], *entry.get("aliases", [])]:
                        candidates.setdefault(term.casefold(), set()).add(entry["id"])
                internal_terms = {term for term, candidate_ids in candidates.items() if len(candidate_ids) == 1}
                missing_external = sorted({
                    relationship for entry in entries for relationship in entry["relationships"]
                    if relationship.casefold() not in internal_terms
                    and relationship.casefold() not in {str(label).casefold() for label in labels}
                })
                if missing_external:
                    failures.append("relationship vocabulary missing terms: " + ", ".join(missing_external))

    citation_audit_path = ROOT / "audits" / "citation-audit.json"
    if not citation_audit_path.exists():
        failures.append("audits/citation-audit.json is required")
    else:
        try:
            citation_audit = json.loads(citation_audit_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"audits/citation-audit.json: invalid JSON: {exc}")
        else:
            audited = citation_audit.get("citations")
            current_urls = {
                citation["url"] for entry in entries for citation in entry.get("citations", [])
                if isinstance(citation, dict) and isinstance(citation.get("url"), str)
            }
            if citation_audit.get("schema_version") != 1 or not isinstance(audited, list):
                failures.append("audits/citation-audit.json has an invalid structure")
            else:
                audited_urls = {item.get("url") for item in audited if isinstance(item, dict)}
                broken = [item.get("url") for item in audited if isinstance(item, dict)
                          and item.get("access_status") == "broken"]
                if audited_urls != current_urls:
                    failures.append("audits/citation-audit.json does not match canonical citation URLs")
                if broken:
                    failures.append("audits/citation-audit.json contains broken citations: " + ", ".join(broken))

    valid_regime_tags = set()
    taxonomy_path = ROOT / "regimes" / "taxonomy.json"
    if not taxonomy_path.exists():
        failures.append("regimes/taxonomy.json is required")
    else:
        try:
            taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"regimes/taxonomy.json: invalid JSON: {exc}")
        else:
            found_dimensions = {}
            dimensions = taxonomy.get("dimensions")
            if not isinstance(dimensions, list):
                failures.append("regime taxonomy dimensions must be an array")
            else:
                for dimension in dimensions:
                    if not isinstance(dimension, dict):
                        failures.append("regime taxonomy dimension is not an object")
                        continue
                    dimension_id = dimension.get("id")
                    states = dimension.get("states")
                    if not isinstance(dimension_id, str) or not isinstance(states, list):
                        failures.append("regime taxonomy dimension is missing id or states")
                        continue
                    state_ids = {
                        state.get("id") for state in states if isinstance(state, dict)
                    }
                    found_dimensions[dimension_id] = state_ids
                    for state in states:
                        if (not isinstance(state, dict)
                                or not isinstance(state.get("id"), str)
                                or not isinstance(state.get("definition"), str)
                                or not state["definition"].strip()):
                            failures.append(f"regime taxonomy {dimension_id} has an invalid state")
                            continue
                        valid_regime_tags.add(f"{dimension_id}.{state['id']}")
                if found_dimensions != EXPECTED_REGIME_DIMENSIONS:
                    failures.append("regime taxonomy does not match the controlled dimensions and states")

    core_ids = set()
    collection_path = ROOT / "collections" / "core-perps.json"
    if not collection_path.exists():
        failures.append("collections/core-perps.json is required")
    else:
        try:
            collection = json.loads(collection_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"core-perps.json: invalid JSON: {exc}")
        else:
            concept_ids = collection.get("concept_ids")
            if not isinstance(concept_ids, list) or len(concept_ids) != 50:
                failures.append("core-perps collection must contain exactly 50 concept IDs")
            elif len(set(concept_ids)) != 50:
                failures.append("core-perps collection contains duplicate concept IDs")
            else:
                core_ids = set(concept_ids)
                missing = sorted(set(concept_ids) - set(ids))
                if missing:
                    failures.append("core-perps collection has unknown IDs: " + ", ".join(missing))
                by_id = {entry["id"]: entry for entry in entries}
                shallow = [
                    concept_id for concept_id in concept_ids
                    if len(by_id[concept_id].get("citations", [])) < 2
                ]
                if shallow:
                    failures.append("core-perps concepts need at least two citations: " + ", ".join(shallow))
                if source_policy:
                    authoritative = []
                    host_tiers = source_policy["host_tiers"]
                    for concept_id in concept_ids:
                        tiers = {
                            host_tiers.get(urlparse(citation["url"]).netloc.casefold(), source_policy["default_tier"])
                            for citation in by_id[concept_id]["citations"]
                        }
                        if tiers == {"secondary"}:
                            authoritative.append(concept_id)
                    if authoritative:
                        failures.append(
                            "core-perps concepts need a primary or canonical-technical citation: "
                            + ", ".join(authoritative)
                        )

                annotations = collection.get("annotations")
                if not isinstance(annotations, dict):
                    failures.append("core-perps annotations must be an object")
                elif set(annotations) != set(concept_ids):
                    failures.append("core-perps annotations must cover exactly the 50 concept IDs")
                else:
                    for concept_id, annotation in annotations.items():
                        if not isinstance(annotation, dict):
                            failures.append(f"core-perps annotation {concept_id} is not an object")
                            continue
                        tags = annotation.get("regime_relevance")
                        note = annotation.get("behavior_note")
                        if not isinstance(tags, list) or not tags:
                            failures.append(f"core-perps annotation {concept_id} needs regime_relevance")
                        elif len(tags) != len(set(tags)):
                            failures.append(f"core-perps annotation {concept_id} has duplicate regime tags")
                        else:
                            unknown_tags = sorted(set(tags) - valid_regime_tags)
                            if unknown_tags:
                                failures.append(
                                    f"core-perps annotation {concept_id} has unknown regime tags: "
                                    + ", ".join(unknown_tags)
                                )
                        if not isinstance(note, str) or not note.strip():
                            failures.append(f"core-perps annotation {concept_id} needs behavior_note")

    playbook_paths = sorted((ROOT / "playbooks").glob("*.json"))
    if len(playbook_paths) != 5:
        failures.append(f"expected exactly 5 playbooks, found {len(playbook_paths)}")
    playbook_ids = []
    for playbook_path in playbook_paths:
        try:
            playbook = json.loads(playbook_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{playbook_path.name}: invalid JSON: {exc}")
            continue
        if not isinstance(playbook, dict):
            failures.append(f"{playbook_path.name}: playbook must be an object")
            continue
        missing_fields = sorted(PLAYBOOK_REQUIRED - set(playbook))
        if missing_fields:
            failures.append(f"{playbook_path.name}: missing fields: " + ", ".join(missing_fields))
        playbook_id = playbook.get("id")
        playbook_ids.append(playbook_id)
        if playbook_id != playbook_path.stem:
            failures.append(f"{playbook_path.name}: id must match filename")
        if playbook.get("classification") != "untested-research-hypothesis":
            failures.append(f"{playbook_path.name}: invalid classification")
        if playbook.get("market_type") != "generic-crypto-perpetual-futures":
            failures.append(f"{playbook_path.name}: invalid market_type")
        if playbook.get("signal_timeframe") != "15m":
            failures.append(f"{playbook_path.name}: signal_timeframe must be 15m")
        if playbook.get("warning") != PLAYBOOK_WARNING:
            failures.append(f"{playbook_path.name}: required warning is missing or changed")
        linked_concepts = playbook.get("concept_ids")
        if not isinstance(linked_concepts, list) or len(linked_concepts) < 2:
            failures.append(f"{playbook_path.name}: concept_ids needs at least two items")
        else:
            unknown_concepts = sorted(set(linked_concepts) - core_ids)
            if unknown_concepts:
                failures.append(f"{playbook_path.name}: concepts outside core: " + ", ".join(unknown_concepts))
        required_data = playbook.get("required_data")
        if (not isinstance(required_data, list) or not required_data
                or any(not isinstance(item, dict)
                       or not all(isinstance(item.get(field), str) and item[field].strip()
                                  for field in ("field", "cadence", "freshness"))
                       for item in required_data)):
            failures.append(f"{playbook_path.name}: invalid required_data")
        entries_by_side = playbook.get("entry_conditions")
        if (not isinstance(entries_by_side, dict)
                or any(not isinstance(entries_by_side.get(side), list)
                       or not entries_by_side[side] for side in ("long", "short"))):
            failures.append(f"{playbook_path.name}: entry_conditions needs long and short rules")
        profile = playbook.get("regime_profile")
        if not isinstance(profile, dict):
            failures.append(f"{playbook_path.name}: invalid regime_profile")
        else:
            profile_tags = []
            for side in ("favored", "avoid"):
                tags = profile.get(side)
                if not isinstance(tags, list) or not tags:
                    failures.append(f"{playbook_path.name}: regime_profile.{side} is required")
                else:
                    profile_tags.extend(tags)
            unknown_tags = sorted(set(profile_tags) - valid_regime_tags)
            if unknown_tags:
                failures.append(f"{playbook_path.name}: unknown regime tags: " + ", ".join(unknown_tags))
        constraints = playbook.get("risk_constraints")
        if (not isinstance(constraints, dict)
                or constraints.get("risk_budget_input_required") is not True
                or not isinstance(constraints.get("rules"), list)
                or not constraints["rules"]):
            failures.append(f"{playbook_path.name}: invalid risk_constraints")
        for field, minimum in (("failure_modes", 2), ("validation_plan", 3)):
            value = playbook.get(field)
            if not isinstance(value, list) or len(value) < minimum:
                failures.append(f"{playbook_path.name}: {field} needs at least {minimum} items")
    if len(set(playbook_ids)) != len(playbook_ids):
        failures.append("playbook IDs must be unique")

    required_schemas = {
        "playbook.schema.json", "research-spec.schema.json",
        "dataset-manifest.schema.json", "trade-log.schema.json",
        "research-result.schema.json", "concept-skill.schema.json",
        "concept-aliases.schema.json", "skill-alias.schema.json",
        "skill-alias-catalog.schema.json", "skill-manifest.schema.json",
        "skill-architecture.schema.json", "source-policy.schema.json",
        "citation-audit.schema.json", "relationship-vocabulary.schema.json",
        "analysis-context-request.schema.json", "analysis-context.schema.json",
    }
    schema_paths = {path.name: path for path in (ROOT / "schemas").glob("*.json")}
    missing_schemas = sorted(required_schemas - set(schema_paths))
    if missing_schemas:
        failures.append("missing JSON schemas: " + ", ".join(missing_schemas))
    for schema_name in sorted(required_schemas & set(schema_paths)):
        try:
            schema = json.loads(schema_paths[schema_name].read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{schema_name}: invalid JSON: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            failures.append(f"{schema_name}: must declare JSON Schema 2020-12")

    research_specs = sorted((ROOT / "research" / "specs").glob("*.json"))
    if len(research_specs) != 1:
        failures.append(f"expected exactly 1 executable research spec, found {len(research_specs)}")
    for spec_path in research_specs:
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{spec_path.name}: invalid JSON: {exc}")
            continue
        if set(spec) != RESEARCH_SPEC_REQUIRED:
            failures.append(f"{spec_path.name}: executable spec fields do not match the contract")
        if spec.get("id") != spec_path.stem:
            failures.append(f"{spec_path.name}: id must match filename")
        if spec.get("playbook_id") not in set(playbook_ids):
            failures.append(f"{spec_path.name}: unknown playbook_id")
        if spec.get("classification") != "preliminary-executable-research-spec":
            failures.append(f"{spec_path.name}: invalid classification")
        if spec.get("assets") != ["BTC", "ETH"]:
            failures.append(f"{spec_path.name}: first study assets must be BTC and ETH")
        if spec.get("timeframes") != {"signal": "15m", "context": ["1h", "4h"]}:
            failures.append(f"{spec_path.name}: invalid timeframes")
        if spec.get("warning") != RESEARCH_WARNING:
            failures.append(f"{spec_path.name}: required research warning is missing or changed")

    dataset_manifests = sorted((ROOT / "research" / "datasets").glob("*/dataset-manifest.json"))
    if len(dataset_manifests) != 1:
        failures.append(f"expected exactly 1 immutable research dataset, found {len(dataset_manifests)}")
    for manifest_path in dataset_manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{manifest_path}: invalid JSON: {exc}")
            continue
        if manifest.get("dataset_id") != manifest_path.parent.name:
            failures.append(f"{manifest_path}: dataset_id must match directory")
        if manifest.get("assets") != ["BTC", "ETH"]:
            failures.append(f"{manifest_path}: assets must be BTC and ETH")
        quality = manifest.get("quality")
        if (not isinstance(quality, dict) or quality.get("valid") is not True
                or quality.get("closed_candles_only") is not True
                or any(quality.get(field) != 0 for field in ("duplicates", "missing_intervals", "funding_gaps"))):
            failures.append(f"{manifest_path}: dataset quality gate is not clean")
        files = manifest.get("files")
        verified_hashes = []
        if not isinstance(files, list) or len(files) != 4:
            failures.append(f"{manifest_path}: dataset must contain four data files")
            continue
        for item in sorted(files, key=lambda value: value.get("path", "")):
            relative = item.get("path")
            if not isinstance(relative, str) or Path(relative).name != relative:
                failures.append(f"{manifest_path}: invalid dataset file path")
                continue
            data_path = manifest_path.parent / relative
            if not data_path.exists():
                failures.append(f"{manifest_path}: missing data file {relative}")
                continue
            digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
            verified_hashes.append(digest)
            if digest != item.get("sha256"):
                failures.append(f"{manifest_path}: hash mismatch for {relative}")
            try:
                document = json.loads(data_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                failures.append(f"{data_path}: invalid JSON: {exc}")
                continue
            rows = document.get("candles") if item.get("kind") == "candles" else document.get("funding")
            if not isinstance(rows, list) or len(rows) != item.get("rows"):
                failures.append(f"{manifest_path}: row-count mismatch for {relative}")
        aggregate_hash = hashlib.sha256("\n".join(verified_hashes).encode("ascii")).hexdigest()
        if aggregate_hash != manifest.get("dataset_sha256"):
            failures.append(f"{manifest_path}: aggregate dataset hash mismatch")

    result_paths = sorted((ROOT / "research" / "results").glob("*/result.json"))
    if len(result_paths) != 1:
        failures.append(f"expected exactly 1 canonical research result, found {len(result_paths)}")
    for result_path in result_paths:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{result_path}: invalid JSON: {exc}")
            continue
        if result.get("run_id") != result_path.parent.name:
            failures.append(f"{result_path}: run_id must match directory")
        if result.get("classification") != "preliminary-limited-window-research":
            failures.append(f"{result_path}: invalid classification")
        if result.get("status") not in {"preliminary", "inconclusive", "data-quality-failed"}:
            failures.append(f"{result_path}: invalid result status")
        if len(research_specs) == 1:
            expected_spec_hash = hashlib.sha256(research_specs[0].read_bytes()).hexdigest()
            if result.get("spec", {}).get("sha256") != expected_spec_hash:
                failures.append(f"{result_path}: spec hash mismatch")
        if len(dataset_manifests) == 1:
            expected_dataset = json.loads(dataset_manifests[0].read_text(encoding="utf-8"))
            if result.get("dataset", {}).get("sha256") != expected_dataset.get("dataset_sha256"):
                failures.append(f"{result_path}: dataset hash mismatch")
        scenarios = result.get("scenarios")
        if not isinstance(scenarios, list) or [item.get("slippage_bps") for item in scenarios] != [0.0, 2.5, 5.0]:
            failures.append(f"{result_path}: cost scenarios must be 0, 2.5, and 5 bps")
            scenarios = []
        headline = [item for item in scenarios if item.get("headline") is True]
        if len(headline) != 1 or headline[0].get("slippage_bps") != result.get("headline_scenario"):
            failures.append(f"{result_path}: exactly one headline scenario is required")
            headline = []
        trade_path = result_path.with_name("trades.json")
        if not trade_path.exists():
            failures.append(f"{result_path}: trades.json is missing")
            continue
        try:
            trade_log = json.loads(trade_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{trade_path}: invalid JSON: {exc}")
            continue
        if trade_log.get("run_id") != result.get("run_id"):
            failures.append(f"{trade_path}: run_id mismatch")
        trades = trade_log.get("trades")
        if not isinstance(trades, list):
            failures.append(f"{trade_path}: trades must be an array")
            trades = []
        if headline and headline[0].get("metrics", {}).get("trade_count") != len(trades):
            failures.append(f"{trade_path}: trade count does not match headline metrics")
        trade_ids = [trade.get("trade_id") for trade in trades]
        if len(trade_ids) != len(set(trade_ids)):
            failures.append(f"{trade_path}: trade IDs must be unique")
        for trade in trades:
            if not trade.get("signal_time", 0) < trade.get("entry_time", 0) <= trade.get("exit_time", 0):
                failures.append(f"{trade_path}: invalid event order for {trade.get('trade_id')}")
            expected_net = (
                trade.get("gross_r", 0) - trade.get("fee_r", 0)
                - trade.get("slippage_r", 0) + trade.get("funding_r", 0)
            )
            if abs(expected_net - trade.get("net_r", 0)) > 1e-9:
                failures.append(f"{trade_path}: cost decomposition mismatch for {trade.get('trade_id')}")

    placeholders = sum(
        1 for entry in entries
        if str(entry.get("definition", "")).startswith(PLACEHOLDER)
    )
    citations = sum(len(entry.get("citations", [])) for entry in entries)
    skill_errors = validate_catalog(ROOT)
    failures.extend(f"skill catalog: {error}" for error in skill_errors)
    skill_manifest = json.loads(
        (ROOT / "skills" / "manifest.json").read_text(encoding="utf-8")
    )
    print(
        f"CONCEPT SKILLS {skill_manifest['skill_count']} canonical; "
        f"{skill_manifest['alias_count']} compatibility aliases"
    )
    print(
        f"\nTOTAL entries={len(entries)} citations={citations} "
        f"placeholders={placeholders} errors={len(failures)}"
    )
    if failures:
        print("\nVALIDATION ERRORS")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Validate and summarize the trading knowledge library.

Usage: python scripts/status.py

The command exits non-zero when the catalog is structurally incomplete,
contains a placeholder, lacks required content, or has malformed citations.
"""
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "A trading concept within"
REQUIRED_TEXT = (
    "id", "name", "domain", "definition", "intuition", "mechanics",
    "failure_modes", "misconceptions", "example", "source_hint",
)
REQUIRED_LISTS = ("aliases", "relationships", "citations")
REQUIRED_CITATION = ("source", "url", "section", "accessed")
REMOVED_PROVENANCE_FIELDS = {
    "status", "reviewed_by", "review_date", "review_note",
}
EXPECTED_REGIME_DIMENSIONS = {
    "trend": {"uptrend", "downtrend", "range", "transition"},
    "volatility": {"compressed", "normal", "expanded", "shock"},
    "liquidity": {"deep", "normal", "thin", "dislocated"},
    "positioning": {"balanced", "long-crowded", "short-crowded", "deleveraging"},
}


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
    if len(entries) != 1500:
        failures.append(f"expected 1500 entries, found {len(entries)}")
    if len(set(ids)) != len(ids):
        failures.append("duplicate or missing IDs exist")
    if len(set(names)) != len(names):
        failures.append("duplicate or missing names exist")
    if not all(isinstance(index, int) for index in indexes):
        failures.append("all master_index values must be integers")
    elif sorted(indexes) != list(range(1, 1501)):
        failures.append("master_index must cover 1..1500 exactly once")

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

    placeholders = sum(
        1 for entry in entries
        if str(entry.get("definition", "")).startswith(PLACEHOLDER)
    )
    citations = sum(len(entry.get("citations", [])) for entry in entries)
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

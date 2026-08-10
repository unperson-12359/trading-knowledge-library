#!/usr/bin/env python3
"""Create the explicit external-term registry for non-canonical relationships."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "relationships" / "vocabulary.json"


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def main():
    concepts = []
    for path in sorted((ROOT / "concepts").glob("*.json")):
        concepts.extend(json.loads(path.read_text(encoding="utf-8")))
    candidates = {}
    for concept in concepts:
        for term in [concept["name"], *concept.get("aliases", [])]:
            candidates.setdefault(term.casefold(), set()).add(concept["id"])
    internal = {term for term, ids in candidates.items() if len(ids) == 1}
    labels = sorted({
        relationship for concept in concepts for relationship in concept["relationships"]
        if relationship.casefold() not in internal
    }, key=str.casefold)
    used = set()
    terms = []
    for label in labels:
        base = slug(label) or "term"
        identifier = f"external/{base}"
        suffix = 2
        while identifier in used:
            identifier = f"external/{base}-{suffix}"
            suffix += 1
        used.add(identifier)
        terms.append({"id": identifier, "label": label, "kind": "external-term",
                      "note": "A useful relationship term not yet promoted to a full canonical concept."})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "$schema": "../schemas/relationship-vocabulary.schema.json",
        "schema_version": 1, "terms": terms,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"external relationship terms: {len(terms)}")


if __name__ == "__main__":
    main()

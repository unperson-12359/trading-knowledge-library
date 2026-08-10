"""Diagnose canonical concept-file damage without restoring legacy duplicates.

The active concepts/*.json files are the source of truth. Recover damaged files
from version control, then run scripts/status.py; never re-import master_v1.txt
over the active catalog.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONCEPTS = ROOT / "concepts"
EXPECTED_COUNT = 1438


def main():
    entries = []
    failures = []
    for path in sorted(CONCEPTS.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{path.name}: invalid JSON: {exc}")
            continue
        if not isinstance(payload, list):
            failures.append(f"{path.name}: top level must be an array")
            continue
        entries.extend(payload)
    indexes = [entry.get("master_index") for entry in entries]
    ids = [entry.get("id") for entry in entries]
    if len(entries) != EXPECTED_COUNT:
        failures.append(f"expected {EXPECTED_COUNT} entries, found {len(entries)}")
    if sorted(indexes) != list(range(1, EXPECTED_COUNT + 1)):
        failures.append(f"master_index must cover 1..{EXPECTED_COUNT} exactly once")
    if len(ids) != len(set(ids)):
        failures.append("concept IDs must be unique")
    if failures:
        print("Canonical catalog needs recovery from version control:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Canonical catalog is intact: {EXPECTED_COUNT} entries; no repair needed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

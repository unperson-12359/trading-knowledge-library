"""Validate and summarize the trading knowledge library.

Usage: python scripts/status.py

The command exits non-zero when the catalog is structurally incomplete or an
entry labelled ``reviewed`` does not meet the v1 reviewed-entry contract.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "A trading concept within"
STATUSES = {"candidate", "provisional", "reviewed", "trusted", "disputed"}
REQUIRED_REVIEWED = (
    "definition", "intuition", "mechanics", "failure_modes", "misconceptions",
    "example", "reviewed_by", "review_date",
)
REQUIRED_CITATION = ("source", "url", "section", "accessed")


def _valid_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def entry_errors(entry):
    errors = []
    status = entry.get("status")
    if status not in STATUSES:
        errors.append(f"invalid status {status!r}")
    definition = entry.get("definition", "")
    if not isinstance(definition, str) or not definition.strip():
        errors.append("missing definition")
    elif definition.startswith(PLACEHOLDER):
        errors.append("placeholder definition")

    if status in {"reviewed", "trusted"}:
        for field in REQUIRED_REVIEWED:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"missing {field}")
        if entry.get("review_date") and not _valid_date(entry["review_date"]):
            errors.append("review_date is not ISO-8601")
        citations = entry.get("citations")
        if not isinstance(citations, list) or not citations:
            errors.append("reviewed entry has no citations")
        else:
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
    return errors


def main():
    entries = []
    failures = []
    rows = []
    print(f"{'domain':44} {'n':>4} {'rev':>4} {'prov':>4} {'bad':>4}  state")
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
        reviewed = sum(1 for entry in data if entry.get("status") == "reviewed")
        provisional = sum(1 for entry in data if entry.get("status") == "provisional")
        state = "DONE" if reviewed == len(data) and bad == 0 else "partial"
        rows.append((path.stem, len(data), reviewed, provisional, bad, state))
        entries.extend(data)

    for row in rows:
        print(f"{row[0]:44} {row[1]:>4} {row[2]:>4} {row[3]:>4} {row[4]:>4}  {row[5]}")

    ids = [entry.get("id") for entry in entries]
    names = [str(entry.get("name", "")).casefold() for entry in entries]
    indexes = [entry.get("master_index") for entry in entries]
    if len(entries) != 1500:
        failures.append(f"expected 1500 entries, found {len(entries)}")
    if len(set(ids)) != len(ids):
        failures.append("duplicate or missing IDs exist")
    if len(set(names)) != len(names):
        failures.append("duplicate or missing names exist")
    if sorted(indexes) != list(range(1, 1501)):
        failures.append("master_index must cover 1..1500 exactly once")

    reviewed = sum(1 for entry in entries if entry.get("status") == "reviewed")
    provisional = sum(1 for entry in entries if entry.get("status") == "provisional")
    placeholders = sum(
        1 for entry in entries
        if str(entry.get("definition", "")).startswith(PLACEHOLDER)
    )
    print(
        f"\nTOTAL entries={len(entries)} reviewed={reviewed} "
        f"provisional={provisional} placeholders={placeholders} errors={len(failures)}"
    )
    if failures:
        print("\nVALIDATION ERRORS")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

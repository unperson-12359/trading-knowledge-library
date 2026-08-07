"""Repair concept files damaged by killed agents.

- Salvages complete reviewed entries from truncated JSON (indicators, options).
- Re-imports missing entries from sources/master_v1.txt as provisional.
- Never touches intact entries; never deletes reviewed work.
- Asserts the library is whole afterwards: 1,500 unique entries, every
  master_index 1..1500 present exactly once.

Pure stdlib; no network, no AI.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_master import CONCEPTS_DIR, DOMAIN_MAP, MASTER, parse_master, slugify

REVIEW_DATE = "2026-08-06"


def provisional_entry(raw):
    domain = DOMAIN_MAP.get(raw["domain"], raw["domain"])
    return {
        "id": f"{slugify(domain)}/{slugify(raw['name'])}",
        "name": raw["name"],
        "aliases": [],
        "domain": domain,
        "definition": raw["definition"],
        "intuition": "",
        "mechanics": "",
        "formula": "",
        "relationships": [],
        "failure_modes": "",
        "misconceptions": "",
        "example": "",
        "citations": [],
        "source_hint": raw["source_hint"],
        "status": "provisional",
        "reviewed_by": "",
        "review_date": "",
        "review_note": "Restored from master_v1 during repair; verification pending.",
        "master_index": raw["index"],
    }


def salvage_truncated(path: Path):
    """Return list of complete entry dicts from a truncated JSON array file."""
    text = path.read_text(encoding="utf-8")
    # entries are pretty-printed at depth 1; a complete entry ends with a line "  },"
    cut = text.rfind("\n  },")
    if cut == -1:
        return []
    candidate = text[:cut] + "\n  }\n]"
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return []


def atomic_write(path: Path, entries):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def main():
    master_raw = parse_master(MASTER)
    assert len(master_raw) == 1500
    by_domain = {}
    for raw in master_raw:
        domain = DOMAIN_MAP.get(raw["domain"], raw["domain"])
        by_domain.setdefault(domain, {})[raw["index"]] = raw

    damaged = ["indicators", "options", "time-series-analysis",
               "trading-systems", "macro-and-fundamentals"]

    for slug in damaged:
        path = CONCEPTS_DIR / f"{slug}.json"
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            source = "intact"
        except json.JSONDecodeError:
            existing = salvage_truncated(path)
            source = "salvaged"
        domain = existing[0]["domain"] if existing else None
        expected = by_domain[domain]
        have = {e["master_index"] for e in existing}
        missing = [idx for idx in sorted(expected) if idx not in have]
        for idx in missing:
            existing.append(provisional_entry(expected[idx]))
        existing.sort(key=lambda e: e["master_index"])
        atomic_write(path, existing)
        kept = len(have)
        print(f"{slug}.json ({source}): kept {kept}, restored {len(missing)}, total {len(existing)}")

    # whole-library validation
    all_entries = []
    for p in sorted(CONCEPTS_DIR.glob("*.json")):
        all_entries.extend(json.loads(p.read_text(encoding="utf-8")))
    idxs = sorted(e["master_index"] for e in all_entries)
    assert len(all_entries) == 1500, f"total {len(all_entries)}"
    assert idxs == list(range(1, 1501)), "master_index coverage broken"
    assert len({e["id"] for e in all_entries}) == 1500, "duplicate ids"
    assert len({e["name"].lower() for e in all_entries}) == 1500, "duplicate names"
    reviewed = sum(1 for e in all_entries if e["status"] == "reviewed")
    print(f"\nLIBRARY WHOLE: 1500 entries, reviewed={reviewed}, provisional={1500 - reviewed}")


if __name__ == "__main__":
    sys.exit(main())

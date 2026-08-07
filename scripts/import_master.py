"""Parse sources/master_v1.txt into concepts/<domain>.json files.

Stdlib only. Asserts exactly 1,500 unique entries and normalizes the stray
micro-domains from the first 34 reviewed entries into the canonical domains.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "sources" / "master_v1.txt"
CONCEPTS_DIR = ROOT / "concepts"

DOMAIN_MAP = {
    "Foundations": "Market foundations",
    "Venues": "Market foundations",
    "Infrastructure": "Market foundations",
    "Participants": "Participants",
    "Orders": "Orders and execution",
    "Execution": "Orders and execution",
    "Quotes": "Microstructure",
    "Derivatives": "Contract mechanics",
    "Risk": "Risk and performance",
    "Statistics": "Statistics and probability",
    "Probability": "Statistics and probability",
}


def slugify(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_master(path: Path):
    entries = []
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = re.match(r"^(\d{4})\.\s+(.+)$", line)
        if m:
            if current:
                entries.append(current)
            current = {"index": int(m.group(1)), "name": m.group(2).strip()}
        elif current is not None:
            for field, key in (("Domain", "domain"), ("Definition", "definition"),
                               ("Source authority", "source_hint"), ("Status", "status")):
                if line.startswith(f"{field}: "):
                    current[key] = line[len(field) + 2:].strip()
    if current:
        entries.append(current)
    return entries


def main():
    raw_entries = parse_master(MASTER)
    assert len(raw_entries) == 1500, f"expected 1500 entries, got {len(raw_entries)}"

    names = [e["name"].lower() for e in raw_entries]
    assert len(set(names)) == 1500, "duplicate entry names found"

    domains = {}
    for e in raw_entries:
        for key in ("domain", "definition", "source_hint", "status"):
            assert key in e, f"entry {e['name']} missing {key}"
        domain = DOMAIN_MAP.get(e["domain"], e["domain"])
        status = e["status"].lower()
        assert status in ("reviewed", "provisional"), f"bad status {status}"
        entry = {
            "id": f"{slugify(domain)}/{slugify(e['name'])}",
            "name": e["name"],
            "aliases": [],
            "domain": domain,
            "definition": e["definition"],
            "intuition": "",
            "mechanics": "",
            "formula": "",
            "relationships": [],
            "failure_modes": "",
            "misconceptions": "",
            "example": "",
            "citations": [],
            "source_hint": e["source_hint"],
            "status": status,
            "reviewed_by": "master_v1 import" if status == "reviewed" else "",
            "review_date": "2026-08-06" if status == "reviewed" else "",
            "review_note": ("Reviewed in master_v1 against source family; exact citation pending."
                            if status == "reviewed" else ""),
            "master_index": e["index"],
        }
        domains.setdefault(domain, []).append(entry)

    CONCEPTS_DIR.mkdir(exist_ok=True)
    for old in CONCEPTS_DIR.glob("*.json"):
        old.unlink()
    for domain, entries in sorted(domains.items()):
        out = CONCEPTS_DIR / f"{slugify(domain)}.json"
        out.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(len(v) for v in domains.values())
    reviewed = sum(1 for v in domains.values() for e in v if e["status"] == "reviewed")
    print(f"domains: {len(domains)}")
    print(f"entries: {total}")
    print(f"reviewed: {reviewed}")
    print(f"provisional: {total - reviewed}")
    for domain in sorted(domains):
        print(f"  {domain}: {len(domains[domain])}")
    assert total == 1500


if __name__ == "__main__":
    sys.exit(main())

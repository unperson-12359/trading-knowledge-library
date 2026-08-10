"""Parse the immutable 1,500-entry legacy import into a separate directory.

This archival utility refuses to write into concepts/, whose current JSON is
the source of truth and includes post-import consolidation decisions.
"""
import argparse
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
                               ("Source authority", "_legacy_source_hint")):
                if line.startswith(f"{field}: "):
                    current[key] = line[len(field) + 2:].strip()
    if current:
        entries.append(current)
    return entries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", required=True,
        help="separate directory for the legacy 1,500-entry projection",
    )
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    if output_dir == CONCEPTS_DIR.resolve():
        parser.error("refusing to overwrite canonical concepts/ with the legacy import")
    raw_entries = parse_master(MASTER)
    assert len(raw_entries) == 1500, f"expected 1500 entries, got {len(raw_entries)}"

    names = [e["name"].lower() for e in raw_entries]
    assert len(set(names)) == 1500, "duplicate entry names found"

    domains = {}
    for e in raw_entries:
        for key in ("domain", "definition"):
            assert key in e, f"entry {e['name']} missing {key}"
        domain = DOMAIN_MAP.get(e["domain"], e["domain"])
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
            "master_index": e["index"],
        }
        domains.setdefault(domain, []).append(entry)

    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("*.json"):
        old.unlink()
    for domain, entries in sorted(domains.items()):
        out = output_dir / f"{slugify(domain)}.json"
        out.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(len(v) for v in domains.values())
    print(f"domains: {len(domains)}")
    print(f"entries: {total}")
    for domain in sorted(domains):
        print(f"  {domain}: {len(domains[domain])}")
    assert total == 1500


if __name__ == "__main__":
    sys.exit(main())

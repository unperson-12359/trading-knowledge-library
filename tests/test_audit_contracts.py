import json
import unittest
from pathlib import Path

from scripts import status


ROOT = Path(__file__).resolve().parent.parent


def concepts():
    rows = []
    for path in (ROOT / "concepts").glob("*.json"):
        rows.extend(json.loads(path.read_text(encoding="utf-8")))
    return rows


class AuditContractTests(unittest.TestCase):
    def test_legacy_source_hint_is_rejected(self):
        entry = dict(concepts()[0])
        entry["source_hint"] = "citation pending"
        self.assertTrue(any("source_hint" in error for error in status.entry_errors(entry)))

    def test_relationship_vocabulary_covers_external_terms(self):
        vocabulary = json.loads((ROOT / "relationships" / "vocabulary.json").read_text(encoding="utf-8"))
        labels = {item["label"].casefold() for item in vocabulary["terms"]}
        candidates = {}
        for entry in concepts():
            for term in [entry["name"], *entry.get("aliases", [])]:
                candidates.setdefault(term.casefold(), set()).add(entry["id"])
        internal = {term for term, ids in candidates.items() if len(ids) == 1}
        external = {
            relationship.casefold() for entry in concepts() for relationship in entry["relationships"]
            if relationship.casefold() not in internal
        }
        self.assertEqual(labels, external)

    def test_committed_citation_audit_matches_catalog(self):
        audit = json.loads((ROOT / "audits" / "citation-audit.json").read_text(encoding="utf-8"))
        urls = {citation["url"] for entry in concepts() for citation in entry["citations"]}
        audited_urls = {row["url"] for row in audit["citations"]}
        self.assertEqual(audited_urls, urls)
        self.assertEqual(audit["summary"]["broken_urls"], [])


if __name__ == "__main__":
    unittest.main()

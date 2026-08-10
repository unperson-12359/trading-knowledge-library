import importlib.util
import json
import unittest
from pathlib import Path

from scripts import build_skills


ROOT = Path(__file__).resolve().parent.parent
EXPECTED_FIRST_GROUP = [
    "orders-and-execution/market-order",
    "orders-and-execution/limit-order",
    "orders-and-execution/stop-order",
    "microstructure/bid-ask-spread",
    "orders-and-execution/market-impact",
    "orders-and-execution/slippage",
    "contract-mechanics/open-interest",
    "risk-and-performance/margin",
    "risk-and-performance/initial-margin",
    "risk-and-performance/maintenance-margin",
    "risk-and-performance/leverage",
    "instruments/perpetual-futures-contract",
    "microstructure/order-book",
    "microstructure/market-depth",
    "microstructure/order-flow-imbalance",
    "time-series-analysis/regime-switching-model",
    "risk-and-performance/realized-volatility",
    "risk-and-performance/maximum-drawdown",
    "risk-and-performance/trade-expectancy",
    "risk-and-performance/position-sizing",
]


def load_router_search():
    path = ROOT / ".agents" / "skills" / "tkl-concept-router" / "scripts" / "search.py"
    spec = importlib.util.spec_from_file_location("tkl_router_search", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConceptSkillTests(unittest.TestCase):
    def test_catalog_order_starts_with_locked_core_group(self):
        actual = [row[0]["id"] for row in build_skills.ordered_records(ROOT)[:20]]
        self.assertEqual(actual, EXPECTED_FIRST_GROUP)

    def test_all_generated_names_are_unique_and_host_compatible(self):
        used = set()
        for concept, _, _ in build_skills.ordered_records(ROOT):
            name = build_skills.skill_name_for(concept, used)
            self.assertLessEqual(len(name), 63)
            self.assertRegex(name, r"^[a-z0-9-]+$")
            self.assertNotIn(name, used)
            used.add(name)
        self.assertEqual(len(used), 1438)

    def test_catalog_and_packages_validate(self):
        self.assertEqual(build_skills.validate_catalog(ROOT), [])

    def test_router_prefers_exact_concept(self):
        router = load_router_search()
        profiles = [
            {"skill_name": "tkl-slippage", "concept_id": "orders-and-execution/slippage",
             "display_name": "Slippage", "domain": "Orders and execution", "core": True,
             "description": "Apply slippage.", "trigger_phrases": ["slippage", "price slippage"]},
            {"skill_name": "tkl-market-impact", "concept_id": "orders-and-execution/market-impact",
             "display_name": "Market impact", "domain": "Orders and execution", "core": True,
             "description": "Apply market impact.", "trigger_phrases": ["market impact", "impact"]},
        ]
        matches = router.search(profiles, "slippage", limit=2)
        self.assertEqual(matches[0]["concept_id"], "orders-and-execution/slippage")
        self.assertGreater(matches[0]["match_score"], 100)

    def test_numbered_return_queries_bind_the_period(self):
        router = load_router_search()
        manifest = json.loads((ROOT / "skills" / "manifest.json").read_text(encoding="utf-8"))
        aliases = build_skills.expand_aliases(ROOT)
        for query, periods in [
            ("20-period simple return", 20),
            ("show the 20-period holding period return", 20),
            ("explain the 64 period return", 64),
            ("calculate a 100-period return", 100),
        ]:
            with self.subTest(query=query):
                match = router.search(manifest["skills"], query, limit=1, aliases=aliases)[0]
                self.assertEqual(match["skill_name"], "tkl-n-period-simple-return")
                self.assertEqual(match["bound_parameters"], {"periods": periods})

    def test_retired_ids_and_skill_names_resolve_as_aliases(self):
        router = load_router_search()
        manifest = json.loads((ROOT / "skills" / "manifest.json").read_text(encoding="utf-8"))
        aliases = build_skills.expand_aliases(ROOT)
        self.assertEqual(len(aliases), 63)
        for periods in range(2, 65):
            with self.subTest(periods=periods):
                matches = router.search(
                    manifest["skills"], "", limit=1,
                    skill_name=f"tkl-{periods}-period-simple-return", aliases=aliases,
                )
                self.assertEqual(matches[0]["skill_name"], "tkl-n-period-simple-return")
                self.assertEqual(matches[0]["bound_parameters"], {"periods": periods})
                concept_matches = router.search(
                    manifest["skills"], "", limit=1,
                    concept_id=f"parameterized-analytics/{periods}-period-simple-return",
                    aliases=aliases,
                )
                self.assertEqual(
                    concept_matches[0]["concept_id"],
                    "parameterized-analytics/n-period-simple-return",
                )
                self.assertEqual(
                    concept_matches[0]["bound_parameters"], {"periods": periods}
                )

    def test_parameterized_concept_replaces_numbered_canonicals(self):
        records = [row[0] for row in build_skills.load_concepts(ROOT)]
        ids = {record["id"] for record in records}
        self.assertEqual(len(records), 1438)
        self.assertIn("statistics-and-probability/simple-return", ids)
        self.assertIn("parameterized-analytics/n-period-simple-return", ids)
        for periods in range(2, 65):
            self.assertNotIn(f"parameterized-analytics/{periods}-period-simple-return", ids)

    def test_public_catalog_uses_unified_detail_pages_not_batch_language(self):
        catalog = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("batch", catalog.casefold())
        self.assertIn("Search 1,438 canonical trading concepts", catalog)
        self.assertIn('id="catalog-controls"', catalog)
        manifest = json.loads((ROOT / "skills" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["skill_count"], 1438)
        self.assertEqual(manifest["alias_count"], 63)
        generic = ROOT / "docs" / "skills" / "tkl-n-period-simple-return" / "index.html"
        html = generic.read_text(encoding="utf-8")
        self.assertIn('id="selected-period"', html)
        self.assertIn('data-skill-tab="concept"', html)
        self.assertIn('id="panel-concept-json"', html)

    def test_retired_site_and_api_urls_are_compatible(self):
        alias_catalog = json.loads(
            (ROOT / "docs" / "api" / "v1" / "concept-aliases.json").read_text(encoding="utf-8")
        )
        self.assertEqual(alias_catalog["alias_count"], 63)
        for periods in (2, 20, 64):
            page = ROOT / "docs" / "skills" / f"tkl-{periods}-period-simple-return" / "index.html"
            api = ROOT / "docs" / "api" / "v1" / "skills" / f"tkl-{periods}-period-simple-return.json"
            self.assertIn(f"?periods={periods}", page.read_text(encoding="utf-8"))
            payload = json.loads(api.read_text(encoding="utf-8"))
            self.assertEqual(payload["type"], "alias")
            self.assertEqual(payload["canonical_skill_name"], "tkl-n-period-simple-return")
            self.assertEqual(payload["parameters"], {"periods": periods})

    def test_legacy_browsing_routes_forward_to_the_consolidated_catalog(self):
        domain = (ROOT / "docs" / "parameterized-analytics" / "page-2.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("location.replace", domain)
        self.assertIn("20-period-simple-return", (
            ROOT / "docs" / "parameterized-analytics" / "index.html"
        ).read_text(encoding="utf-8"))
        self.assertIn("tkl-n-period-simple-return/?periods=27", domain)

    def test_public_concept_urls_are_unified(self):
        concepts = json.loads(
            (ROOT / "docs" / "api" / "v1" / "concepts.json").read_text(encoding="utf-8")
        )
        search_index = json.loads((ROOT / "docs" / "search-index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(concepts), 1438)
        self.assertTrue(all(row["url"] == row["skill_url"] for row in concepts))
        self.assertTrue(all(row["url"].startswith("skills/tkl-") for row in concepts))
        self.assertTrue(all(row["u"].startswith("skills/tkl-") for row in search_index))


if __name__ == "__main__":
    unittest.main()

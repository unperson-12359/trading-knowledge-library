import importlib.util
import json
import unittest
from pathlib import Path

from scripts import build_skills


ROOT = Path(__file__).resolve().parent.parent
EXPECTED_FIRST_BATCH = [
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
    def test_rollout_order_starts_with_locked_core_batch(self):
        actual = [row[0]["id"] for row in build_skills.ordered_records(ROOT)[:20]]
        self.assertEqual(actual, EXPECTED_FIRST_BATCH)

    def test_all_generated_names_are_unique_and_host_compatible(self):
        used = set()
        for concept, _, _ in build_skills.ordered_records(ROOT):
            name = build_skills.skill_name_for(concept, used)
            self.assertLessEqual(len(name), 63)
            self.assertRegex(name, r"^[a-z0-9-]+$")
            self.assertNotIn(name, used)
            used.add(name)
        self.assertEqual(len(used), 1500)

    def test_catalog_and_every_completed_batch_validate(self):
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

    def test_completed_batch_queries_route_to_the_expected_skill(self):
        router = load_router_search()
        manifest = json.loads(
            (ROOT / "skills" / "manifest.json").read_text(encoding="utf-8")
        )
        for eval_path in sorted((ROOT / "skills" / "evals").glob("batch-*.json")):
            evaluation = json.loads(eval_path.read_text(encoding="utf-8"))
            for case in evaluation["cases"]:
                for query in case["positive_queries"]:
                    with self.subTest(batch=evaluation["batch_number"], query=query):
                        matches = router.search(manifest["skills"], query, limit=1)
                        self.assertTrue(matches)
                        self.assertEqual(matches[0]["skill_name"], case["skill_name"])

    def test_progress_is_an_exact_multiple_of_twenty(self):
        progress = json.loads((ROOT / "skills" / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress["completed_count"], progress["completed_batches"] * 20)


if __name__ == "__main__":
    unittest.main()

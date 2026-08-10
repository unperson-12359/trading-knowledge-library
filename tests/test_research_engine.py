import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from scripts import research


def candle(index, open_price=100, high=101, low=99, close=100, volume=10):
    start = index * research.INTERVAL_MS
    return {
        "time": start,
        "end_time": start + research.INTERVAL_MS - 1,
        "open": str(open_price),
        "high": str(high),
        "low": str(low),
        "close": str(close),
        "volume": str(volume),
    }


class ResearchIndicatorTests(unittest.TestCase):
    def test_wilder_atr_uses_seed_then_recursive_smoothing(self):
        rows = [candle(0, high=11, low=9, close=10), candle(1, high=13, low=10, close=12), candle(2, high=14, low=11, close=13)]
        values = research.wilder_atr(rows, 2)
        self.assertIsNone(values[0])
        self.assertEqual(values[1], 2.5)
        self.assertEqual(values[2], 2.75)

    def test_nearest_rank(self):
        self.assertEqual(research.nearest_rank([5, 1, 4, 2, 3], 0.2), 1)
        self.assertEqual(research.nearest_rank([5, 1, 4, 2, 3], 0.5), 3)

    def test_feature_history_is_unchanged_by_future_bars(self):
        spec = json.loads(research.DEFAULT_SPEC.read_text(encoding="utf-8"))
        rows = []
        for index in range(340):
            price = 100 + (index % 17) * 0.1
            rows.append(candle(index, price, price + 1, price - 1, price + 0.2, 10 + index % 5))
        prefix = research.prepare_features(rows[:300], spec)
        full = research.prepare_features(rows, spec)
        self.assertEqual(prefix[250], full[250])


class ResearchExecutionTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(research.DEFAULT_SPEC.read_text(encoding="utf-8"))

    @patch("scripts.research.prepare_features")
    def test_signal_enters_next_bar_and_gap_stop_uses_worse_open(self, prepare_features):
        rows = [
            candle(0, 100, 101, 99, 100),
            candle(1, 100, 101, 99, 100),
            candle(2, 95, 96, 94, 95),
        ]
        prepare_features.return_value = [
            {"atr": 1.0, "long_signal": True, "short_signal": False},
            {"atr": 1.0, "long_signal": False, "short_signal": False},
            {"atr": 1.0, "long_signal": False, "short_signal": False},
        ]
        trades = research.simulate_asset("BTC", rows, [], self.spec)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["signal_time"], rows[0]["end_time"])
        self.assertEqual(trades[0]["entry_time"], rows[1]["time"])
        self.assertEqual(trades[0]["raw_entry"], 100)
        self.assertEqual(trades[0]["initial_stop"], 98)
        self.assertEqual(trades[0]["raw_exit"], 95)
        self.assertEqual(trades[0]["exit_reason"], "stop")

    def test_positive_funding_is_a_cost_to_a_long(self):
        position = {"side": "long", "entry_time": 0, "risk_distance": 10}
        rows = [candle(0, close=100), candle(1, close=100)]
        funding = [{"time": research.INTERVAL_MS, "funding_rate": "0.01"}]
        total, events = research.funding_for_trade(position, research.INTERVAL_MS, rows, funding)
        self.assertAlmostEqual(total, -0.1)
        self.assertEqual(events[0]["type"], "funding")

    def test_cost_scenario_changes_only_slippage_component(self):
        raw = {
            "trade_id": "btc-0001", "asset": "BTC", "side": "long",
            "signal_time": 0, "entry_time": 1, "raw_entry": 100,
            "initial_stop": 98, "exit_time": 2, "raw_exit": 104,
            "exit_reason": "time", "holding_bars": 1, "gross_r": 2,
            "fee_r": 0.045, "slip_r_per_bps": 0.1, "funding_r": -0.01,
            "events": [],
        }
        zero = research.public_trade(deepcopy(raw), 0)
        five = research.public_trade(deepcopy(raw), 5)
        self.assertEqual(zero["gross_r"], five["gross_r"])
        self.assertEqual(zero["fee_r"], five["fee_r"])
        self.assertEqual(zero["funding_r"], five["funding_r"])
        self.assertEqual(zero["net_r"] - five["net_r"], 0.5)


if __name__ == "__main__":
    unittest.main()

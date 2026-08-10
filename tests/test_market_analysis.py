import unittest

from scripts import analyze_market


AS_OF = 20_000 * analyze_market.INTERVALS["15m"]


def provider(payload):
    kind = payload["type"]
    if kind == "metaAndAssetCtxs":
        return [
            {"universe": [{"name": "BTC"}, {"name": "ETH"}]},
            [
                {"markPx": "101", "oraclePx": "100.8", "funding": "0.0001", "openInterest": "1200"},
                {"markPx": "51", "oraclePx": "50.8", "funding": "-0.0001", "openInterest": "2200"},
            ],
        ]
    if kind == "l2Book":
        return {"levels": [[{"px": "100", "sz": "4"}, {"px": "99.9", "sz": "3"}], [{"px": "100.1", "sz": "5"}, {"px": "100.2", "sz": "2"}]]}
    if kind == "candleSnapshot":
        request = payload["req"]
        interval = analyze_market.INTERVALS[request["interval"]]
        rows = []
        for index in range(160):
            start = AS_OF - (160 - index) * interval
            close = 100 + index * 0.1
            rows.append({"t": start, "T": start + interval - 1, "o": str(close - 0.1), "h": str(close + 0.5), "l": str(close - 0.5), "c": str(close), "v": "10"})
        rows.append({"t": AS_OF - interval + 1, "T": AS_OF, "o": "999", "h": "999", "l": "999", "c": "999", "v": "1"})
        return rows
    raise AssertionError(f"unexpected request: {payload}")


class MarketAnalysisTests(unittest.TestCase):
    def test_context_is_read_only_and_uses_closed_candles(self):
        context = analyze_market.build_context(("BTC",), AS_OF, post=provider)
        self.assertEqual(context["classification"], "read-only-market-context")
        self.assertEqual(context["status"], "incomplete")
        self.assertEqual(context["assets"][0]["derived"]["last_close"], 115.9)
        self.assertEqual(context["assets"][0]["observed"]["open_interest_change"], None)
        self.assertEqual(context["playbook_fit"][0]["asset"], "BTC")
        self.assertIn("order placement", context["prohibited_actions"])
        self.assertNotIn("entry", context["assets"][0])

    def test_unknown_playbook_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "unknown playbook IDs"):
            analyze_market.build_context(("BTC",), AS_OF, ["not-a-playbook"], post=provider)

    def test_future_as_of_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "future"):
            analyze_market.build_context(("BTC",), 9_999_999_999_999, post=provider)


if __name__ == "__main__":
    unittest.main()

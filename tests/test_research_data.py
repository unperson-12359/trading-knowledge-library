import unittest
from unittest.mock import patch

from scripts import research


class ResearchDataTests(unittest.TestCase):
    def test_normalize_candles_preserves_source_numbers_and_drops_open_bar(self):
        rows = [
            {"t": 0, "T": 899999, "s": "BTC", "i": "15m", "o": "1.0", "h": "2.0", "l": "0.5", "c": "1.5", "v": "10.25", "n": 4},
            {"t": 900000, "T": 1799999, "s": "BTC", "i": "15m", "o": "1.5", "h": "2.5", "l": "1.0", "c": "2.0", "v": "11", "n": 5},
        ]
        normalized = research.normalize_candles("BTC", rows, closed_before=1500000)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["open"], "1.0")
        self.assertEqual(normalized[0]["volume"], "10.25")

    def test_duplicate_and_gap_detection(self):
        rows = [{"time": 0}, {"time": 900000}, {"time": 900000}, {"time": 2700000}]
        self.assertEqual(research.duplicate_count(rows), 1)
        self.assertEqual(research.gap_count(rows, 900000), 1)

    @patch("scripts.research.time.sleep", return_value=None)
    @patch("scripts.research.post_info")
    def test_funding_pagination_advances_from_last_timestamp(self, post_info, _sleep):
        first = [{"time": index, "coin": "BTC", "fundingRate": "0", "premium": "0"} for index in range(500)]
        second = [{"time": 500, "coin": "BTC", "fundingRate": "0", "premium": "0"}]
        post_info.side_effect = [first, second]
        requests = []
        rows = research.fetch_funding("BTC", 0, 1000, requests)
        self.assertEqual(len(rows), 501)
        self.assertEqual(post_info.call_args_list[1].args[0]["startTime"], 500)
        self.assertEqual(len(requests), 2)


if __name__ == "__main__":
    unittest.main()

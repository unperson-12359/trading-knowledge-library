#!/usr/bin/env python3
"""Build a read-only, LLM-ready Hyperliquid perpetual-market context packet.

The command never accepts credentials, addresses, positions, or order parameters.
It fetches public data only and labels missing or stale context explicitly.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://api.hyperliquid.xyz/info"
ASSETS = ("BTC", "ETH")
INTERVALS = {"15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000, "4h": 4 * 60 * 60 * 1000}
WARNING = (
    "Educational research context only. This packet is not financial advice, a trade "
    "recommendation, position sizing, or an instruction to place an order."
)


def post_info(payload, attempts=3):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(API_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt + 1 == attempts:
                raise RuntimeError(f"Hyperliquid HTTP {exc.code}: {exc.reason}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 == attempts:
                raise RuntimeError(f"Hyperliquid request failed after {attempts} attempts: {exc}") from exc
        time.sleep(min(2 ** attempt, 4))
    raise AssertionError("unreachable")


def closed_candles(asset, interval, as_of, post=post_info, bars=160):
    start = as_of - bars * INTERVALS[interval]
    rows = post({"type": "candleSnapshot", "req": {
        "coin": asset, "interval": interval, "startTime": start, "endTime": as_of,
    }})
    if not isinstance(rows, list):
        raise RuntimeError(f"{asset} {interval} candles are not an array")
    output = []
    for row in rows:
        required = {"t", "T", "o", "h", "l", "c", "v"}
        if not isinstance(row, dict) or not required.issubset(row):
            raise RuntimeError(f"{asset} {interval} candle is malformed")
        if int(row["T"]) >= as_of:
            continue
        output.append({
            "time": int(row["t"]), "end_time": int(row["T"]), "open": float(row["o"]),
            "high": float(row["h"]), "low": float(row["l"]), "close": float(row["c"]),
            "volume": float(row["v"]),
        })
    output.sort(key=lambda row: row["time"])
    if len(output) < 30:
        raise RuntimeError(f"{asset} {interval} has fewer than 30 closed candles")
    return output


def wilder_atr(rows, period=14):
    ranges = []
    for index, row in enumerate(rows):
        previous = rows[index - 1]["close"] if index else row["close"]
        ranges.append(max(row["high"] - row["low"], abs(row["high"] - previous), abs(row["low"] - previous)))
    seed = sum(ranges[:period]) / period
    value = seed
    for item in ranges[period:]:
        value = ((period - 1) * value + item) / period
    return value


def latest_features(rows):
    recent = rows[-14:]
    close = rows[-1]["close"]
    high = max(row["high"] for row in recent)
    low = min(row["low"] for row in recent)
    stochastic = None if high == low else 100 * (close - low) / (high - low)
    vwap_rows = rows[-96:]
    volume = sum(row["volume"] for row in vwap_rows)
    vwap = None if volume <= 0 else sum(((row["high"] + row["low"] + row["close"]) / 3) * row["volume"] for row in vwap_rows) / volume
    returns = [math.log(right["close"] / left["close"]) for left, right in zip(rows[-97:-1], rows[-96:]) if left["close"] > 0]
    realized_volatility = None if len(returns) < 2 else statistics.pstdev(returns) * math.sqrt(len(returns))
    return {
        "last_close": close, "atr_14": wilder_atr(rows), "atr_14_pct": wilder_atr(rows) / close * 100,
        "rolling_vwap_24h": vwap, "stochastic_14": stochastic,
        "return_15m_pct": (close / rows[-2]["close"] - 1) * 100,
        "return_1h_pct": (close / rows[-5]["close"] - 1) * 100,
        "realized_volatility_window": "96 closed 15m bars", "realized_volatility": realized_volatility,
        "anchored_vwap": None,
        "anchored_vwap_status": "unknown: no user-selected anchor was supplied",
    }


def market_context(asset, meta_contexts, post=post_info):
    if not isinstance(meta_contexts, list) or len(meta_contexts) != 2:
        raise RuntimeError("metaAndAssetCtxs returned an unexpected shape")
    meta, contexts = meta_contexts
    universe = meta.get("universe", []) if isinstance(meta, dict) else []
    if not isinstance(contexts, list):
        raise RuntimeError("asset contexts are not an array")
    index = next((i for i, item in enumerate(universe) if item.get("name") == asset), None)
    if index is None or index >= len(contexts) or not isinstance(contexts[index], dict):
        raise RuntimeError(f"{asset} is missing from perpetual asset contexts")
    context = contexts[index]
    required = {"markPx", "oraclePx", "funding", "openInterest"}
    if not required.issubset(context):
        raise RuntimeError(f"{asset} asset context is missing required fields")
    book = post({"type": "l2Book", "coin": asset})
    levels = book.get("levels") if isinstance(book, dict) else None
    if not isinstance(levels, list) or len(levels) != 2 or not levels[0] or not levels[1]:
        raise RuntimeError(f"{asset} L2 book is incomplete")
    bids, asks = levels
    best_bid, best_ask = float(bids[0]["px"]), float(asks[0]["px"])
    midpoint = (best_bid + best_ask) / 2
    return {
        "mark_price": float(context["markPx"]), "oracle_price": float(context["oraclePx"]),
        "funding_rate": float(context["funding"]), "open_interest": float(context["openInterest"]),
        "best_bid": best_bid, "best_ask": best_ask,
        "spread_bps": (best_ask - best_bid) / midpoint * 10000,
        "top_5_bid_size": sum(float(level["sz"]) for level in bids[:5]),
        "top_5_ask_size": sum(float(level["sz"]) for level in asks[:5]),
        "open_interest_change": None,
        "open_interest_change_status": "unknown: this read contains current open interest, not a historical series",
    }


def regime(features, market):
    trend = "range"
    if features["rolling_vwap_24h"] is not None:
        if features["last_close"] > features["rolling_vwap_24h"] and features["return_1h_pct"] > 0:
            trend = "uptrend"
        elif features["last_close"] < features["rolling_vwap_24h"] and features["return_1h_pct"] < 0:
            trend = "downtrend"
        elif abs(features["return_1h_pct"]) > 0.75:
            trend = "transition"
    volatility = "normal"
    if features["atr_14_pct"] >= 2:
        volatility = "shock"
    elif features["atr_14_pct"] >= 1:
        volatility = "expanded"
    elif features["atr_14_pct"] < 0.35:
        volatility = "compressed"
    positioning = "balanced"
    if market["funding_rate"] > 0:
        positioning = "long-crowded"
    elif market["funding_rate"] < 0:
        positioning = "short-crowded"
    return {
        "rule_version": 1,
        "trend": {"state": trend, "basis": "15m close, 1h return, and rolling 24h VWAP"},
        "volatility": {"state": volatility, "basis": "14-period ATR as a percent of latest 15m close"},
        "liquidity": {"state": "observed", "basis": "current L2 spread and top-five displayed sizes; no venue-wide classification"},
        "positioning": {"state": positioning, "basis": "current funding sign only; no open-interest history"},
    }


def concept_ids():
    return [
        "instruments/perpetual-futures-contract", "crypto-and-defi/funding-rate",
        "contract-mechanics/open-interest", "crypto-and-defi/oracle", "microstructure/order-book",
        "microstructure/bid-ask-spread", "microstructure/market-depth", "orders-and-execution/slippage",
        "indicators/volume-weighted-average-price", "indicators/average-true-range",
        "indicators/stochastic-oscillator", "risk-and-performance/realized-volatility",
    ]


def missing_data_for(field):
    value = field.casefold()
    blockers = (
        "liquidation", "trades", "aggregate coverage", "event-anchored",
        "next payment", "constituent health", "open interest and funding",
        "open interest by venue", "funding and open interest",
    )
    if any(term in value for term in blockers):
        return field
    if "session vwap" in value:
        return field
    return None


def playbook_fit(regime_state, selected_ids=None):
    playbooks = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "playbooks").glob("*.json"))]
    if selected_ids:
        unknown = sorted(set(selected_ids) - {item["id"] for item in playbooks})
        if unknown:
            raise RuntimeError("unknown playbook IDs: " + ", ".join(unknown))
        playbooks = [item for item in playbooks if item["id"] in selected_ids]
    tags = {f"trend.{regime_state['trend']['state']}", f"volatility.{regime_state['volatility']['state']}", f"positioning.{regime_state['positioning']['state']}"}
    result = []
    for item in playbooks:
        favored = set(item["regime_profile"]["favored"])
        avoid = set(item["regime_profile"]["avoid"])
        missing = [field for row in item["required_data"]
                   if (field := missing_data_for(row["field"]))]
        result.append({
            "playbook_id": item["id"],
            "classification": "inconclusive",
            "matched_favored_regime_tags": sorted(tags & favored),
            "matched_avoid_regime_tags": sorted(tags & avoid),
            "available_observations": ["closed 15m/1h/4h OHLCV", "current mark/oracle price", "current funding", "current open interest", "current L2 spread and displayed depth"],
            "unmet_required_data": missing,
            "reason": "Regime context is available, but the first release does not evaluate every entry condition, open-interest history, or liquidation/trade feed.",
            "concept_ids": item["concept_ids"], "failure_modes": item["failure_modes"],
        })
    return result


def build_context(assets=ASSETS, as_of=None, selected_playbooks=None, post=post_info):
    as_of = int(as_of or time.time() * 1000)
    if as_of > int(time.time() * 1000) + 60_000:
        raise RuntimeError("as_of cannot be more than one minute in the future")
    meta_contexts = post({"type": "metaAndAssetCtxs"})
    output_assets = []
    incomplete = False
    for asset in assets:
        candles = {interval: closed_candles(asset, interval, as_of, post) for interval in INTERVALS}
        features = latest_features(candles["15m"])
        market = market_context(asset, meta_contexts, post)
        state = regime(features, market)
        output_assets.append({
            "asset": asset, "observed": market, "derived": features, "regime": state,
            "concept_ids": concept_ids(), "closed_bar_end_time": candles["15m"][-1]["end_time"],
        })
        incomplete = incomplete or market["open_interest_change"] is None
    assessments = [
        {"asset": row["asset"], "assessments": playbook_fit(row["regime"], selected_playbooks)}
        for row in output_assets
    ]
    return {
        "$schema": "../schemas/analysis-context.schema.json", "schema_version": 1,
        "classification": "read-only-market-context", "status": "incomplete" if incomplete else "complete",
        "venue": "Hyperliquid", "as_of": as_of,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "assets": output_assets, "playbook_fit": assessments,
        "warnings": [WARNING, "Funding and open interest are venue-specific observations.", "All playbook conclusions remain inconclusive until their full required data and entry conditions are evaluated."],
        "prohibited_actions": ["order placement", "wallet access", "account access", "position sizing", "trade recommendation"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", action="append", choices=ASSETS, dest="assets")
    parser.add_argument("--as-of", type=int, help="UTC epoch milliseconds; defaults to current time")
    parser.add_argument("--playbook", action="append", dest="playbooks")
    parser.add_argument("--output", type=Path, help="Optional explicit output file; no data is saved by default")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON to stdout")
    args = parser.parse_args()
    try:
        context = build_context(tuple(args.assets or ASSETS), args.as_of, args.playbooks)
    except RuntimeError as exc:
        print(json.dumps({"schema_version": 1, "classification": "read-only-market-context", "status": "failed", "error": str(exc), "warnings": [WARNING]}), file=sys.stderr)
        return 1
    payload = json.dumps(context, ensure_ascii=False, indent=2 if args.pretty else None) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())

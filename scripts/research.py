"""Fetch, run, and publish deterministic research artifacts.

Stdlib only. Phase 2 initially exposes the ``fetch`` command; later checkpoints
add the runner and publisher without changing the dataset contract.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
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
DEFAULT_SPEC = ROOT / "research" / "specs" / "atr-volatility-breakout-v1.json"
INTERVAL_MS = 15 * 60 * 1000
HOUR_MS = 60 * 60 * 1000
API_URL = "https://api.hyperliquid.xyz/info"


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_bytes(value)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def post_info(payload, attempts=5):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        API_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, list):
                raise RuntimeError(f"Hyperliquid returned {type(data).__name__}, expected list")
            return data
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt + 1 == attempts:
                raise RuntimeError(f"Hyperliquid HTTP {exc.code}: {exc.reason}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 == attempts:
                raise RuntimeError(f"Hyperliquid request failed after {attempts} attempts: {exc}") from exc
        time.sleep(min(2 ** attempt, 8))
    raise AssertionError("unreachable")


def normalize_candles(asset, rows, closed_before):
    candles = []
    for row in rows:
        required = {"t", "T", "s", "i", "o", "h", "l", "c", "v", "n"}
        if not isinstance(row, dict) or not required.issubset(row):
            raise RuntimeError(f"{asset} candle row is malformed")
        if int(row["T"]) >= closed_before:
            continue
        candles.append({
            "asset": asset,
            "interval": "15m",
            "time": int(row["t"]),
            "end_time": int(row["T"]),
            "open": str(row["o"]),
            "high": str(row["h"]),
            "low": str(row["l"]),
            "close": str(row["c"]),
            "volume": str(row["v"]),
            "trades": int(row["n"]),
        })
    candles.sort(key=lambda row: row["time"])
    return candles


def normalize_funding(asset, rows):
    funding = []
    for row in rows:
        if not isinstance(row, dict) or not {"coin", "fundingRate", "premium", "time"}.issubset(row):
            raise RuntimeError(f"{asset} funding row is malformed")
        funding.append({
            "asset": asset,
            "time": int(row["time"]),
            "funding_rate": str(row["fundingRate"]),
            "premium": str(row["premium"]),
        })
    funding.sort(key=lambda row: row["time"])
    return funding


def duplicate_count(rows):
    timestamps = [row["time"] for row in rows]
    return len(timestamps) - len(set(timestamps))


def gap_count(rows, expected_ms, tolerance_ms=0):
    return sum(
        1 for left, right in zip(rows, rows[1:])
        if right["time"] - left["time"] > expected_ms + tolerance_ms
    )


def fetch_funding(asset, start_time, end_time, request_log):
    cursor = start_time
    collected = []
    while cursor <= end_time:
        payload = {"type": "fundingHistory", "coin": asset, "startTime": cursor, "endTime": end_time}
        page = post_info(payload)
        request_log.append({
            "request_type": "fundingHistory", "asset": asset,
            "start_time": cursor, "end_time": end_time, "source_url": API_URL,
        })
        if not page:
            break
        collected.extend(page)
        last_time = max(int(row["time"]) for row in page)
        if last_time < cursor:
            raise RuntimeError(f"{asset} funding pagination did not advance")
        cursor = last_time + 1
        if len(page) < 500:
            break
        time.sleep(0.25)
    unique = {int(row["time"]): row for row in collected}
    return [unique[key] for key in sorted(unique)]


def fetch_dataset(spec_path, output_root, end_time=None):
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec["data_source"]["provider"] != "Hyperliquid":
        raise RuntimeError("fetch currently supports only Hyperliquid")

    now_ms = int(time.time() * 1000)
    closed_before = (now_ms // INTERVAL_MS) * INTERVAL_MS
    requested_end = int(end_time) if end_time is not None else closed_before - 1
    requested_end = min(requested_end, closed_before - 1)
    requested_start = requested_end - spec["data_source"]["maximum_candles"] * INTERVAL_MS + 1
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    candle_data = {}
    funding_data = {}
    requests = []
    for asset in spec["assets"]:
        candle_payload = {
            "type": "candleSnapshot",
            "req": {"coin": asset, "interval": "15m", "startTime": requested_start, "endTime": requested_end},
        }
        raw_candles = post_info(candle_payload)
        requests.append({
            "request_type": "candleSnapshot", "asset": asset,
            "start_time": requested_start, "end_time": requested_end, "source_url": API_URL,
        })
        candle_data[asset] = normalize_candles(asset, raw_candles, closed_before)
        raw_funding = fetch_funding(asset, requested_start, requested_end, requests)
        funding_data[asset] = normalize_funding(asset, raw_funding)

    if any(not candle_data[asset] or not funding_data[asset] for asset in spec["assets"]):
        raise RuntimeError("dataset is missing candles or funding")
    effective_start = max(candle_data[asset][0]["time"] for asset in spec["assets"])
    effective_end = min(candle_data[asset][-1]["end_time"] for asset in spec["assets"])
    stamp = datetime.fromtimestamp(effective_end / 1000, tz=timezone.utc).strftime("%Y%m%dT%H%MZ")
    dataset_id = f"hyperliquid-mainnet-btc-eth-15m-{stamp}"
    dataset_dir = output_root / dataset_id
    if dataset_dir.exists():
        raise RuntimeError(f"dataset already exists: {dataset_dir}")

    duplicates = sum(duplicate_count(candle_data[a]) + duplicate_count(funding_data[a]) for a in spec["assets"])
    missing_intervals = sum(gap_count(candle_data[a], INTERVAL_MS) for a in spec["assets"])
    funding_gaps = sum(gap_count(funding_data[a], HOUR_MS, tolerance_ms=5 * 60 * 1000) for a in spec["assets"])
    quality_valid = duplicates == 0 and missing_intervals == 0 and funding_gaps == 0

    files = []
    for asset in spec["assets"]:
        candle_path = dataset_dir / f"{asset.lower()}-15m-candles.json"
        candle_doc = {"schema_version": 1, "provider": "Hyperliquid", "asset": asset, "interval": "15m", "candles": candle_data[asset]}
        candle_hash = write_json(candle_path, candle_doc)
        files.append({"asset": asset, "kind": "candles", "path": candle_path.name, "rows": len(candle_data[asset]), "sha256": candle_hash})

        funding_path = dataset_dir / f"{asset.lower()}-funding.json"
        funding_doc = {"schema_version": 1, "provider": "Hyperliquid", "asset": asset, "cadence": "1h", "funding": funding_data[asset]}
        funding_hash = write_json(funding_path, funding_doc)
        files.append({"asset": asset, "kind": "funding", "path": funding_path.name, "rows": len(funding_data[asset]), "sha256": funding_hash})

    dataset_hash = sha256_bytes("\n".join(item["sha256"] for item in sorted(files, key=lambda item: item["path"])).encode("ascii"))
    manifest = {
        "$schema": "https://unperson-12359.github.io/trading-knowledge-library/schemas/dataset-manifest.schema.json",
        "dataset_id": dataset_id,
        "schema_version": 1,
        "provider": "Hyperliquid",
        "network": "mainnet",
        "retrieved_at": retrieved_at,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "assets": spec["assets"],
        "files": files,
        "requests": requests,
        "quality": {
            "valid": quality_valid,
            "closed_candles_only": all(row["end_time"] < closed_before for asset in spec["assets"] for row in candle_data[asset]),
            "duplicates": duplicates,
            "missing_intervals": missing_intervals,
            "funding_gaps": funding_gaps,
            "notes": [
                "The official candle endpoint is limited to the most recent 5000 candles.",
                "Missing market intervals are not forward-filled.",
                "Funding timestamps may differ from the exact hour by a small publication delay."
            ],
        },
        "dataset_sha256": dataset_hash,
        "warning": "Hyperliquid exposes only the most recent 5000 candles. This snapshot is preliminary and does not represent a full market cycle."
    }
    manifest_path = dataset_dir / "dataset-manifest.json"
    write_json(manifest_path, manifest)
    if not quality_valid:
        raise RuntimeError(f"dataset quality gate failed; inspect {manifest_path}")
    print(f"dataset={dataset_id} candles={sum(len(v) for v in candle_data.values())} funding={sum(len(v) for v in funding_data.values())} sha256={dataset_hash}")
    return dataset_dir


def load_dataset(dataset_dir):
    manifest_path = dataset_dir / "dataset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verified = []
    candles = {}
    funding = {}
    for item in sorted(manifest["files"], key=lambda value: value["path"]):
        path = dataset_dir / item["path"]
        payload = path.read_bytes()
        digest = sha256_bytes(payload)
        if digest != item["sha256"]:
            raise RuntimeError(f"dataset hash mismatch: {path}")
        verified.append(digest)
        document = json.loads(payload.decode("utf-8"))
        if item["kind"] == "candles":
            candles[item["asset"]] = document["candles"]
        else:
            funding[item["asset"]] = document["funding"]
    aggregate = sha256_bytes("\n".join(verified).encode("ascii"))
    if aggregate != manifest["dataset_sha256"]:
        raise RuntimeError("aggregate dataset hash mismatch")
    if manifest["quality"]["valid"] is not True:
        raise RuntimeError("dataset quality gate is not valid")
    return manifest, candles, funding


def wilder_atr(candles, period):
    true_ranges = []
    for index, candle in enumerate(candles):
        high, low = float(candle["high"]), float(candle["low"])
        if index == 0:
            true_ranges.append(high - low)
        else:
            previous_close = float(candles[index - 1]["close"])
            true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    values = [None] * len(candles)
    if len(candles) < period:
        return values
    values[period - 1] = sum(true_ranges[:period]) / period
    for index in range(period, len(candles)):
        values[index] = (values[index - 1] * (period - 1) + true_ranges[index]) / period
    return values


def ema(values, period):
    result = [None] * len(values)
    if len(values) < period:
        return result
    result[period - 1] = sum(values[:period]) / period
    alpha = 2.0 / (period + 1.0)
    for index in range(period, len(values)):
        result[index] = alpha * values[index] + (1 - alpha) * result[index - 1]
    return result


def nearest_rank(values, quantile):
    if not values:
        raise ValueError("nearest_rank needs at least one value")
    ordered = sorted(values)
    rank = max(1, math.ceil(quantile * len(ordered)))
    return ordered[rank - 1]


def aggregate_candles(candles, timeframe_ms):
    buckets = {}
    for candle in candles:
        bucket = candle["time"] // timeframe_ms * timeframe_ms
        buckets.setdefault(bucket, []).append(candle)
    expected = timeframe_ms // INTERVAL_MS
    aggregated = []
    for bucket in sorted(buckets):
        rows = sorted(buckets[bucket], key=lambda value: value["time"])
        if len(rows) != expected or rows[-1]["end_time"] != bucket + timeframe_ms - 1:
            continue
        aggregated.append({
            "time": bucket,
            "end_time": bucket + timeframe_ms - 1,
            "open": float(rows[0]["open"]),
            "high": max(float(row["high"]) for row in rows),
            "low": min(float(row["low"]) for row in rows),
            "close": float(rows[-1]["close"]),
            "volume": sum(float(row["volume"]) for row in rows),
        })
    return aggregated


def context_states(candles, period, slope_lookback):
    states = {}
    for name, timeframe_ms in (("1h", 4 * INTERVAL_MS), ("4h", 16 * INTERVAL_MS)):
        rows = aggregate_candles(candles, timeframe_ms)
        averages = ema([row["close"] for row in rows], period)
        values = []
        for index, row in enumerate(rows):
            bearish = bullish = False
            if index >= period - 1 + slope_lookback and averages[index] is not None:
                slope = averages[index] - averages[index - slope_lookback]
                bearish = row["close"] < averages[index] and slope < 0
                bullish = row["close"] > averages[index] and slope > 0
            values.append({"end_time": row["end_time"], "bearish": bearish, "bullish": bullish})
        states[name] = values
    return states


def latest_context_state(states, timeframe, end_time):
    rows = states[timeframe]
    times = [row["end_time"] for row in rows]
    index = bisect.bisect_right(times, end_time) - 1
    return rows[index] if index >= 0 else {"bearish": False, "bullish": False}


def prepare_features(candles, spec):
    indicators = spec["indicators"]
    atr = wilder_atr(candles, indicators["atr"]["period_bars"])
    normalized = [
        None if value is None else value / float(candle["close"])
        for value, candle in zip(atr, candles)
    ]
    states = context_states(
        candles,
        indicators["context_trend"]["ema_period_bars"],
        indicators["context_trend"]["slope_lookback_bars"],
    )
    compression_lookback = indicators["compression"]["lookback_bars"]
    breakout_lookback = indicators["breakout"]["lookback_bars"]
    volume_lookback = indicators["volume"]["lookback_bars"]
    features = []
    for index, candle in enumerate(candles):
        feature = {"atr": atr[index], "long_signal": False, "short_signal": False}
        if atr[index] is None or index < max(compression_lookback, breakout_lookback, volume_lookback):
            features.append(feature)
            continue
        history = normalized[index - compression_lookback:index]
        if any(value is None for value in history):
            features.append(feature)
            continue
        threshold = nearest_rank(history, indicators["compression"]["quantile"])
        compressed = normalized[index] <= threshold
        prior = candles[index - breakout_lookback:index]
        prior_high = max(float(row["high"]) for row in prior)
        prior_low = min(float(row["low"]) for row in prior)
        volume_median = statistics.median(float(row["volume"]) for row in candles[index - volume_lookback:index])
        close = float(candle["close"])
        volume_ok = float(candle["volume"]) > volume_median
        one_hour = latest_context_state(states, "1h", candle["end_time"])
        four_hour = latest_context_state(states, "4h", candle["end_time"])
        established_downtrend = one_hour["bearish"] and four_hour["bearish"]
        established_uptrend = one_hour["bullish"] and four_hour["bullish"]
        confirmation = indicators["breakout"]["confirmation_atr"] * atr[index]
        feature.update({
            "compressed": compressed,
            "compression_threshold": threshold,
            "prior_high": prior_high,
            "prior_low": prior_low,
            "volume_median": volume_median,
            "established_downtrend": established_downtrend,
            "established_uptrend": established_uptrend,
            "long_signal": compressed and volume_ok and close > prior_high + confirmation and not established_downtrend,
            "short_signal": compressed and volume_ok and close < prior_low - confirmation and not established_uptrend,
        })
        features.append(feature)
    return features


def price_string(value):
    return f"{value:.10f}".rstrip("0").rstrip(".")


def funding_for_trade(position, exit_time, candles, funding):
    candle_ends = [row["end_time"] for row in candles]
    side_value = 1 if position["side"] == "long" else -1
    total = 0.0
    events = []
    for row in funding:
        timestamp = row["time"]
        if not (position["entry_time"] < timestamp <= exit_time):
            continue
        candle_index = bisect.bisect_right(candle_ends, timestamp) - 1
        if candle_index < 0:
            continue
        proxy = float(candles[candle_index]["close"])
        rate = float(row["funding_rate"])
        funding_r = -side_value * rate * proxy / position["risk_distance"]
        total += funding_r
        events.append({
            "type": "funding", "time": timestamp, "rate": row["funding_rate"],
            "price_proxy": price_string(proxy), "funding_r": round(funding_r, 12),
        })
    return total, events


def finalize_trade(position, exit_time, raw_exit, reason, holding_bars, candles, funding, fee_bps):
    side_value = 1 if position["side"] == "long" else -1
    risk = position["risk_distance"]
    gross_r = side_value * (raw_exit - position["raw_entry"]) / risk
    fee_r = (position["raw_entry"] + raw_exit) * fee_bps / 10000.0 / risk
    slip_r_per_bps = (position["raw_entry"] + raw_exit) / 10000.0 / risk
    funding_r, funding_events = funding_for_trade(position, exit_time, candles, funding)
    events = [*position["events"], *funding_events, {
        "type": "exit", "time": exit_time, "reason": reason,
        "raw_price": price_string(raw_exit),
    }]
    return {
        "trade_id": position["trade_id"], "asset": position["asset"],
        "side": position["side"], "signal_time": position["signal_time"],
        "entry_time": position["entry_time"], "raw_entry": position["raw_entry"],
        "initial_stop": position["initial_stop"], "exit_time": exit_time,
        "raw_exit": raw_exit, "exit_reason": reason, "holding_bars": holding_bars,
        "gross_r": gross_r, "fee_r": fee_r, "slip_r_per_bps": slip_r_per_bps,
        "funding_r": funding_r, "events": events,
    }


def simulate_asset(asset, candles, funding, spec):
    features = prepare_features(candles, spec)
    execution = spec["execution"]
    fee_bps = spec["costs"]["taker_fee_bps"]
    trades = []
    position = None
    pending = None
    trade_number = 0

    for index, candle in enumerate(candles):
        raw_open = float(candle["open"])
        raw_high = float(candle["high"])
        raw_low = float(candle["low"])
        raw_close = float(candle["close"])

        if pending is not None and position is None:
            trade_number += 1
            side = pending["side"]
            risk_distance = execution["initial_stop_atr"] * pending["atr"]
            initial_stop = raw_open - risk_distance if side == "long" else raw_open + risk_distance
            position = {
                "trade_id": f"{asset.lower()}-{trade_number:04d}", "asset": asset,
                "side": side, "signal_time": pending["signal_time"],
                "entry_time": candle["time"], "entry_index": index,
                "raw_entry": raw_open, "risk_distance": risk_distance,
                "initial_stop": initial_stop, "active_stop": initial_stop,
                "best_close": raw_open,
                "events": [
                    {"type": "signal", "time": pending["signal_time"], "side": side},
                    {"type": "entry", "time": candle["time"], "raw_price": price_string(raw_open)},
                    {"type": "initial-stop", "active_time": candle["time"], "price": price_string(initial_stop)},
                ],
            }
            pending = None

        exited = False
        if position is not None:
            stop = position["active_stop"]
            if position["side"] == "long" and raw_low <= stop:
                raw_exit = min(stop, raw_open)
                reason = "stop"
                exited = True
            elif position["side"] == "short" and raw_high >= stop:
                raw_exit = max(stop, raw_open)
                reason = "stop"
                exited = True
            elif index - position["entry_index"] >= execution["maximum_holding_bars"]:
                raw_exit = raw_open
                reason = "time"
                exited = True

            if exited:
                trades.append(finalize_trade(
                    position, candle["time"], raw_exit, reason,
                    index - position["entry_index"], candles, funding, fee_bps,
                ))
                position = None
            else:
                atr_value = features[index]["atr"]
                if atr_value is not None:
                    if position["side"] == "long":
                        position["best_close"] = max(position["best_close"], raw_close)
                        candidate = position["best_close"] - execution["trailing_stop_atr"] * atr_value
                        new_stop = max(position["active_stop"], candidate)
                    else:
                        position["best_close"] = min(position["best_close"], raw_close)
                        candidate = position["best_close"] + execution["trailing_stop_atr"] * atr_value
                        new_stop = min(position["active_stop"], candidate)
                    if new_stop != position["active_stop"]:
                        active_time = candles[index + 1]["time"] if index + 1 < len(candles) else candle["end_time"] + 1
                        position["events"].append({
                            "type": "trailing-stop-update", "decision_time": candle["end_time"],
                            "active_time": active_time, "price": price_string(new_stop),
                        })
                        position["active_stop"] = new_stop

        if position is None and pending is None and index + 1 < len(candles):
            feature = features[index]
            if feature.get("long_signal"):
                pending = {"side": "long", "signal_time": candle["end_time"], "atr": feature["atr"]}
            elif feature.get("short_signal"):
                pending = {"side": "short", "signal_time": candle["end_time"], "atr": feature["atr"]}

    if position is not None:
        last = candles[-1]
        trades.append(finalize_trade(
            position, last["end_time"], float(last["close"]), "end-of-data",
            len(candles) - 1 - position["entry_index"], candles, funding, fee_bps,
        ))
    return trades


def public_trade(trade, slippage_bps):
    side_value = 1 if trade["side"] == "long" else -1
    entry_price = trade["raw_entry"] * (1 + side_value * slippage_bps / 10000.0)
    exit_price = trade["raw_exit"] * (1 - side_value * slippage_bps / 10000.0)
    slippage_r = trade["slip_r_per_bps"] * slippage_bps
    net_r = trade["gross_r"] - trade["fee_r"] - slippage_r + trade["funding_r"]
    return {
        "trade_id": trade["trade_id"], "asset": trade["asset"], "side": trade["side"],
        "signal_time": trade["signal_time"], "entry_time": trade["entry_time"],
        "entry_price": price_string(entry_price), "initial_stop": price_string(trade["initial_stop"]),
        "exit_time": trade["exit_time"], "exit_price": price_string(exit_price),
        "exit_reason": trade["exit_reason"], "holding_bars": trade["holding_bars"],
        "gross_r": round(trade["gross_r"], 12), "fee_r": round(trade["fee_r"], 12),
        "slippage_r": round(slippage_r, 12), "funding_r": round(trade["funding_r"], 12),
        "net_r": round(net_r, 12), "events": trade["events"],
    }


def basic_metrics(trades, total_bars):
    values = [trade["net_r"] for trade in trades]
    gross = [trade["gross_r"] for trade in trades]
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
    wins = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    return {
        "trade_count": len(trades),
        "gross_expectancy_r": round(statistics.mean(gross), 10) if gross else None,
        "net_expectancy_r": round(statistics.mean(values), 10) if values else None,
        "win_rate": round(sum(value > 0 for value in values) / len(values), 10) if values else None,
        "median_r": round(statistics.median(values), 10) if values else None,
        "profit_factor": round(wins / losses, 10) if losses else None,
        "maximum_drawdown_r": round(max_drawdown, 10),
        "exposure_fraction": round(sum(trade["holding_bars"] for trade in trades) / total_bars, 10) if total_bars else 0.0,
        "fee_r": round(sum(trade["fee_r"] for trade in trades), 10),
        "slippage_r": round(sum(trade["slippage_r"] for trade in trades), 10),
        "funding_r": round(sum(trade["funding_r"] for trade in trades), 10),
    }


def scenario_metrics(trades, total_bars, effective_start, effective_end, holdout_fraction, segment_days):
    metrics = basic_metrics(trades, total_bars)
    metrics["long_short_split"] = {
        side: basic_metrics([trade for trade in trades if trade["side"] == side], total_bars)
        for side in ("long", "short")
    }
    metrics["asset_split"] = {
        asset: basic_metrics([trade for trade in trades if trade["asset"] == asset], total_bars // 2)
        for asset in ("BTC", "ETH")
    }
    cutoff = effective_start + int((effective_end - effective_start) * (1 - holdout_fraction))
    metrics["holdout_start"] = cutoff
    metrics["holdout"] = basic_metrics([trade for trade in trades if trade["entry_time"] >= cutoff], max(1, int(total_bars * holdout_fraction)))
    segment_ms = segment_days * 24 * HOUR_MS
    segments = []
    cursor = effective_start
    while cursor <= effective_end:
        end = min(cursor + segment_ms - 1, effective_end)
        segment_trades = [trade for trade in trades if cursor <= trade["entry_time"] <= end]
        segment = basic_metrics(segment_trades, max(1, int((end - cursor + 1) / INTERVAL_MS) * 2))
        segment.update({"start": cursor, "end": end})
        segments.append(segment)
        cursor = end + 1
    metrics["seven_day_segments"] = segments
    return metrics


def run_research(spec_path, dataset_dir, output_root):
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes.decode("utf-8"))
    spec_hash = sha256_bytes(spec_bytes)
    manifest, candle_sets, funding_sets = load_dataset(dataset_dir)
    raw_trades = []
    for asset in spec["assets"]:
        raw_trades.extend(simulate_asset(asset, candle_sets[asset], funding_sets[asset], spec))
    raw_trades.sort(key=lambda trade: (trade["entry_time"], trade["asset"], trade["trade_id"]))

    run_hash = sha256_bytes(f"{spec_hash}:{manifest['dataset_sha256']}".encode("ascii"))[:12]
    run_id = f"{spec['id']}-{manifest['dataset_id']}-{run_hash}"
    result_dir = output_root / run_id
    if result_dir.exists():
        raise RuntimeError(f"research result already exists: {result_dir}")
    result_dir.mkdir(parents=True)

    headline_bps = spec["costs"]["headline_slippage_bps"]
    headline_trades = [public_trade(trade, headline_bps) for trade in raw_trades]
    trade_log = {
        "$schema": "https://unperson-12359.github.io/trading-knowledge-library/schemas/trade-log.schema.json",
        "schema_version": 1, "run_id": run_id, "spec_id": spec["id"],
        "dataset_id": manifest["dataset_id"], "slippage_bps": headline_bps,
        "trades": headline_trades,
    }
    write_json(result_dir / "trades.json", trade_log)

    scenarios = []
    total_bars = sum(len(candle_sets[asset]) for asset in spec["assets"])
    for slippage_bps in spec["costs"]["slippage_scenarios_bps"]:
        scenario_trades = [public_trade(trade, slippage_bps) for trade in raw_trades]
        scenarios.append({
            "slippage_bps": slippage_bps,
            "headline": slippage_bps == headline_bps,
            "metrics": scenario_metrics(
                scenario_trades, total_bars, manifest["effective_start"], manifest["effective_end"],
                spec["evaluation"]["holdout_fraction"], spec["evaluation"]["segment_days"],
            ),
            "trade_log_path": "trades.json" if slippage_bps == headline_bps else None,
        })
    headline_metrics = next(item["metrics"] for item in scenarios if item["headline"])
    status = "preliminary" if headline_metrics["trade_count"] >= spec["evaluation"]["minimum_conclusive_trades"] else "inconclusive"
    result = {
        "$schema": "https://unperson-12359.github.io/trading-knowledge-library/schemas/research-result.schema.json",
        "schema_version": 1, "run_id": run_id,
        "created_at": manifest["retrieved_at"],
        "classification": "preliminary-limited-window-research",
        "status": status,
        "spec": {"id": spec["id"], "version": spec["version"], "sha256": spec_hash, "path": f"../../specs/{spec_path.name}"},
        "dataset": {"id": manifest["dataset_id"], "sha256": manifest["dataset_sha256"], "manifest_path": f"../../datasets/{manifest['dataset_id']}/dataset-manifest.json", "effective_start": manifest["effective_start"], "effective_end": manifest["effective_end"]},
        "headline_scenario": headline_bps,
        "scenarios": scenarios,
        "data_quality": manifest["quality"],
        "warnings": [
            spec["warning"],
            manifest["warning"],
            "Bar data cannot reproduce intrabar order sequence or historical order-book impact.",
            "Funding notional uses the latest closed 15-minute close as a price proxy.",
            "The chronological holdout is descriptive because the specification was not developed under a formally sealed process."
        ],
    }
    write_json(result_dir / "result.json", result)
    print(f"run={run_id} status={status} trades={headline_metrics['trade_count']} net_expectancy_r={headline_metrics['net_expectancy_r']}")
    return result_dir


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch = subparsers.add_parser("fetch", help="Fetch an immutable Hyperliquid dataset snapshot")
    fetch.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    fetch.add_argument("--output-root", type=Path, default=ROOT / "research" / "datasets")
    fetch.add_argument("--end-time", type=int, help="Optional inclusive epoch-millisecond end time")
    run = subparsers.add_parser("run", help="Run a frozen spec against an immutable dataset")
    run.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    run.add_argument("--dataset", type=Path, help="Dataset directory; defaults to the sole local snapshot")
    run.add_argument("--output-root", type=Path, default=ROOT / "research" / "results")
    return parser


def sole_dataset():
    root = ROOT / "research" / "datasets"
    datasets = sorted(path for path in root.iterdir() if path.is_dir())
    if len(datasets) != 1:
        raise RuntimeError(f"expected exactly one dataset snapshot, found {len(datasets)}")
    return datasets[0]


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "fetch":
            fetch_dataset(args.spec.resolve(), args.output_root.resolve(), args.end_time)
        elif args.command == "run":
            dataset = args.dataset.resolve() if args.dataset else sole_dataset()
            run_research(args.spec.resolve(), dataset, args.output_root.resolve())
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"research error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Fetch, run, and publish deterministic research artifacts.

Stdlib only. Phase 2 initially exposes the ``fetch`` command; later checkpoints
add the runner and publisher without changing the dataset contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch = subparsers.add_parser("fetch", help="Fetch an immutable Hyperliquid dataset snapshot")
    fetch.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    fetch.add_argument("--output-root", type=Path, default=ROOT / "research" / "datasets")
    fetch.add_argument("--end-time", type=int, help="Optional inclusive epoch-millisecond end time")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "fetch":
            fetch_dataset(args.spec.resolve(), args.output_root.resolve(), args.end_time)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"research error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

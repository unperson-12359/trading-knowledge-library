#!/usr/bin/env python3
"""Create a machine-readable, read-only citation accessibility audit."""

import argparse
import concurrent.futures
import json
import socket
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "audits" / "citation-audit.json"
USER_AGENT = "PakupaiCitationAudit/1.0 (+https://github.com/unperson-12359/trading-knowledge-library)"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def authority_for(url, policy):
    return policy["host_tiers"].get(urlparse(url).netloc.casefold(), policy["default_tier"])


def classify_http(status):
    if 200 <= status < 400:
        return "reachable"
    if status in {401, 403}:
        return "access-blocked"
    if status == 429:
        return "rate-limited"
    if status in {404, 410}:
        return "broken"
    return "transient-failure"


def probe(url, timeout):
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Range": "bytes=0-4095",
            "Accept": "text/html,application/json,application/pdf;q=0.8,*/*;q=0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return {"access_status": classify_http(response.status), "http_status": response.status,
                    "resolved_url": response.geturl(), "content_type": response.headers.get_content_type()}
    except HTTPError as exc:
        # Some citation hosts return a spurious 404 to partial-content probes but
        # serve the same URL after an ordinary browser-style redirect. Verify a
        # permanent-failure response once before calling it broken.
        if exc.code in {404, 410}:
            try:
                fallback = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(fallback, timeout=timeout) as response:
                    redirected = urlparse(response.geturl()).netloc.casefold()
                    original = urlparse(url).netloc.casefold()
                    return {
                        "access_status": "reachable" if redirected == original else "access-blocked",
                        "http_status": response.status, "resolved_url": response.geturl(),
                        "content_type": response.headers.get_content_type(),
                    }
            except (HTTPError, URLError, socket.timeout, TimeoutError, OSError):
                pass
        return {"access_status": classify_http(exc.code), "http_status": exc.code,
                "resolved_url": exc.url, "content_type": exc.headers.get_content_type() if exc.headers else None}
    except (URLError, socket.timeout, TimeoutError, OSError) as exc:
        return {"access_status": "transient-failure", "error": type(exc).__name__}


def citations():
    rows = {}
    for path in sorted((ROOT / "concepts").glob("*.json")):
        for concept in read_json(path):
            for citation in concept["citations"]:
                row = rows.setdefault(citation["url"], {
                    "url": citation["url"], "source": citation["source"], "concept_ids": [],
                    "citation_count": 0,
                })
                row["concept_ids"].append(concept["id"])
                row["citation_count"] += 1
    return rows


def audit(timeout=15, workers=12):
    policy = read_json(ROOT / "sources" / "source-policy.json")
    rows = citations()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(lambda value: probe(value, timeout), rows)
        for row, result in zip(rows.values(), results):
            row["concept_ids"] = sorted(set(row["concept_ids"]))
            row["authority_tier"] = authority_for(row["url"], policy)
            row.update(result)
    ordered = sorted(rows.values(), key=lambda item: item["url"])
    counts = Counter(item["access_status"] for item in ordered)
    return {
        "$schema": "../schemas/citation-audit.schema.json",
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "policy": {
            "permanent_failure_statuses": [404, 410],
            "blocked_statuses": [401, 403],
            "rate_limited_status": 429,
        },
        "summary": {
            "unique_urls": len(ordered), "concept_citations": sum(item["citation_count"] for item in ordered),
            "access_status_counts": dict(sorted(counts.items())),
            "broken_urls": [item["url"] for item in ordered if item["access_status"] == "broken"],
        },
        "citations": ordered,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    result = audit(args.timeout, args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 1 if result["summary"]["broken_urls"] else 0


if __name__ == "__main__":
    sys.exit(main())

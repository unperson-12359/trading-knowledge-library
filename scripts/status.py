"""Cheap status scan of the library. Reads JSON only, prints a summary.

Usage: python scripts/status.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "A trading concept within"


def main():
    tot = rev = ph = 0
    print(f"{'domain':44} {'n':>4} {'rev':>4} {'prov':>4} {'placeh':>6}  state")
    for p in sorted((ROOT / "concepts").glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"{p.stem:44} CORRUPT")
            continue
        n = len(data)
        r = sum(1 for e in data if e["status"] == "reviewed")
        w = sum(1 for e in data if e["definition"].startswith(PLACEHOLDER))
        state = "DONE" if (r == n and w == 0) else ("partial" if r else "untouched")
        print(f"{p.stem:44} {n:>4} {r:>4} {n - r:>4} {w:>6}  {state}")
        tot += n
        rev += r
        ph += w
    print(f"\nTOTAL entries={tot} reviewed={rev} provisional={tot - rev} placeholders={ph}")


if __name__ == "__main__":
    sys.exit(main())

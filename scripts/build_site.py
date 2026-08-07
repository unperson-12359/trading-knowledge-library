"""Build a static site from concepts/*.json into docs/ (GitHub Pages source).

Stdlib only. Generates:
  docs/index.html        status dashboard + domain links
  docs/<domain-slug>.html  one page per domain with all entries rendered
"""
import html
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONCEPTS = ROOT / "concepts"
DOCS = ROOT / "docs"

CSS = """
body{font-family:Georgia,serif;max-width:860px;margin:0 auto;padding:2rem 1rem;color:#1a1a1a;line-height:1.55}
a{color:#0b5fff;text-decoration:none}a:hover{text-decoration:underline}
h1{border-bottom:3px solid #111;padding-bottom:.3rem}
h2{margin-top:2rem}
.badge{display:inline-block;font-size:.72rem;font-weight:bold;padding:.1rem .45rem;border-radius:.7rem;vertical-align:middle;text-transform:uppercase;font-family:system-ui}
.reviewed{background:#d8f3dc;color:#1b4332}.provisional{background:#fff3cd;color:#7f6000}
.trusted{background:#cfe2ff;color:#084298}.disputed{background:#f8d7da;color:#842029}
.entry{border-bottom:1px solid #ddd;padding:1rem 0}
.entry h3{margin:0 0 .3rem}
.field{margin:.25rem 0}.label{font-weight:bold;font-family:system-ui;font-size:.8rem;text-transform:uppercase;color:#555}
.formula{font-family:Consolas,monospace;background:#f4f4f4;padding:.4rem .6rem;border-radius:4px}
.bar{background:#eee;border-radius:6px;overflow:hidden;height:1.2rem;margin:.3rem 0 1rem}
.bar>div{background:#2d6a4f;height:100%}
table{border-collapse:collapse;width:100%;font-family:system-ui;font-size:.9rem}
td,th{border-bottom:1px solid #ddd;padding:.35rem .5rem;text-align:left}
.meta{color:#666;font-size:.85rem;font-family:system-ui}
ul.rel{margin:.2rem 0;padding-left:1.2rem}
"""

FIELDS = [("intuition", "Intuition"), ("mechanics", "Mechanics"),
          ("failure_modes", "Failure modes"), ("misconceptions", "Misconceptions"),
          ("example", "Example")]


def esc(s):
    return html.escape(str(s))


def render_entry(e):
    parts = [f'<div class="entry"><h3>{esc(e["name"])} '
             f'<span class="badge {esc(e["status"])}">{esc(e["status"])}</span></h3>']
    parts.append(f'<div class="field">{esc(e["definition"])}</div>')
    for key, label in FIELDS:
        if e.get(key):
            parts.append(f'<div class="field"><span class="label">{label}:</span> {esc(e[key])}</div>')
    if e.get("formula"):
        parts.append(f'<div class="formula">{esc(e["formula"])}</div>')
    if e.get("aliases"):
        parts.append(f'<div class="field"><span class="label">Aliases:</span> {esc(", ".join(e["aliases"]))}</div>')
    if e.get("relationships"):
        rel = "".join(f"<li>{esc(r)}</li>" for r in e["relationships"])
        parts.append(f'<div class="field"><span class="label">Related:</span><ul class="rel">{rel}</ul></div>')
    for c in e.get("citations", []):
        url = esc(c.get("url", ""))
        sec = f' — {esc(c["section"])}' if c.get("section") else ""
        parts.append(f'<div class="field"><span class="label">Source:</span> '
                     f'<a href="{url}">{esc(c.get("source", url))}</a>{sec}</div>')
    if e.get("review_note"):
        parts.append(f'<div class="meta">Note: {esc(e["review_note"])}</div>')
    parts.append("</div>")
    return "\n".join(parts)


def page(title, body):
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{body}"
            f"<p class='meta'>Generated {date.today().isoformat()} by scripts/build_site.py · "
            f"<a href='https://github.com/unperson-12359/trading-knowledge-library'>GitHub repo</a></p>"
            f"</body></html>")


def main():
    DOCS.mkdir(exist_ok=True)
    domains = []
    for p in sorted(CONCEPTS.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        domains.append((p.stem, data))

    total = sum(len(d) for _, d in domains)
    reviewed = sum(1 for _, d in domains for e in d if e["status"] == "reviewed")
    pct = round(100 * reviewed / total)

    rows = []
    for slug, data in domains:
        n = len(data)
        r = sum(1 for e in data if e["status"] == "reviewed")
        rows.append(f"<tr><td><a href='{slug}.html'>{esc(data[0]['domain'])}</a></td>"
                    f"<td>{n}</td><td>{r}</td><td>{n - r}</td></tr>")
        entries_html = "\n".join(render_entry(e) for e in data)
        body = (f"<p><a href='index.html'>&larr; Library index</a></p>"
                f"<h1>{esc(data[0]['domain'])}</h1>"
                f"<p class='meta'>{n} concepts · {r} reviewed</p>{entries_html}")
        (DOCS / f"{slug}.html").write_text(page(data[0]["domain"], body), encoding="utf-8")

    index_body = (
        "<h1>Pakupai Trading Knowledge Library</h1>"
        "<p>A machine-readable, source-verified knowledge base of trading concepts. "
        "Every reviewed entry carries an exact citation to an authoritative source. "
        "This is Phase 1 of Pakupai: the knowledge foundation for AI-native trading.</p>"
        f"<p><strong>{reviewed} of {total} concepts reviewed ({pct}%)</strong></p>"
        f"<div class='bar'><div style='width:{pct}%'></div></div>"
        "<p class='meta'>Trust levels: <span class='badge reviewed'>reviewed</span> verified against an "
        "authoritative source with exact citation · <span class='badge provisional'>provisional</span> "
        "working definition awaiting citation-level review</p>"
        "<h2>Domains</h2>"
        "<table><tr><th>Domain</th><th>Concepts</th><th>Reviewed</th><th>Provisional</th></tr>"
        + "".join(rows) + "</table>")
    (DOCS / "index.html").write_text(page("Pakupai Trading Knowledge Library", index_body),
                                     encoding="utf-8")
    print(f"site built: {len(domains) + 1} pages, {total} entries, {reviewed} reviewed ({pct}%)")


if __name__ == "__main__":
    sys.exit(main())

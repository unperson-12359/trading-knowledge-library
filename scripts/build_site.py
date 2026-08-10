"""Build the static site from concepts/*.json into docs/ (GitHub Pages source).

Stdlib only. Generates:
  docs/index.html              dashboard + domain table + search
  docs/about.html              AI disclosure and project methodology
  docs/all.html                A-Z index of every concept
  docs/<slug>/index.html       domain page 1 (25 entries/page)
  docs/<slug>/page-N.html      further domain pages
  docs/search-index.json       client-side search data
  docs/sitemap.xml             every generated page

Navigation: sidebar with all domains on every page, breadcrumbs, prev/next
domain links, full pager (First/Prev/numbered/Next/Last), rel=prev/next,
internal link checker (build fails if any internal href is broken).
"""
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONCEPTS = ROOT / "concepts"
DOCS = ROOT / "docs"
BASE = "https://unperson-12359.github.io/trading-knowledge-library"
PER_PAGE = 25

CSS = """
*{box-sizing:border-box}
body{font-family:Georgia,serif;margin:0;color:#1a1a1a;line-height:1.55;display:flex;min-height:100vh}
a{color:#0b5fff;text-decoration:none}a:hover{text-decoration:underline}
nav#sidebar{width:250px;flex-shrink:0;background:#f7f7f5;border-right:1px solid #e2e2e0;padding:1rem;position:sticky;top:0;height:100vh;overflow-y:auto;font-family:system-ui;font-size:.85rem}
nav#sidebar h2{font-size:.95rem;margin:.2rem 0 .6rem}
nav#sidebar ul{list-style:none;margin:0;padding:0}
nav#sidebar li{margin:.1rem 0}
nav#sidebar a{display:block;padding:.18rem .4rem;border-radius:4px;color:#333}
nav#sidebar a.active{background:#2d6a4f;color:#fff;font-weight:600}
nav#sidebar a:hover{background:#e6e6e2;text-decoration:none}
nav#sidebar a.active:hover{background:#2d6a4f}
nav#sidebar .count{color:#888;font-size:.75rem}
nav#sidebar a.active .count{color:#cfe8d8}
main{flex:1;padding:1.5rem 2rem;max-width:900px;min-width:0}
h1{border-bottom:3px solid #111;padding-bottom:.3rem;font-size:1.6rem}
.crumbs{font-family:system-ui;font-size:.8rem;color:#666;margin-bottom:1rem}
.crumbs a{color:#666}
.entry{border-bottom:1px solid #ddd;padding:1rem 0}
.entry h3{margin:0 0 .3rem;font-size:1.1rem}
.entry h3 .anchor{color:#bbb;font-size:.8rem}
.field{margin:.25rem 0}.label{font-weight:bold;font-family:system-ui;font-size:.75rem;text-transform:uppercase;color:#555}
.formula{font-family:Consolas,monospace;background:#f4f4f4;padding:.4rem .6rem;border-radius:4px;font-size:.9rem;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-family:system-ui;font-size:.88rem}
td,th{border-bottom:1px solid #ddd;padding:.3rem .5rem;text-align:left}
.meta{color:#666;font-size:.82rem;font-family:system-ui}
ul.rel{margin:.2rem 0;padding-left:1.2rem}
.pager{display:flex;gap:.3rem;flex-wrap:wrap;align-items:center;margin:1.2rem 0;font-family:system-ui;font-size:.85rem}
.pager a,.pager span.cur{padding:.25rem .6rem;border:1px solid #ccc;border-radius:4px}
.pager a:hover{background:#f0f0ee;text-decoration:none}
.pager span.cur{background:#2d6a4f;color:#fff;border-color:#2d6a4f;font-weight:600}
.pager span.gap{border:none}
.showing{font-family:system-ui;font-size:.8rem;color:#666}
.domainnav{display:flex;justify-content:space-between;margin-top:2rem;font-family:system-ui;font-size:.85rem}
.toc{columns:2;font-family:system-ui;font-size:.82rem;background:#fafaf8;border:1px solid #e8e8e5;border-radius:6px;padding:.8rem 1rem}
.toc a{color:#333}
#search{width:100%;padding:.4rem .6rem;border:1px solid #ccc;border-radius:6px;font-size:.9rem;margin-bottom:.6rem;font-family:system-ui}
#search-results{list-style:none;margin:0 0 .8rem;padding:0}
#search-results li{padding:.25rem .4rem;border-bottom:1px solid #eee}
#search-results .sr-domain{color:#888;font-size:.72rem}
@media(max-width:820px){
 body{display:block}
 nav#sidebar{width:100%;height:auto;position:static;border-right:none;border-bottom:1px solid #e2e2e0}
 nav#sidebar details.tocwrap:not([open]) .navlist{display:none}
 main{padding:1rem}
 .toc{columns:1}
}
"""

SEARCH_JS = """
(function(){
  var box=document.getElementById('search'),res=document.getElementById('search-results');
  if(!box||!res)return;var idx=null;
  function load(){if(idx)return Promise.resolve(idx);
    return fetch(box.getAttribute('data-index')).then(function(r){return r.json()}).then(function(d){idx=d;return d});}
  box.addEventListener('input',function(){
    var q=box.value.trim().toLowerCase();res.innerHTML='';
    if(q.length<2)return;
    load().then(function(data){
      var hits=data.filter(function(e){return e.n.toLowerCase().indexOf(q)!==-1}).slice(0,12);
      res.innerHTML=hits.map(function(e){
        return '<li><a href="'+e.u+'">'+e.n+'</a> <span class="sr-domain">'+e.d+'</span></li>';
      }).join('')||'<li class="meta">No matches</li>';
    });
  });
})();
"""

FIELDS = [("intuition", "Intuition"), ("mechanics", "Mechanics"),
          ("failure_modes", "Failure modes"), ("misconceptions", "Misconceptions"),
          ("example", "Example")]


def esc(s):
    return html.escape(str(s), quote=True)


def anchor(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def render_entry(e, prefix):
    parts = [f'<article class="entry" id="{anchor(e["name"])}"><h3>{esc(e["name"])} '
             f'<a class="anchor" href="#{anchor(e["name"])}">#</a></h3>']
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
                     f'<a href="{url}" rel="noopener">{esc(c.get("source", url))}</a>{sec}</div>')
    parts.append("</article>")
    return "\n".join(parts)


def page(title, body, prefix, slug, domains, extra_head="", description=""):
    links = []
    for s, d in domains:
        active = ' class="active"' if s == slug else ""
        links.append(f'<li><a href="{prefix}{s}/"{active}>{esc(d[0]["domain"])} '
                     f'<span class="count">{len(d)}</span></a></li>')
    nav = (f'<nav id="sidebar" aria-label="Domains">'
           f'<h2><a href="{prefix}index.html" style="color:#111">Trading Library</a></h2>'
           f'<input id="search" type="search" placeholder="Search 1,500 concepts…" '
           f'data-index="{prefix}search-index.json" aria-label="Search concepts">'
           f'<ul id="search-results"></ul>'
           f'<details class="tocwrap" open><summary class="meta">Domains</summary>'
           f'<ul class="navlist"><li><a href="{prefix}all.html"'
           + (' class="active"' if slug == "all" else "")
           + f'>A–Z index</a></li><li><a href="{prefix}about.html"'
           + (' class="active"' if slug == "about" else "")
           + f'>About &amp; Methodology</a></li>{"".join(links)}</ul></details></nav>')
    desc = f'<meta name="description" content="{esc(description)}">' if description else ""
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title>{desc}{extra_head}<style>{CSS}</style></head>"
            f"<body>{nav}<main>{body}"
            f"<p class='meta'>Generated {date.today().isoformat()} · "
            f"<a href='{prefix}about.html'>About &amp; Methodology</a> · "
            f"<a href='https://github.com/unperson-12359/trading-knowledge-library'>GitHub</a></p>"
            f"</main><script>{SEARCH_JS}</script></body></html>")


def pager(slug, page_no, n_pages, prefix=""):
    if n_pages <= 1:
        return ""
    def href(p):
        return f"{prefix}index.html" if p == 1 else f"{prefix}page-{p}.html"
    items = []
    if page_no > 1:
        items.append(f'<a href="{href(1)}" rel="first">First</a>')
        items.append(f'<a href="{href(page_no - 1)}" rel="prev">Prev</a>')
    nums = sorted({1, n_pages, *range(max(1, page_no - 2), min(n_pages, page_no + 2) + 1)})
    last = 0
    for p in nums:
        if p - last > 1:
            items.append('<span class="gap">…</span>')
        items.append(f'<span class="cur" aria-current="page">{p}</span>' if p == page_no
                     else f'<a href="{href(p)}">{p}</a>')
        last = p
    if page_no < n_pages:
        items.append(f'<a href="{href(page_no + 1)}" rel="next">Next</a>')
        items.append(f'<a href="{href(n_pages)}" rel="last">Last</a>')
    return f'<div class="pager" role="navigation" aria-label="Pagination">{"".join(items)}</div>'


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()

    domains = []
    for p in sorted(CONCEPTS.glob("*.json")):
        domains.append((p.stem, json.loads(p.read_text(encoding="utf-8"))))

    total = sum(len(d) for _, d in domains)
    written = set()      # relative paths of generated pages, for the link checker
    search_index = []    # {n, d, u}
    az = {}              # letter -> [(name, url)]

    # ---- domain pages (paginated) ----
    for di, (slug, data) in enumerate(domains):
        n = len(data)
        n_pages = max(1, (n + PER_PAGE - 1) // PER_PAGE)
        ddir = DOCS / slug
        ddir.mkdir()
        prev_slug = domains[di - 1][0] if di > 0 else None
        next_slug = domains[di + 1][0] if di + 1 < len(domains) else None
        toc = '<div class="toc">' + "".join(
            f'<div><a href="#{anchor(e["name"])}">{esc(e["name"])}</a></div>' for e in data) + "</div>"

        for pno in range(1, n_pages + 1):
            chunk = data[(pno - 1) * PER_PAGE: pno * PER_PAGE]
            fname = "index.html" if pno == 1 else f"page-{pno}.html"
            for e in chunk:
                url = f"{slug}/" if pno == 1 else f"{slug}/page-{pno}.html"
                url += f"#{anchor(e['name'])}"
                search_index.append({"n": e["name"], "d": data[0]["domain"],
                                     "u": url})
                az.setdefault(e["name"][0].upper(), []).append((e["name"], url))

            lo, hi = (pno - 1) * PER_PAGE + 1, min(n, pno * PER_PAGE)
            crumbs = (f'<div class="crumbs"><a href="../index.html">Home</a> / '
                      f'<a href="./">{esc(data[0]["domain"])}</a>'
                      + (f' / page {pno}' if pno > 1 else "") + "</div>")
            head = ""
            if pno > 1:
                head += f'<link rel="prev" href="{"./" if pno == 2 else f"page-{pno-1}.html"}">'
            if pno < n_pages:
                head += f'<link rel="next" href="page-{pno+1}.html">'
            domnav = '<div class="domainnav">'
            domnav += (f'<a href="../{prev_slug}/">&larr; {esc(domains[di-1][1][0]["domain"])}</a>'
                       if prev_slug else "<span></span>")
            domnav += (f'<a href="../{next_slug}/">{esc(domains[di+1][1][0]["domain"])} &rarr;</a>'
                       if next_slug else "<span></span>")
            domnav += "</div>"

            body = (crumbs + f"<h1>{esc(data[0]['domain'])}</h1>"
                    f'<p class="meta">{n} concepts · '
                    f'<span class="showing">showing {lo}–{hi} of {n}</span></p>'
                    + (toc if pno == 1 else "")
                    + pager(slug, pno, n_pages)
                    + "\n".join(render_entry(e, "../") for e in chunk)
                    + pager(slug, pno, n_pages) + domnav)
            title = f"{data[0]['domain']}" + (f" — page {pno}" if pno > 1 else "")
            (ddir / fname).write_text(
                page(title, body, "../", slug, domains, extra_head=head,
                     description=f"{data[0]['domain']}: {n} trading concepts with citations."),
                encoding="utf-8")
            written.add(f"{slug}/{fname}")

    # ---- A-Z index ----
    letters = sorted(az)
    alpha_nav = " ".join(f'<a href="#L-{l}">{l}</a>' for l in letters)
    az_body = ['<div class="crumbs"><a href="index.html">Home</a> / A–Z index</div>',
               f"<h1>All {total} concepts, A–Z</h1>",
               f'<div class="pager">{alpha_nav}</div>']
    for l in letters:
        az_body.append(f'<h2 id="L-{l}">{l}</h2><ul>')
        for name, url in sorted(az[l], key=lambda x: x[0].lower()):
            az_body.append(f'<li><a href="{url}">{esc(name)}</a></li>')
        az_body.append("</ul>")
    (DOCS / "all.html").write_text(
        page("A–Z index", "\n".join(az_body), "", "all", domains), encoding="utf-8")
    written.add("all.html")

    # ---- index / dashboard ----
    rows = []
    for slug, data in domains:
        n = len(data)
        rows.append(f"<tr><td><a href='{slug}/'>{esc(data[0]['domain'])}</a></td>"
                    f"<td>{n}</td></tr>")
    index_body = (
        '<div class="crumbs">Home</div>'
        "<h1>Pakupai Trading Knowledge Library</h1>"
        "<p>A machine-readable library of trading concepts with definitions, mechanics, "
        "failure modes, misconceptions, examples, relationships, and citations. "
        "Phase 1 of Pakupai: the knowledge foundation for AI-native trading.</p>"
        f"<p><strong>{total} concepts across {len(domains)} domains</strong></p>"
        "<p class='meta'>Built with AI systems. Read the "
        "<a href='about.html'>About &amp; Methodology</a> disclosure before using the material.</p>"
        "<h2>Domains</h2>"
        "<table><tr><th>Domain</th><th>Concepts</th></tr>"
        + "".join(rows) + "</table>")
    (DOCS / "index.html").write_text(
        page("Pakupai Trading Knowledge Library", index_body, "", "", domains,
             description="AI-built trading knowledge library: 1,500 concepts with citations."),
        encoding="utf-8")
    written.add("index.html")

    # ---- about / methodology ----
    about_body = (
        '<div class="crumbs"><a href="index.html">Home</a> / About &amp; Methodology</div>'
        "<h1>About &amp; Methodology</h1>"
        "<h2>AI disclosure</h2>"
        "<p>This project is built and maintained with AI systems. AI is used to research, "
        "draft, organize, and update the material. The content may contain errors or "
        "omissions; inspect the cited sources and verify critical information independently. "
        "Nothing here is financial advice, a recommendation, or evidence that a trading "
        "setup is profitable.</p>"
        "<h2>How the library is organized</h2>"
        "<p>The canonical data lives in structured JSON. This website and the text export are "
        "generated from that data. Entries emphasize mechanics, failure modes, misconceptions, "
        "worked examples, relationships, and direct citations.</p>"
        "<h2>Source policy</h2>"
        "<p>Direct regulatory, exchange, protocol, technical, and canonical research sources "
        "are preferred. Secondary sources are used when direct material is unavailable. A "
        "citation supports a definition or mechanism; it does not demonstrate profitability.</p>"
        "<h2>Use responsibly</h2>"
        "<p>Market rules, venue mechanics, and software behavior change. Verify time-sensitive "
        "details against current official documentation before relying on them.</p>")
    (DOCS / "about.html").write_text(
        page("About & Methodology", about_body, "", "about", domains,
             description="AI disclosure and methodology for the Pakupai Trading Knowledge Library."),
        encoding="utf-8")
    written.add("about.html")

    # ---- search index + sitemap ----
    (DOCS / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    urls = [f"{BASE}/{w.replace('index.html', '')}" for w in sorted(written)]
    (DOCS / "sitemap.xml").write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>\n"
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n",
        encoding="utf-8")

    # ---- internal link checker ----
    href_re = re.compile(r'href="([^"#]+)(#[^"]*)?"')
    broken = []
    for rel in written:
        fpath = DOCS / rel
        text = re.sub(r"<script>.*?</script>", "", fpath.read_text(encoding="utf-8"),
                      flags=re.DOTALL)
        for m in href_re.finditer(text):
            target = m.group(1)
            if target.startswith(("http", "mailto")):
                continue
            resolved = (fpath.parent / target).resolve()
            if target.endswith("/"):
                resolved = resolved / "index.html"
            elif resolved.is_dir():
                resolved = resolved / "index.html"
            if not resolved.exists():
                broken.append(f"{rel} -> {target}")
    assert not broken, f"broken internal links:\n" + "\n".join(broken[:20])

    print(f"site built: {len(written)} pages, {total} entries, 0 broken links")


if __name__ == "__main__":
    sys.exit(main())

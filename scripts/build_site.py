"""Build the static site from concepts/*.json into docs/ (GitHub Pages source).

Stdlib only. Generates:
  docs/index.html              dashboard + domain table + search
  docs/about.html              AI disclosure and project methodology
  docs/playbooks/              research playbook index + detail pages
  docs/research/               executable research index + result reports
  docs/all.html                A-Z index of every concept
  docs/<slug>/index.html       domain page 1 (25 entries/page)
  docs/<slug>/page-N.html      further domain pages
  docs/api/v1/regimes.json     regime taxonomy + core annotations
  docs/api/v1/playbooks.json   all research playbook objects
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
from datetime import date, datetime, timezone
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
.warning{background:#fff4d6;border-left:4px solid #d97706;padding:.75rem 1rem;font-family:system-ui;font-size:.88rem}
.tag{display:inline-block;background:#edf2f7;border-radius:999px;padding:.12rem .5rem;margin:.1rem;font-family:system-ui;font-size:.75rem}
.playbook-card{border:1px solid #ddd;border-radius:6px;padding:.8rem 1rem;margin:.8rem 0}
.playbook-card h2{margin:.1rem 0 .35rem;font-size:1.15rem}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;margin:1rem 0}
.metric{border:1px solid #ddd;border-radius:6px;padding:.65rem;background:#fafaf8;font-family:system-ui}
.metric strong{display:block;font-size:1.15rem}.metric span{font-size:.72rem;color:#666}
.negative{color:#a61b1b}.positive{color:#176b35}
.json{white-space:pre-wrap;background:#f4f4f4;padding:.7rem;border-radius:4px;font-family:Consolas,monospace;font-size:.8rem}
.query-controls{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:.55rem;margin:1rem 0;font-family:system-ui}
.query-controls input,.query-controls select{width:100%;padding:.5rem;border:1px solid #bbb;border-radius:5px;background:#fff}
.query-controls label{font-size:.78rem;color:#555}.query-controls .check{display:flex;align-items:end;padding-bottom:.5rem}
.query-result{border-bottom:1px solid #ddd;padding:.8rem 0}.query-result h2{font-size:1.05rem;margin:0 0 .2rem}
.skills-hero{background:#111;color:#fff;border-radius:10px;padding:1.3rem 1.4rem;margin-bottom:1rem}.skills-hero h1{border:0;margin:.1rem 0}.skills-hero p{max-width:680px}.skills-hero a{color:#ffb08a}
.catalog-stat{font-family:system-ui;font-size:1.05rem;margin:.8rem 0}.catalog-stat strong{font-size:1.45rem}
.skill-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem;margin:1rem 0}
.skill-card{border:1px solid #ccc;border-radius:8px;padding:1rem;background:#fff;display:flex;flex-direction:column;min-height:205px}.skill-card:hover{border-color:#d97745;box-shadow:0 3px 12px #0000000d}.skill-card h2{font-family:system-ui;font-size:1.08rem;margin:0 0 .25rem}.skill-card p{margin:.5rem 0;flex:1}.skill-links{font-family:system-ui;font-size:.82rem;border-top:1px solid #eee;padding-top:.55rem}.skill-arrow{float:right;color:#d05f2c}
.skill-identity{border:1px solid #ddd;border-radius:8px;padding:.8rem 1rem;font-family:system-ui;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem;margin:1rem 0}.skill-identity strong{display:block;font-size:.78rem;color:#666}.skill-identity span{overflow-wrap:anywhere}
.use-panel{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:1rem 0}.copy-row{display:flex;gap:.5rem;align-items:start}.copy-row pre{flex:1;margin:0}.copy-button{border:1px solid #aaa;background:#fff;border-radius:5px;padding:.45rem .65rem;cursor:pointer;font-weight:600}.copy-button:hover{background:#f3f3f0}
.source-nav{display:flex;gap:.5rem;flex-wrap:wrap;font-family:system-ui;font-size:.82rem;margin:.8rem 0}.source-nav a{border:1px solid #ccc;border-radius:5px;padding:.25rem .5rem}
.source-file{border:1px solid #ddd;border-radius:7px;margin:.65rem 0;background:#fafaf8}.source-file summary{padding:.7rem .85rem;cursor:pointer;font-family:system-ui;font-weight:700}.source-file pre{border-top:1px solid #ddd;margin:0;border-radius:0;max-height:620px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.evidence-section{border-top:1px solid #ddd;padding-top:.35rem;margin-top:1rem}.citation-list li{margin:.35rem 0}
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
 .query-controls{grid-template-columns:1fr 1fr}
 .metric-grid{grid-template-columns:1fr 1fr}
 .skill-grid{grid-template-columns:1fr}
 .skill-identity{grid-template-columns:1fr}
 .copy-row{display:block}.copy-button{margin-top:.5rem}
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
      var hits=data.filter(function(e){return (e.n+' '+(e.a||'')+' '+(e.x||'')).toLowerCase().indexOf(q)!==-1}).slice(0,12);
      res.innerHTML=hits.map(function(e){
        return '<li><a href="'+e.u+'">'+e.n+'</a> <span class="sr-domain">'+e.d+'</span></li>';
      }).join('')||'<li class="meta">No matches</li>';
    });
  });
})();
"""

QUERY_JS = """
(function(){
  var form=document.getElementById('query-controls'),out=document.getElementById('query-results'),count=document.getElementById('query-count');
  if(!form||!out)return;
  var state={concepts:[],playbooks:[]},fields=['q','type','domain','required_input','regime'];
  function h(s){return String(s).replace(/[&<>\"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]});}
  function applyUrl(){var p=new URLSearchParams(location.search);fields.forEach(function(k){if(p.has(k))form.elements[k].value=p.get(k)});form.elements.core.checked=p.get('core')==='1';}
  function updateUrl(){var p=new URLSearchParams();fields.forEach(function(k){var v=form.elements[k].value.trim();if(v)p.set(k,v)});if(form.elements.core.checked)p.set('core','1');history.replaceState(null,'',location.pathname+(p.toString()?'?'+p:''));}
  function concept(c){return {type:'concept',title:c.name,domain:c.domain,url:c.url,core:c.core,regimes:(c.regime_annotation||{}).regime_relevance||[],required:[],summary:c.definition,text:[c.name,(c.aliases||[]).join(' '),c.definition,c.intuition,c.mechanics,c.failure_modes,c.misconceptions].join(' ').toLowerCase()};}
  function playbook(p){return {type:'playbook',title:p.title,domain:'Research playbooks',url:'playbooks/'+p.id+'.html',core:true,regimes:(p.regime_profile.favored||[]).concat(p.regime_profile.avoid||[]),required:(p.required_data||[]).map(function(x){return x.field}),summary:p.hypothesis,text:[p.title,p.hypothesis,(p.failure_modes||[]).join(' '),(p.concept_ids||[]).join(' ')].join(' ').toLowerCase()};}
  function run(){updateUrl();var q=form.elements.q.value.trim().toLowerCase(),type=form.elements.type.value,domain=form.elements.domain.value,required=form.elements.required_input.value,regime=form.elements.regime.value,core=form.elements.core.checked;
    var rows=state.concepts.map(concept).concat(state.playbooks.map(playbook)).filter(function(x){return (!q||x.text.indexOf(q)!==-1)&&(!type||x.type===type)&&(!domain||x.domain===domain)&&(!core||x.core)&&(!required||x.required.indexOf(required)!==-1)&&(!regime||x.regimes.indexOf(regime)!==-1)}).slice(0,200);
    count.textContent=rows.length+(rows.length===200?' (first 200)':'')+' results';
    out.innerHTML=rows.map(function(x){return '<article class="query-result"><h2><a href="'+h(x.url)+'">'+h(x.title)+'</a></h2><div class="meta">'+h(x.type)+' &middot; '+h(x.domain)+(x.core?' &middot; core':'')+'</div><p>'+h(x.summary)+'</p></article>'}).join('')||'<p>No matching records.</p>';
  }
  applyUrl();Promise.all([fetch('api/v1/concepts.json').then(function(r){return r.json()}),fetch('api/v1/playbooks.json').then(function(r){return r.json()})]).then(function(data){state.concepts=data[0];state.playbooks=data[1];run()});
  form.addEventListener('input',run);form.addEventListener('change',run);form.addEventListener('submit',function(e){e.preventDefault();run()});
})();
"""

SKILLS_JS = """
(function(){
  var form=document.getElementById('skill-controls'),out=document.getElementById('skill-results'),count=document.getElementById('skill-count');
  if(!form||!out)return;var catalog=[];
  function h(s){return String(s==null?'':s).replace(/[&<>\"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]});}
  function render(){var q=form.elements.q.value.trim().toLowerCase(),domain=form.elements.domain.value,core=form.elements.core.checked;
    var rows=catalog.filter(function(x){var text=[x.display_name,x.concept_id,x.description,(x.trigger_phrases||[]).join(' ')].join(' ').toLowerCase();return (!q||text.indexOf(q)!==-1)&&(!domain||x.domain===domain)&&(!core||x.core);});
    count.textContent=rows.length+' of '+catalog.length+' skills';
    out.innerHTML=rows.map(function(x){return '<article class="skill-card"><h2><a href="'+h(x.detail_url)+'">'+h(x.display_name)+'</a><span class="skill-arrow">&rarr;</span></h2><div class="meta">'+h(x.domain)+(x.core?' &middot; core collection':'')+'</div><p>'+h(x.description)+'</p><div class="skill-links"><a href="'+h(x.detail_url)+'">View complete skill</a> &middot; <a href="'+h(x.profile_url)+'">JSON</a></div></article>';}).join('')||(catalog.length?'<p>No skills match these filters.</p>':'<p>The skill catalog is being prepared.</p>');
  }
  fetch('../api/v1/skills.json').then(function(r){return r.json()}).then(function(data){catalog=data.skills||[];var wanted=new URLSearchParams(location.search).get('skill');if(wanted)form.elements.q.value=wanted;render();});
  form.addEventListener('input',render);form.addEventListener('change',render);
})();
"""

COPY_JS = """
(function(){
  document.querySelectorAll('[data-copy]').forEach(function(button){
    button.addEventListener('click',function(){var target=document.getElementById(button.getAttribute('data-copy'));if(!target)return;navigator.clipboard.writeText(target.textContent).then(function(){var old=button.textContent;button.textContent='Copied';setTimeout(function(){button.textContent=old},1400);});});
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


def render_entry(e, prefix, relationship_lookup, concept_urls):
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
        rendered = []
        for relationship in e["relationships"]:
            concept_id = relationship_lookup.get(relationship.casefold())
            if concept_id:
                rendered.append(
                    f'<li><a href="{prefix}{concept_urls[concept_id]}">{esc(relationship)}</a></li>'
                )
            else:
                rendered.append(f"<li>{esc(relationship)}</li>")
        rel = "".join(rendered)
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
           + f'>About &amp; Methodology</a></li><li><a href="{prefix}query.html"'
           + (' class="active"' if slug == "query" else "")
           + f'>Structured query</a></li><li><a href="{prefix}playbooks/"'
           + (' class="active"' if slug == "playbooks" else "")
           + f'>Research playbooks</a></li><li><a href="{prefix}research/"'
           + (' class="active"' if slug == "research" else "")
           + f'>Research results</a></li><li><a href="{prefix}skills/"'
           + (' class="active"' if slug == "skills" else "")
           + f'>Concept skills</a></li>{"".join(links)}</ul></details></nav>')
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


def render_playbook(playbook, prefix, concept_urls, concept_names):
    def items(values):
        return "<ul>" + "".join(f"<li>{esc(value)}</li>" for value in values) + "</ul>"

    concept_links = []
    for concept_id in playbook["concept_ids"]:
        concept_links.append(
            f'<li><a href="{prefix}{concept_urls[concept_id]}">{esc(concept_names[concept_id])}</a></li>'
        )
    data_rows = "".join(
        f'<tr><td>{esc(item["field"])}</td><td>{esc(item["cadence"])}</td>'
        f'<td>{esc(item["freshness"])}</td></tr>' for item in playbook["required_data"]
    )
    favored = "".join(f'<span class="tag">{esc(tag)}</span>' for tag in playbook["regime_profile"]["favored"])
    avoid = "".join(f'<span class="tag">{esc(tag)}</span>' for tag in playbook["regime_profile"]["avoid"])
    return (
        f'<p class="warning"><strong>{esc(playbook["classification"])}</strong><br>{esc(playbook["warning"])}</p>'
        f'<p><strong>Market:</strong> {esc(playbook["market_type"])} &middot; '
        f'<strong>Signal:</strong> {esc(playbook["signal_timeframe"])} &middot; '
        f'<strong>Context:</strong> {esc(", ".join(playbook["context_timeframes"]))}</p>'
        f'<h2>Hypothesis</h2><p>{esc(playbook["hypothesis"])}</p>'
        f'<h2>Regime profile</h2><p><strong>Favored research context:</strong> {favored}</p>'
        f'<p><strong>Avoid:</strong> {avoid}</p>'
        f'<h2>Required data</h2><table><tr><th>Field</th><th>Cadence</th><th>Freshness</th></tr>{data_rows}</table>'
        f'<h2>Parameters to test</h2><div class="json">{esc(json.dumps(playbook["parameters"], ensure_ascii=False, indent=2))}</div>'
        f'<h2>Entry conditions</h2><h3>Long</h3>{items(playbook["entry_conditions"]["long"])}'
        f'<h3>Short</h3>{items(playbook["entry_conditions"]["short"])}'
        f'<h2>Invalidation</h2>{items(playbook["invalidation"])}'
        f'<h2>Exit logic</h2>{items(playbook["exit_logic"])}'
        f'<h2>Cost model</h2><p>{esc(playbook["cost_model"]["notes"])}</p>{items(playbook["cost_model"]["required"])}'
        f'<h2>Risk constraints</h2>{items(playbook["risk_constraints"]["rules"])}'
        f'<h2>Failure modes</h2>{items(playbook["failure_modes"])}'
        f'<h2>Validation plan</h2>{items(playbook["validation_plan"])}'
        f'<h2>Linked concepts</h2><ul>{"".join(concept_links)}</ul>'
    )


def utc_time(milliseconds):
    return datetime.fromtimestamp(
        milliseconds / 1000, timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")


def metric_value(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def metric_card(label, value, css_class=""):
    return (
        f'<div class="metric"><strong class="{css_class}">{esc(value)}</strong>'
        f'<span>{esc(label)}</span></div>'
    )


def research_report(result):
    headline = next(item for item in result["scenarios"] if item["headline"])
    metrics = headline["metrics"]
    expectancy_class = "positive" if (metrics["net_expectancy_r"] or 0) > 0 else "negative"
    cards = "".join([
        metric_card("Trades", str(metrics["trade_count"])),
        metric_card("Net expectancy", f'{metric_value(metrics["net_expectancy_r"])} R', expectancy_class),
        metric_card("Win rate", f'{metric_value(metrics["win_rate"] * 100, 1)}%'),
        metric_card("Maximum drawdown", f'{metric_value(metrics["maximum_drawdown_r"])} R', "negative"),
    ])
    scenario_rows = "".join(
        "<tr>"
        f'<td>{scenario["slippage_bps"]:.1f} bps{" (headline)" if scenario["headline"] else ""}</td>'
        f'<td>{scenario["metrics"]["trade_count"]}</td>'
        f'<td>{metric_value(scenario["metrics"]["gross_expectancy_r"])}</td>'
        f'<td>{metric_value(scenario["metrics"]["net_expectancy_r"])}</td>'
        f'<td>{metric_value(scenario["metrics"]["maximum_drawdown_r"])}</td>'
        f'<td>{metric_value(scenario["metrics"]["holdout"]["net_expectancy_r"])}</td>'
        "</tr>" for scenario in result["scenarios"]
    )
    split_rows = "".join(
        f'<tr><td>{esc(label)}</td><td>{values["trade_count"]}</td>'
        f'<td>{metric_value(values["net_expectancy_r"])}</td>'
        f'<td>{metric_value(values["win_rate"] * 100, 1) + "%" if values["win_rate"] is not None else "n/a"}</td></tr>'
        for label, values in [
            ("BTC", metrics["asset_split"]["BTC"]),
            ("ETH", metrics["asset_split"]["ETH"]),
            ("Long", metrics["long_short_split"]["long"]),
            ("Short", metrics["long_short_split"]["short"]),
            ("Chronological holdout", metrics["holdout"]),
        ]
    )
    segment_rows = "".join(
        f'<tr><td>{utc_time(segment["start"])}</td><td>{utc_time(segment["end"])}</td>'
        f'<td>{segment["trade_count"]}</td><td>{metric_value(segment["net_expectancy_r"])}</td>'
        f'<td>{metric_value(segment["maximum_drawdown_r"])}</td></tr>'
        for segment in metrics["seven_day_segments"]
    )
    if metrics["net_expectancy_r"] > 0:
        interpretation = (
            "The modeled net expectancy is positive in the headline scenario. "
            "This remains preliminary and does not establish future profitability."
        )
    else:
        interpretation = (
            "The modeled net expectancy is negative in the headline scenario and in this "
            "run's other slippage scenarios. This frozen configuration did not show "
            "profitability in the sampled window."
        )
    warnings = "".join(f"<li>{esc(warning)}</li>" for warning in result["warnings"])
    run_id = result["run_id"]
    dataset_id = result["dataset"]["id"]
    return (
        f'<div class="crumbs"><a href="../index.html">Home</a> / '
        f'<a href="./">Research results</a> / {esc(run_id)}</div>'
        '<h1>ATR Volatility Breakout: first executable study</h1>'
        f'<p class="warning"><strong>{esc(result["status"].title())} limited-window research.</strong> '
        'Not validated, not financial advice, and not evidence of profitability.</p>'
        f'<p class="meta">Run <code>{esc(run_id)}</code><br>'
        f'Generated from immutable inputs on {esc(result["created_at"])}.</p>'
        f'<div class="metric-grid">{cards}</div>'
        '<h2>Plain-language result</h2>'
        f'<p>{esc(interpretation)}</p>'
        '<p>The rules were frozen before the market snapshot and canonical run were produced. '
        'No parameter search was performed by this engine. Results use 15-minute bars, so '
        'intrabar order sequence and historical order-book impact cannot be reconstructed.</p>'
        '<h2>Dataset and run contract</h2>'
        '<table><tr><th>Field</th><th>Value</th></tr>'
        '<tr><td>Market data</td><td>Hyperliquid mainnet BTC and ETH perpetuals</td></tr>'
        f'<tr><td>Window</td><td>{utc_time(result["dataset"]["effective_start"])} through '
        f'{utc_time(result["dataset"]["effective_end"])}</td></tr>'
        f'<tr><td>Dataset hash</td><td><code>{esc(result["dataset"]["sha256"])}</code></td></tr>'
        f'<tr><td>Spec hash</td><td><code>{esc(result["spec"]["sha256"])}</code></td></tr>'
        f'<tr><td>Headline costs</td><td>4.5 bps taker fee per side + '
        f'{result["headline_scenario"]:.1f} bps slippage per side + historical funding</td></tr></table>'
        '<h2>Cost sensitivity</h2>'
        '<table><tr><th>Slippage / side</th><th>Trades</th><th>Gross exp. R</th>'
        '<th>Net exp. R</th><th>Max DD R</th><th>Holdout exp. R</th></tr>'
        f'{scenario_rows}</table>'
        '<h2>Headline breakdown</h2>'
        '<table><tr><th>Slice</th><th>Trades</th><th>Net exp. R</th><th>Win rate</th></tr>'
        f'{split_rows}</table>'
        '<h2>Seven-day stability segments</h2>'
        '<table><tr><th>Start</th><th>End</th><th>Trades</th><th>Net exp. R</th>'
        f'<th>Max DD R</th></tr>{segment_rows}</table>'
        '<h2>Machine-readable evidence</h2><ul>'
        f'<li><a href="../api/v1/results/{esc(run_id)}/result.json">Complete result JSON</a></li>'
        f'<li><a href="../api/v1/results/{esc(run_id)}/trades.json">Headline trade log JSON</a></li>'
        '<li><a href="../api/v1/research-specs.json">Frozen executable specification JSON</a></li>'
        f'<li><a href="../api/v1/datasets/{esc(dataset_id)}/dataset-manifest.json">'
        'Dataset manifest JSON</a></li></ul>'
        f'<h2>Required caveats</h2><ul>{warnings}</ul>'
    )


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    shutil.copytree(ROOT / "schemas", DOCS / "schemas")

    domains = []
    for p in sorted(CONCEPTS.glob("*.json")):
        domains.append((p.stem, json.loads(p.read_text(encoding="utf-8"))))

    total = sum(len(d) for _, d in domains)
    playbooks = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "playbooks").glob("*.json"))
    ]
    research_specs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "research" / "specs").glob("*.json"))
    ]
    dataset_manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "research" / "datasets").glob("*/dataset-manifest.json"))
    ]
    research_results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "research" / "results").glob("*/result.json"))
    ]
    taxonomy = json.loads((ROOT / "regimes" / "taxonomy.json").read_text(encoding="utf-8"))
    core_collection = json.loads(
        (ROOT / "collections" / "core-perps.json").read_text(encoding="utf-8")
    )
    skill_manifest = json.loads(
        (ROOT / "skills" / "manifest.json").read_text(encoding="utf-8")
    )
    skill_progress = json.loads(
        (ROOT / "skills" / "progress.json").read_text(encoding="utf-8")
    )
    skill_architecture = json.loads(
        (ROOT / "skills" / "architecture.json").read_text(encoding="utf-8")
    )
    written = set()      # relative paths of generated pages, for the link checker
    search_index = []    # {n, d, u}
    az = {}              # letter -> [(name, url)]
    concept_urls = {}
    concept_names = {}
    concept_by_id = {}
    term_ids = {}
    for slug, data in domains:
        for index, entry in enumerate(data):
            page_no = index // PER_PAGE + 1
            url = f"{slug}/" if page_no == 1 else f"{slug}/page-{page_no}.html"
            url += f"#{anchor(entry['name'])}"
            concept_urls[entry["id"]] = url
            concept_names[entry["id"]] = entry["name"]
            concept_by_id[entry["id"]] = entry
            for term in [entry["name"], *entry.get("aliases", [])]:
                term_ids.setdefault(term.casefold(), set()).add(entry["id"])
    relationship_lookup = {
        term: next(iter(ids_for_term))
        for term, ids_for_term in term_ids.items() if len(ids_for_term) == 1
    }
    unresolved_relationships = sorted({
        relationship for _, data in domains for entry in data
        for relationship in entry.get("relationships", [])
        if relationship.casefold() not in relationship_lookup
    })

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
                search_index.append({
                    "n": e["name"], "d": data[0]["domain"], "u": url,
                    "a": " ".join(e.get("aliases", [])),
                    "x": " ".join([e.get("definition", ""), e.get("intuition", "")]),
                })
                concept_urls[e["id"]] = url
                concept_names[e["id"]] = e["name"]
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
                    + "\n".join(
                        render_entry(e, "../", relationship_lookup, concept_urls)
                        for e in chunk
                    )
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
        "<p><a href='query.html'><strong>Open the structured query</strong></a> &middot; "
        "<a href='playbooks/'>Browse research playbooks</a> &middot; "
        "<a href='research/'>View executable research</a> &middot; "
        "<a href='skills/'>Browse concept skills</a> &middot; "
        "<a href='api/v1/manifest.json'>API manifest</a></p>"
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
        "worked examples, relationships, and direct citations. The structured query and static "
        "JSON API are dependency-free generated views of the same canonical material.</p>"
        "<p>Executable studies keep frozen research specifications, immutable hashed datasets, "
        "deterministic trade logs, and reported metrics as separate JSON records. Human-readable "
        "research pages are generated from those same records and do not replace them.</p>"
        "<p>The concept-skill layer uses one discoverable repository router plus individually "
        "installable catalog packages. Each package contains a concise SKILL.md, a machine-readable "
        "skill profile, and a self-contained JSON reference tied to canonical concept data by hash. "
        "The JSON concept catalog remains the factual source of truth.</p>"
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

    # ---- structured query ----
    domain_options = "".join(
        f'<option value="{esc(data[0]["domain"])}">{esc(data[0]["domain"])}</option>'
        for _, data in domains
    )
    required_inputs = sorted({
        item["field"] for playbook in playbooks for item in playbook["required_data"]
    })
    required_options = "".join(
        f'<option value="{esc(value)}">{esc(value)}</option>' for value in required_inputs
    )
    regime_tags = [
        f'{dimension["id"]}.{state["id"]}'
        for dimension in taxonomy["dimensions"] for state in dimension["states"]
    ]
    regime_options = "".join(
        f'<option value="{esc(value)}">{esc(value)}</option>' for value in regime_tags
    )
    query_body = (
        '<div class="crumbs"><a href="index.html">Home</a> / Structured query</div>'
        '<h1>Structured knowledge query</h1>'
        '<p>Search concepts and research playbooks, then narrow by type, domain, core membership, required data, or regime context. The URL updates as you filter so a query can be shared.</p>'
        '<form id="query-controls" class="query-controls">'
        '<label>Search<input name="q" type="search" placeholder="funding liquidation VWAP..."></label>'
        '<label>Record type<select name="type"><option value="">All types</option><option value="concept">Concept</option><option value="playbook">Playbook</option></select></label>'
        f'<label>Domain<select name="domain"><option value="">All domains</option><option value="Research playbooks">Research playbooks</option>{domain_options}</select></label>'
        f'<label>Regime<select name="regime"><option value="">All regimes</option>{regime_options}</select></label>'
        f'<label>Required input<select name="required_input"><option value="">Any input</option>{required_options}</select></label>'
        '<label class="check"><input name="core" type="checkbox" style="width:auto;margin-right:.4rem">Core only</label>'
        '</form><p id="query-count" class="meta">Loading structured data...</p><div id="query-results"></div>'
    )
    query_html = page(
        "Structured knowledge query", query_body, "", "query", domains,
        description="Filter trading concepts and untested research playbooks by structured context."
    ).replace("</body>", f"<script>{QUERY_JS}</script></body>")
    (DOCS / "query.html").write_text(query_html, encoding="utf-8")
    written.add("query.html")

    # ---- GitHub-first concept skill catalog ----
    skill_dir = DOCS / "skills"
    skill_dir.mkdir()
    skill_domains = sorted({profile["domain"] for profile in skill_manifest["skills"]})
    skill_domain_options = "".join(
        f'<option value="{esc(value)}">{esc(value)}</option>' for value in skill_domains
    )
    skill_body = (
        '<div class="crumbs"><a href="../index.html">Home</a> / Concept skills</div>'
        '<section class="skills-hero"><h1>Trading Concept Skills</h1>'
        '<p>Browse focused AI-readable skills for explaining and applying trading concepts '
        'with mechanics, failure modes, misconceptions, and citations.</p>'
        f'<p class="catalog-stat"><strong>{skill_progress["completed_count"]}</strong> skills available</p>'
        '<p><a href="../api/v1/skills.json">Machine-readable catalog</a></p></section>'
        '<p class="warning">Built with AI systems. These packages provide educational research '
        'and decision support, not autonomous execution, financial advice, or evidence of profitability.</p>'
        '<h2>Find a skill</h2>'
        '<form id="skill-controls" class="query-controls">'
        '<label>Search<input name="q" type="search" placeholder="funding rate, slippage, margin..."></label>'
        f'<label>Domain<select name="domain"><option value="">All domains</option>{skill_domain_options}</select></label>'
        '<label class="check"><input name="core" type="checkbox" style="width:auto;margin-right:.4rem">Core collection only</label>'
        '</form><p id="skill-count" class="meta">Loading catalog...</p><div id="skill-results" class="skill-grid"></div>'
    )
    skill_html = page(
        "Trading concept skills", skill_body, "../", "skills", domains,
        description="Searchable catalog of GitHub-first, AI-readable trading concept skills.",
    ).replace("</body>", f"<script>{SKILLS_JS}</script></body>")
    (skill_dir / "index.html").write_text(skill_html, encoding="utf-8")
    written.add("skills/index.html")

    # Every catalog item gets a complete human-readable page with its source files.
    skill_by_concept = {
        profile["concept_id"]: profile for profile in skill_manifest["skills"]
    }
    for profile in skill_manifest["skills"]:
        concept = concept_by_id[profile["concept_id"]]
        package = ROOT / profile["package_path"]
        detail_dir = skill_dir / profile["skill_name"]
        detail_dir.mkdir()
        router_prompt = (
            f"Use $tkl-concept-router to find and apply {profile['display_name']} "
            "from the Pakupai Trading Knowledge Library. Separate facts, inferences, "
            "and unknowns; include failure modes, misconceptions, and citations."
        )
        related_links = []
        for related_id in profile["related_concept_ids"]:
            related_skill = skill_by_concept.get(related_id)
            if related_skill:
                related_links.append(
                    f'<li><a href="../{esc(related_skill["skill_name"])}/">'
                    f'{esc(concept_names[related_id])}</a></li>'
                )
            else:
                related_links.append(
                    f'<li><a href="../../{esc(concept_urls[related_id])}">'
                    f'{esc(concept_names[related_id])}</a></li>'
                )
        citations = "".join(
            f'<li><a href="{esc(citation["url"])}" rel="noopener">'
            f'{esc(citation["source"])}</a> — {esc(citation["section"])}</li>'
            for citation in concept["citations"]
        )
        aliases = "".join(
            f'<span class="tag">{esc(alias)}</span>'
            for alias in concept.get("aliases", [])
        )
        formula = (
            f'<div class="field"><span class="label">Formula</span>'
            f'<div class="formula">{esc(concept["formula"])}</div></div>'
            if concept.get("formula") else ""
        )
        skill_source = (package / "SKILL.md").read_text(encoding="utf-8")
        profile_source = (package / "skill.json").read_text(encoding="utf-8")
        agent_source = (package / "agents" / "openai.yaml").read_text(encoding="utf-8")
        reference_source = (package / "references" / "concept.json").read_text(encoding="utf-8")
        github_folder = (
            "https://github.com/unperson-12359/trading-knowledge-library/tree/main/"
            + profile["package_path"]
        )
        related_section = (
            f'<div class="evidence-section"><h3>Related concepts</h3>'
            f'<ul>{"".join(related_links)}</ul></div>' if related_links else ""
        )
        detail_body = (
            '<div class="crumbs"><a href="../../index.html">Home</a> / '
            '<a href="../">Skills</a> / ' + esc(profile["display_name"]) + '</div>'
            f'<h1>{esc(profile["display_name"])}</h1><p>{esc(profile["description"])}</p>'
            f'<div>{aliases}</div>'
            '<div class="skill-identity">'
            f'<div><strong>Skill</strong><span>{esc(profile["skill_name"])}</span></div>'
            f'<div><strong>Domain</strong><span>{esc(profile["domain"])}</span></div>'
            f'<div><strong>Concept ID</strong><span>{esc(profile["concept_id"])}</span></div>'
            '</div>'
            '<h2>Use this skill</h2><div class="use-panel">'
            '<p>Use the catalog router in a repository that includes this library:</p>'
            '<div class="copy-row"><pre id="router-prompt" class="json">'
            + esc(router_prompt) +
            '</pre><button class="copy-button" data-copy="router-prompt">Copy prompt</button></div>'
            '<p class="meta">For a direct repository-local install, copy this package folder to '
            f'<code>.agents/skills/{esc(profile["skill_name"])}/</code>. '
            f'<a href="{esc(github_folder)}">Open the package on GitHub</a>.</p></div>'
            '<h2>Concept evidence</h2>'
            f'<p>{esc(concept["definition"])}</p>'
            f'<div class="field"><span class="label">Intuition</span><p>{esc(concept["intuition"])}</p></div>'
            f'<div class="field"><span class="label">Mechanics</span><p>{esc(concept["mechanics"])}</p></div>'
            + formula +
            f'<div class="evidence-section"><h3>Failure modes</h3><p>{esc(concept["failure_modes"])}</p></div>'
            f'<div class="evidence-section"><h3>Misconceptions</h3><p>{esc(concept["misconceptions"])}</p></div>'
            f'<div class="evidence-section"><h3>Example</h3><p>{esc(concept["example"])}</p></div>'
            f'<div class="evidence-section"><h3>Citations</h3><ul class="citation-list">{citations}</ul></div>'
            + related_section +
            '<h2 id="source-files">Review the source files</h2>'
            '<p>Everything required to inspect or install this skill is available here and in the JSON API.</p>'
            '<nav class="source-nav"><a href="#skill-md">SKILL.md</a>'
            '<a href="#skill-json">skill.json</a><a href="#concept-json">concept.json</a>'
            '<a href="#openai-yaml">openai.yaml</a></nav>'
            f'<details class="source-file" id="skill-md" open><summary>SKILL.md</summary><pre class="json">{esc(skill_source)}</pre></details>'
            f'<details class="source-file" id="skill-json"><summary>skill.json</summary><pre class="json">{esc(profile_source)}</pre></details>'
            f'<details class="source-file" id="concept-json"><summary>references/concept.json</summary><pre class="json">{esc(reference_source)}</pre></details>'
            f'<details class="source-file" id="openai-yaml"><summary>agents/openai.yaml</summary><pre class="json">{esc(agent_source)}</pre></details>'
            f'<p class="skill-links"><a href="../../api/v1/skills/{esc(profile["skill_name"])}.json">'
            f'Open profile JSON</a> &middot; <a href="{esc(github_folder)}">GitHub source</a> &middot; '
            f'<a href="../../{esc(concept_urls[profile["concept_id"]])}">Canonical concept page</a></p>'
        )
        detail_html = page(
            profile["display_name"] + " skill", detail_body, "../../", "skills", domains,
            description=profile["description"],
        ).replace("</body>", f"<script>{COPY_JS}</script></body>")
        (detail_dir / "index.html").write_text(detail_html, encoding="utf-8")
        written.add(f'skills/{profile["skill_name"]}/index.html')

    # ---- research playbooks ----
    playbook_dir = DOCS / "playbooks"
    playbook_dir.mkdir()
    cards = []
    for playbook in playbooks:
        cards.append(
            f'<article class="playbook-card"><h2><a href="{esc(playbook["id"])}.html">'
            f'{esc(playbook["title"])}</a></h2><p>{esc(playbook["hypothesis"])}</p>'
            f'<p class="meta">15m signal &middot; 1h/4h context &middot; untested research hypothesis</p></article>'
        )
        detail_body = (
            f'<div class="crumbs"><a href="../index.html">Home</a> / '
            f'<a href="./">Research playbooks</a> / {esc(playbook["title"])}</div>'
            f'<h1>{esc(playbook["title"])}</h1>'
            + render_playbook(playbook, "../", concept_urls, concept_names)
        )
        detail_name = f'{playbook["id"]}.html'
        (playbook_dir / detail_name).write_text(
            page(playbook["title"], detail_body, "../", "playbooks", domains,
                 description=playbook["hypothesis"]), encoding="utf-8"
        )
        written.add(f"playbooks/{detail_name}")
    playbook_body = (
        '<div class="crumbs"><a href="../index.html">Home</a> / Research playbooks</div>'
        '<h1>Generic Perpetual-Futures Research Playbooks</h1>'
        '<p class="warning">Every playbook is an untested research hypothesis. These are reproducible '
        'study templates, not trade recommendations or evidence of profitability.</p>'
        + "".join(cards)
    )
    (playbook_dir / "index.html").write_text(
        page("Research playbooks", playbook_body, "../", "playbooks", domains,
             description="Five untested generic perpetual-futures research templates."),
        encoding="utf-8"
    )
    written.add("playbooks/index.html")

    # ---- executable research reports ----
    research_dir = DOCS / "research"
    research_dir.mkdir()
    research_cards = []
    for result in research_results:
        headline = next(item for item in result["scenarios"] if item["headline"])
        metrics = headline["metrics"]
        detail_name = f'{result["run_id"]}.html'
        research_cards.append(
            f'<article class="playbook-card"><h2><a href="{esc(detail_name)}">'
            'ATR Volatility Breakout: first executable study</a></h2>'
            f'<p>{metrics["trade_count"]} trades; headline net expectancy '
            f'{metric_value(metrics["net_expectancy_r"])} R after modeled fees, slippage, and funding.</p>'
            f'<p class="meta">{esc(result["status"])} &middot; immutable dataset &middot; '
            'deterministic trade log</p></article>'
        )
        (research_dir / detail_name).write_text(
            page(
                "ATR Volatility Breakout research result",
                research_report(result), "../", "research", domains,
                description="Preliminary executable BTC/ETH perpetual-futures research with complete JSON evidence.",
            ),
            encoding="utf-8",
        )
        written.add(f"research/{detail_name}")
    research_body = (
        '<div class="crumbs"><a href="../index.html">Home</a> / Research results</div>'
        '<h1>Executable Research Results</h1>'
        '<p class="warning">These are preliminary limited-window studies, not validated strategies, '
        'trade recommendations, or evidence of future profitability.</p>'
        '<p>Each report is generated from a frozen specification, an immutable hashed dataset, '
        'a deterministic result object, and a machine-readable trade log.</p>'
        + "".join(research_cards)
    )
    (research_dir / "index.html").write_text(
        page(
            "Executable research results", research_body, "../", "research", domains,
            description="Reproducible preliminary trading research with machine-readable evidence.",
        ),
        encoding="utf-8",
    )
    written.add("research/index.html")

    # ---- search index + sitemap ----
    (DOCS / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    api_dir = DOCS / "api" / "v1"
    api_dir.mkdir(parents=True)
    regime_api = {
        "taxonomy": taxonomy,
        "collection_id": core_collection["id"],
        "annotations": core_collection["annotations"],
    }
    (api_dir / "regimes.json").write_text(
        json.dumps(regime_api, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (api_dir / "playbooks.json").write_text(
        json.dumps(playbooks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (api_dir / "research-specs.json").write_text(
        json.dumps(research_specs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (api_dir / "dataset-manifests.json").write_text(
        json.dumps(dataset_manifests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if (ROOT / "research" / "datasets").exists():
        shutil.copytree(ROOT / "research" / "datasets", api_dir / "datasets")
    (api_dir / "research-results.json").write_text(
        json.dumps(research_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if (ROOT / "research" / "results").exists():
        shutil.copytree(ROOT / "research" / "results", api_dir / "results")
    core_ids = set(core_collection["concept_ids"])
    public_concepts = []
    resolved_relationship_count = 0
    relationship_count = 0
    for _, data in domains:
        for entry in data:
            public_entry = {
                key: value for key, value in entry.items()
                if key not in {"source_hint", "master_index"}
            }
            relationship_ids = []
            for relationship in entry.get("relationships", []):
                relationship_count += 1
                concept_id = relationship_lookup.get(relationship.casefold())
                if concept_id:
                    relationship_ids.append(concept_id)
                    resolved_relationship_count += 1
            public_entry.update({
                "type": "concept",
                "url": concept_urls[entry["id"]],
                "core": entry["id"] in core_ids,
                "regime_annotation": core_collection["annotations"].get(entry["id"]),
                "relationship_ids": relationship_ids,
            })
            public_concepts.append(public_entry)
    (api_dir / "concepts.json").write_text(
        json.dumps(public_concepts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    core_api = {
        key: value for key, value in core_collection.items()
        if key in {"id", "name", "description", "market_scope", "concept_ids", "annotations"}
    }
    (api_dir / "core-perps.json").write_text(
        json.dumps(core_api, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    public_skills = []
    skill_api_dir = api_dir / "skills"
    skill_api_dir.mkdir()
    raw_base = "https://raw.githubusercontent.com/unperson-12359/trading-knowledge-library/main/"
    for profile in skill_manifest["skills"]:
        public_profile = dict(profile)
        public_profile["$schema"] = f"{BASE}/schemas/concept-skill.schema.json"
        public_profile.update({
            "detail_url": f'{BASE}/skills/{profile["skill_name"]}/',
            "concept_url": f'{BASE}/{concept_urls[profile["concept_id"]]}',
            "profile_url": f'{BASE}/api/v1/skills/{profile["skill_name"]}.json',
            "raw_skill_url": raw_base + profile["package_path"] + "/SKILL.md",
            "raw_profile_url": raw_base + profile["package_path"] + "/skill.json",
            "raw_reference_url": raw_base + profile["package_path"] + "/references/concept.json",
        })
        public_skills.append(public_profile)
        api_profile = dict(profile)
        api_profile["$schema"] = f"{BASE}/schemas/concept-skill.schema.json"
        (skill_api_dir / f'{profile["skill_name"]}.json').write_text(
            json.dumps(api_profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    public_skill_catalog = {
        "schema_version": 1,
        "target_count": skill_manifest["target_count"],
        "completed_count": len(public_skills),
        "skills": public_skills,
    }
    (api_dir / "skills.json").write_text(
        json.dumps(public_skill_catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (api_dir / "skill-progress.json").write_text(
        json.dumps(skill_progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (api_dir / "skill-architecture.json").write_text(
        json.dumps(skill_architecture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": 1,
        "generated": date.today().isoformat(),
        "counts": {"concepts": total, "core_concepts": len(core_ids), "concept_skills": len(public_skills), "playbooks": len(playbooks), "research_specs": len(research_specs), "datasets": len(dataset_manifests), "research_results": len(research_results)},
        "endpoints": {
            "concepts": "concepts.json", "core_perps": "core-perps.json",
            "regimes": "regimes.json", "playbooks": "playbooks.json",
            "research_specs": "research-specs.json", "datasets": "dataset-manifests.json",
            "research_results": "research-results.json", "skills": "skills.json",
            "skill_progress": "skill-progress.json", "skill_architecture": "skill-architecture.json"
        },
        "relationship_resolution": {
            "total_references": relationship_count,
            "resolved_references": resolved_relationship_count,
            "unresolved_references": relationship_count - resolved_relationship_count,
            "unresolved_terms": unresolved_relationships,
        },
        "ai_disclosure": "Built and maintained with AI systems; verify cited sources independently. Nothing here is financial advice or evidence of profitability."
    }
    (api_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
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

    print(
        f"site built: {len(written)} pages, {total} entries, 0 broken links; "
        f"relationships {resolved_relationship_count}/{relationship_count} resolved"
    )


if __name__ == "__main__":
    sys.exit(main())

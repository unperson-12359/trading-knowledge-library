"""Build the static site from concepts/*.json into docs/ (GitHub Pages source).

Stdlib only. Generates:
  docs/index.html              consolidated searchable concept catalog
  docs/about.html              AI disclosure and project methodology
  docs/playbooks/              research playbook index + detail pages
  docs/research/               executable research index + result reports
  docs/all.html                compatibility redirect to the catalog
  docs/<slug>/*.html           compatibility redirects for legacy concept URLs
  docs/api/v1/regimes.json     regime taxonomy + core annotations
  docs/api/v1/playbooks.json   all research playbook objects
  docs/search-index.json       client-side search data
  docs/sitemap.xml             every generated page

Navigation: compact global header, shareable catalog filters, breadcrumbs,
and an internal link checker (build fails if any internal href is broken).
"""
import html
import json
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from build_skills import expand_aliases

ROOT = Path(__file__).resolve().parent.parent
CONCEPTS = ROOT / "concepts"
DOCS = ROOT / "docs"
BASE = "https://unperson-12359.github.io/trading-knowledge-library"
PER_PAGE = 25

CSS = """
*{box-sizing:border-box}
body{font-family:Georgia,serif;margin:0;color:#1a1a1a;line-height:1.55;min-height:100vh;background:#fff}
a{color:#0b5fff;text-decoration:none}a:hover{text-decoration:underline}
.global-header{position:sticky;top:0;z-index:20;background:#101010;color:#fff;border-bottom:1px solid #2d2d2d;font-family:system-ui}
.header-inner{max-width:1180px;margin:0 auto;padding:.8rem 1.4rem;display:flex;align-items:center;gap:1.5rem}
.brand{color:#fff;font-weight:800;letter-spacing:-.02em;white-space:nowrap}.brand:hover{text-decoration:none;color:#ffb08a}
.global-nav{display:flex;align-items:center;gap:.25rem;flex-wrap:wrap}.global-nav a{color:#ddd;padding:.38rem .62rem;border-radius:5px;font-size:.86rem}.global-nav a:hover{background:#262626;color:#fff;text-decoration:none}.global-nav a.active{background:#fff;color:#111;font-weight:700}
.github-link{margin-left:auto;color:#ffb08a;font-size:.86rem}.github-link:hover{color:#fff;text-decoration:none}
main{padding:1.5rem 1.4rem;max-width:1180px;margin:0 auto;min-width:0}
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
.query-controls{display:grid;grid-template-columns:minmax(220px,2fr) repeat(4,minmax(130px,1fr));gap:.55rem;margin:1rem 0;font-family:system-ui;align-items:end}
.query-controls input,.query-controls select{width:100%;padding:.5rem;border:1px solid #bbb;border-radius:5px;background:#fff}
.query-controls label{font-size:.78rem;color:#555}.query-controls .check{display:flex;align-items:end;padding-bottom:.5rem}
.query-result{border-bottom:1px solid #ddd;padding:.8rem 0}.query-result h2{font-size:1.05rem;margin:0 0 .2rem}
.skills-hero{background:#111;color:#fff;border-radius:10px;padding:1.3rem 1.4rem;margin-bottom:1rem}.skills-hero h1{border:0;margin:.1rem 0}.skills-hero p{max-width:680px}.skills-hero a{color:#ffb08a}
.catalog-stat{font-family:system-ui;font-size:1.05rem;margin:.8rem 0}.catalog-stat strong{font-size:1.45rem}
.skill-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem;margin:1rem 0}
.skill-card{border:1px solid #ccc;border-radius:8px;padding:1rem;background:#fff;display:flex;flex-direction:column;min-height:205px}.skill-card:hover{border-color:#d97745;box-shadow:0 3px 12px #0000000d}.skill-card h2{font-family:system-ui;font-size:1.08rem;margin:0 0 .25rem}.skill-card p{margin:.5rem 0;flex:1}.skill-links{font-family:system-ui;font-size:.82rem;border-top:1px solid #eee;padding-top:.55rem}.skill-arrow{float:right;color:#d05f2c}
.skill-identity{border:1px solid #ddd;border-radius:8px;padding:.8rem 1rem;font-family:system-ui;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem;margin:1rem 0}.skill-identity strong{display:block;font-size:.78rem;color:#666}.skill-identity span{overflow-wrap:anywhere}
.use-panel{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:1rem 0}.copy-row{display:flex;gap:.5rem;align-items:start}.copy-row pre{flex:1;margin:0}.copy-button{border:1px solid #aaa;background:#fff;border-radius:5px;padding:.45rem .65rem;cursor:pointer;font-weight:600}.copy-button:hover{background:#f3f3f0}
.source-nav{display:flex;gap:.5rem;flex-wrap:wrap;font-family:system-ui;font-size:.82rem;margin:.8rem 0}.source-nav a{border:1px solid #ccc;border-radius:5px;padding:.25rem .5rem}
.source-file{border:1px solid #ddd;border-radius:7px;margin:.65rem 0;background:#fafaf8}.source-file summary{padding:.7rem .85rem;cursor:pointer;font-family:system-ui;font-weight:700}.source-file pre{border-top:1px solid #ddd;margin:0;border-radius:0;max-height:620px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.evidence-section{border-top:1px solid #ddd;padding-top:.35rem;margin-top:1rem}.citation-list li{margin:.35rem 0}
.skill-tabs{display:flex;gap:.45rem;flex-wrap:wrap;margin:1.2rem 0;border-bottom:1px solid #ddd;padding-bottom:.7rem}.skill-tab{border:1px solid #bbb;background:#fff;color:#0b5fff;border-radius:6px;padding:.45rem .7rem;cursor:pointer;font:600 .82rem system-ui}.skill-tab:hover{background:#f4f4f1}.skill-tab[aria-selected="true"]{background:#111;color:#fff;border-color:#111}.skill-panel{min-height:260px}.skill-panel[hidden]{display:none}.skill-panel>pre{max-height:720px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.domainnav{display:flex;justify-content:space-between;margin-top:2rem;font-family:system-ui;font-size:.85rem}
.toc{columns:2;font-family:system-ui;font-size:.82rem;background:#fafaf8;border:1px solid #e8e8e5;border-radius:6px;padding:.8rem 1rem}
.toc a{color:#333}
#search{width:100%;padding:.4rem .6rem;border:1px solid #ccc;border-radius:6px;font-size:.9rem;margin-bottom:.6rem;font-family:system-ui}
#search-results{list-style:none;margin:0 0 .8rem;padding:0}
#search-results li{padding:.25rem .4rem;border-bottom:1px solid #eee}
#search-results .sr-domain{color:#888;font-size:.72rem}
.catalog-tools{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;margin:.8rem 0}.letter-nav{display:flex;gap:.2rem;flex-wrap:wrap;font:600 .78rem system-ui}.letter-nav a{padding:.2rem .4rem;border-radius:4px;border:1px solid #ddd;color:#444}.letter-nav a.active,.letter-nav a:hover{background:#111;color:#fff;text-decoration:none;border-color:#111}.catalog-pagination{display:flex;gap:.35rem;justify-content:center;align-items:center;margin:1.2rem 0;font-family:system-ui}.catalog-pagination a,.catalog-pagination span{border:1px solid #ccc;border-radius:5px;padding:.35rem .65rem}.catalog-pagination .current{background:#111;color:#fff;border-color:#111}.catalog-pagination a:hover{background:#f3f3f0;text-decoration:none}
.redirect-card{max-width:620px;margin:12vh auto;padding:1.5rem;border:1px solid #ddd;border-radius:10px;font-family:system-ui;background:#fff}
.parameter-note{background:#eef6ff;border-left:4px solid #0b5fff;padding:.7rem 1rem;margin:1rem 0;font-family:system-ui}
@media(max-width:820px){
 .global-header{position:static}.header-inner{align-items:flex-start;gap:.6rem;flex-wrap:wrap}.global-nav{order:3;width:100%}.github-link{margin-left:0}
 main{padding:1rem}
 .toc{columns:1}
 .query-controls{grid-template-columns:1fr 1fr}
 .metric-grid{grid-template-columns:1fr 1fr}
 .skill-grid{grid-template-columns:1fr}
 .skill-identity{grid-template-columns:1fr}
 .copy-row{display:block}.copy-button{margin-top:.5rem}
}
"""

CATALOG_JS = r"""
(function(){
  var form=document.getElementById('catalog-controls'),out=document.getElementById('catalog-results'),count=document.getElementById('catalog-count'),letters=document.getElementById('letter-nav'),pager=document.getElementById('catalog-pagination');
  if(!form||!out)return;
  var state={skills:[],concepts:{},aliases:{}},pageSize=60,fields=['q','domain','regime','letter','sort'];
  function h(s){return String(s==null?'':s).replace(/[&<>\"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]});}
  function applyUrl(){var p=new URLSearchParams(location.search);fields.forEach(function(k){if(p.has(k)&&form.elements[k])form.elements[k].value=p.get(k)});form.elements.core.checked=p.get('core')==='1';}
  function params(page){var p=new URLSearchParams();fields.forEach(function(k){var v=form.elements[k].value.trim();if(v&&!(k==='sort'&&v==='az'))p.set(k,v)});if(form.elements.core.checked)p.set('core','1');if(page>1)p.set('page',page);return p;}
  function href(changes){var p=params(1);Object.keys(changes).forEach(function(k){var v=changes[k];if(v)p.set(k,v);else p.delete(k)});return 'index.html'+(p.toString()?'?'+p:'');}
  function updateUrl(page){var p=params(page);history.replaceState(null,'',location.pathname+(p.toString()?'?'+p:''));}
  function render(){
    var q=form.elements.q.value.trim().toLowerCase(),domain=form.elements.domain.value,regime=form.elements.regime.value,letter=form.elements.letter.value.toUpperCase(),core=form.elements.core.checked,sort=form.elements.sort.value,periodMatch=q.match(/\b(\d+|n)[\s-]*periods?[\s-]+(?:(?:simple|price|holding[\s-]+period)[\s-]+)?returns?\b/i);
    var rows=state.skills.filter(function(x){var c=state.concepts[x.concept_id]||{},aliasText=(state.aliases[x.concept_id]||[]).map(function(a){return [a.legacy_display_name,a.legacy_concept_id,a.legacy_skill_name,(a.legacy_terms||[]).join(' ')].join(' ')}).join(' '),text=[x.display_name,x.concept_id,x.description,(x.trigger_phrases||[]).join(' '),(c.aliases||[]).join(' '),aliasText,c.definition,c.intuition,c.mechanics,c.failure_modes,c.misconceptions].join(' ').toLowerCase(),regimes=((c.regime_annotation||{}).regime_relevance||[]),parameterHit=periodMatch&&x.concept_id==='parameterized-analytics/n-period-simple-return';return (!q||text.indexOf(q)!==-1||parameterHit)&&(!domain||x.concept_id.split('/')[0]===domain)&&(!core||x.core)&&(!regime||regimes.indexOf(regime)!==-1)&&(!letter||x.display_name.charAt(0).toUpperCase()===letter);});
    rows.sort(function(a,b){if(sort==='domain'){var d=a.domain.localeCompare(b.domain);if(d)return d;}return a.display_name.localeCompare(b.display_name);});
    var requested=parseInt(new URLSearchParams(location.search).get('page')||'1',10),pages=Math.max(1,Math.ceil(rows.length/pageSize)),page=Math.min(Math.max(requested,1),pages),shown=rows.slice((page-1)*pageSize,page*pageSize);
    updateUrl(page);count.innerHTML=rows.length+' of '+state.skills.length+' concepts'+(rows.length?' &middot; showing '+((page-1)*pageSize+1)+'&ndash;'+Math.min(page*pageSize,rows.length):'');
    out.innerHTML=shown.map(function(x){var c=state.concepts[x.concept_id]||{},url='skills/'+encodeURIComponent(x.skill_name)+'/'+(periodMatch&&x.concept_id==='parameterized-analytics/n-period-simple-return'&&periodMatch[1]!=='n'?'?periods='+encodeURIComponent(periodMatch[1]):'');return '<article class="skill-card"><h2><a href="'+url+'">'+h(x.display_name)+'</a><span class="skill-arrow">&rarr;</span></h2><div class="meta">'+h(x.domain)+(x.core?' &middot; core collection':'')+'</div><p>'+h(c.definition||x.description)+'</p><div class="skill-links"><a href="'+url+'">Open concept</a> &middot; <a href="api/v1/skills/'+encodeURIComponent(x.skill_name)+'.json">JSON</a></div></article>';}).join('')||(state.skills.length?'<p>No concepts match these filters.</p>':'<p>The concept catalog is being prepared.</p>');
    var alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');letters.innerHTML='<a href="'+h(href({letter:''}))+'"'+(!letter?' class="active"':'')+'>All</a>'+alphabet.map(function(x){return '<a href="'+h(href({letter:x}))+'"'+(letter===x?' class="active"':'')+'>'+x+'</a>';}).join('');
    var nav=[];if(page>1)nav.push('<a href="'+h(href({page:String(page-1)}))+'">&larr; Previous</a>');nav.push('<span class="current">'+page+' of '+pages+'</span>');if(page<pages)nav.push('<a href="'+h(href({page:String(page+1)}))+'">Next &rarr;</a>');pager.innerHTML=nav.join('');
  }
  applyUrl();Promise.all([fetch('api/v1/skills.json').then(function(r){return r.json()}),fetch('api/v1/concepts.json').then(function(r){return r.json()}),fetch('api/v1/concept-aliases.json').then(function(r){return r.json()})]).then(function(data){state.skills=data[0].skills||[];data[1].forEach(function(c){state.concepts[c.id]=c});(data[2].aliases||[]).forEach(function(a){(state.aliases[a.canonical_concept_id]||(state.aliases[a.canonical_concept_id]=[])).push(a)});render();});
  form.addEventListener('input',function(){history.replaceState(null,'',location.pathname);render();});form.addEventListener('change',function(){history.replaceState(null,'',location.pathname);render();});form.addEventListener('submit',function(e){e.preventDefault();render();});
})();
"""

COPY_JS = r"""
(function(){
  var tabs=[].slice.call(document.querySelectorAll('[data-skill-tab]'));
  function show(id,updateHash){tabs.forEach(function(tab){var selected=tab.getAttribute('data-skill-tab')===id;tab.setAttribute('aria-selected',selected?'true':'false');var panel=document.getElementById(tab.getAttribute('aria-controls'));if(panel)panel.hidden=!selected;});if(updateHash)history.replaceState(null,'','#'+id);}
  tabs.forEach(function(tab){tab.addEventListener('click',function(){show(tab.getAttribute('data-skill-tab'),true);});});
  if(tabs.length){var requested=location.hash.replace(/^#/,'');show(tabs.some(function(tab){return tab.getAttribute('data-skill-tab')===requested;})?requested:'concept',false);}
  var periodNote=document.getElementById('selected-period'),periods=new URLSearchParams(location.search).get('periods');if(periodNote&&/^\d+$/.test(periods||'')&&Number(periods)>0){periodNote.hidden=false;periodNote.innerHTML='<strong>Selected lookback:</strong> '+Number(periods)+' periods. Use this value for <code>n</code> and interpret it with the chosen bar frequency.';}
  document.querySelectorAll('[data-copy]').forEach(function(button){
    button.addEventListener('click',function(){var target=document.getElementById(button.getAttribute('data-copy'));if(!target)return;navigator.clipboard.writeText(target.textContent).then(function(){var old=button.textContent;button.textContent='Copied';setTimeout(function(){button.textContent=old},1400);});});
  });
})();
"""

def esc(s):
    return html.escape(str(s), quote=True)


def anchor(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def redirect_document(title, fallback, script):
    """Return a small GitHub Pages-compatible redirect with a usable fallback."""
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
        f"<main><div class='redirect-card'><h1>{esc(title)}</h1>"
        "<p>This address now opens the consolidated trading concept library.</p>"
        f"<p><a href='{esc(fallback)}'>Continue to the library</a></p></div></main>"
        f"<script>{script}</script></body></html>"
    )


def page(title, body, prefix, slug, domains, extra_head="", description=""):
    nav_items = [
        ("", "Library", f"{prefix}index.html"),
        ("playbooks", "Playbooks", f"{prefix}playbooks/"),
        ("research", "Research", f"{prefix}research/"),
        ("analysis", "Analysis API", f"{prefix}analysis.html"),
        ("about", "About", f"{prefix}about.html"),
    ]
    nav_links = "".join(
        f'<a href="{href}"' + (' class="active"' if slug == key else "") +
        f'>{label}</a>'
        for key, label, href in nav_items
    )
    nav = (
        '<header class="global-header"><div class="header-inner">'
        f'<a class="brand" href="{prefix}index.html">Pakupai Library</a>'
        f'<nav class="global-nav" aria-label="Primary">{nav_links}</nav>'
        '<a class="github-link" href="https://github.com/unperson-12359/'
        'trading-knowledge-library">GitHub</a></div></header>'
    )
    desc = f'<meta name="description" content="{esc(description)}">' if description else ""
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title>{desc}{extra_head}<style>{CSS}</style></head>"
            f"<body>{nav}<main>{body}"
            f"<p class='meta'>Generated {date.today().isoformat()} · "
            f"<a href='{prefix}about.html'>About &amp; Methodology</a> · "
            f"<a href='{prefix}api/v1/manifest.json'>JSON API</a> · "
            f"<a href='https://github.com/unperson-12359/trading-knowledge-library'>GitHub</a></p>"
            f"</main></body></html>")


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
    relationship_vocabulary = json.loads(
        (ROOT / "relationships" / "vocabulary.json").read_text(encoding="utf-8")
    )
    skill_manifest = json.loads(
        (ROOT / "skills" / "manifest.json").read_text(encoding="utf-8")
    )
    compatibility_aliases = expand_aliases(ROOT)
    skill_architecture = json.loads(
        (ROOT / "skills" / "architecture.json").read_text(encoding="utf-8")
    )
    source_policy = json.loads(
        (ROOT / "sources" / "source-policy.json").read_text(encoding="utf-8")
    )
    citation_audit = json.loads(
        (ROOT / "audits" / "citation-audit.json").read_text(encoding="utf-8")
    )
    analysis_context_contract = json.loads(
        (ROOT / "schemas" / "analysis-context.schema.json").read_text(encoding="utf-8")
    )
    written = set()      # relative paths of generated pages, for the link checker
    redirects = set()    # compatibility pages excluded from the sitemap
    search_index = []    # {n, d, u}
    legacy_urls = {}
    skill_urls = {
        profile["concept_id"]: f'skills/{profile["skill_name"]}/'
        for profile in skill_manifest["skills"]
    }
    concept_urls = dict(skill_urls)
    concept_names = {}
    concept_by_id = {}
    term_ids = {}
    aliases_by_canonical = {}
    for alias in compatibility_aliases:
        aliases_by_canonical.setdefault(alias["canonical_concept_id"], []).append(alias)
    for slug, data in domains:
        for index, entry in enumerate(data):
            page_no = index // PER_PAGE + 1
            url = f"{slug}/" if page_no == 1 else f"{slug}/page-{page_no}.html"
            url += f"#{anchor(entry['name'])}"
            legacy_urls[entry["id"]] = url
            concept_names[entry["id"]] = entry["name"]
            concept_by_id[entry["id"]] = entry
            search_index.append({
                "n": entry["name"], "d": entry["domain"],
                "u": concept_urls[entry["id"]],
                "a": " ".join(
                    entry.get("aliases", []) + [
                        alias["legacy_display_name"]
                        for alias in aliases_by_canonical.get(entry["id"], [])
                    ]
                ),
                "x": " ".join([entry.get("definition", ""), entry.get("intuition", "")]),
            })
            for term in [entry["name"], *entry.get("aliases", [])]:
                term_ids.setdefault(term.casefold(), set()).add(entry["id"])
    assert len(concept_urls) == total, "every concept must have a unified detail page"
    relationship_lookup = {
        term: next(iter(ids_for_term))
        for term, ids_for_term in term_ids.items() if len(ids_for_term) == 1
    }
    external_lookup = {
        item["label"].casefold(): item for item in relationship_vocabulary["terms"]
    }
    unresolved_relationships = sorted({
        relationship for _, data in domains for entry in data
        for relationship in entry.get("relationships", [])
        if (relationship.casefold() not in relationship_lookup
            and relationship.casefold() not in external_lookup)
    })
    assert not unresolved_relationships, (
        "relationship vocabulary missing terms: " + ", ".join(unresolved_relationships)
    )

    # ---- legacy domain URLs -> unified concept pages ----
    for slug, data in domains:
        n_pages = max(1, (len(data) + PER_PAGE - 1) // PER_PAGE)
        ddir = DOCS / slug
        ddir.mkdir()
        for pno in range(1, n_pages + 1):
            chunk = data[(pno - 1) * PER_PAGE: pno * PER_PAGE]
            fname = "index.html" if pno == 1 else f"page-{pno}.html"
            routes = {
                anchor(entry["name"]): "../" + concept_urls[entry["id"]]
                for entry in chunk
            }
            fallback = f"../index.html?domain={slug}"
            script = (
                "(function(){var routes=" + json.dumps(routes, ensure_ascii=False) +
                ",key=decodeURIComponent(location.hash.slice(1));"
                f"location.replace(routes[key]||{json.dumps(fallback)});}})();"
            )
            rel = f"{slug}/{fname}"
            (ddir / fname).write_text(
                redirect_document(data[0]["domain"], fallback, script), encoding="utf-8"
            )
            written.add(rel)
            redirects.add(rel)

    # ---- retired numbered return domain URLs -> parameterized concept ----
    return_alias_pages = {}
    for alias in compatibility_aliases:
        periods = alias["parameters"]["periods"]
        page_no = (periods - 2) // PER_PAGE + 1
        return_alias_pages.setdefault(page_no, {})[anchor(alias["legacy_display_name"])] = (
            "../skills/tkl-n-period-simple-return/?periods=" + str(periods)
        )
    return_alias_pages.setdefault(1, {})[anchor("N-period simple return")] = (
        "../skills/tkl-n-period-simple-return/"
    )
    return_dir = DOCS / "parameterized-analytics"
    return_dir.mkdir(exist_ok=True)
    for page_no, routes in sorted(return_alias_pages.items()):
        fname = "index.html" if page_no == 1 else f"page-{page_no}.html"
        fallback = "../index.html?domain=parameterized-analytics"
        script = (
            "(function(){var routes=" + json.dumps(routes, ensure_ascii=False) +
            ",key=decodeURIComponent(location.hash.slice(1));"
            f"location.replace(routes[key]||{json.dumps(fallback)});}})();"
        )
        rel = f"parameterized-analytics/{fname}"
        (return_dir / fname).write_text(
            redirect_document("Parameterized analytics", fallback, script),
            encoding="utf-8",
        )
        written.add(rel)
        redirects.add(rel)

    # ---- compatibility A-Z route ----
    all_script = "location.replace('index.html'+location.search+location.hash);"
    (DOCS / "all.html").write_text(
        redirect_document("A–Z concept index", "index.html", all_script), encoding="utf-8"
    )
    written.add("all.html")
    redirects.add("all.html")

    # ---- consolidated concept catalog ----
    domain_options = "".join(
        f'<option value="{esc(slug)}">{esc(data[0]["domain"])} ({len(data)})</option>'
        for slug, data in domains
    )
    regime_tags = [
        f'{dimension["id"]}.{state["id"]}'
        for dimension in taxonomy["dimensions"] for state in dimension["states"]
    ]
    regime_options = "".join(
        f'<option value="{esc(value)}">{esc(value)}</option>' for value in regime_tags
    )
    index_body = (
        '<div class="crumbs">Library</div>'
        '<section class="skills-hero"><h1>Trading Knowledge Library</h1>'
        f'<p>Search {total:,} canonical trading concepts. Every result opens one complete page with the '
        'human explanation, AI skill instructions, canonical JSON, packaged references, '
        'failure modes, misconceptions, and citations.</p>'
        f'<p class="catalog-stat"><strong>{total}</strong> concepts across '
        f'<strong>{len(domains)}</strong> domains</p>'
        '<p><a href="api/v1/skills.json">Machine-readable catalog</a></p></section>'
        '<p class="warning">Built with AI systems. Verify cited sources independently. '
        'This library provides educational research and decision support, not financial advice.</p>'
        '<form id="catalog-controls" class="query-controls">'
        '<label>Search<input name="q" type="search" placeholder="funding rate, slippage, margin..."></label>'
        f'<label>Domain<select name="domain"><option value="">All domains</option>{domain_options}</select></label>'
        f'<label>Regime<select name="regime"><option value="">All regimes</option>{regime_options}</select></label>'
        '<label>Sort<select name="sort"><option value="az">A–Z</option><option value="domain">Domain</option></select></label>'
        '<label class="check"><input name="core" type="checkbox" style="width:auto;margin-right:.4rem">Core collection only</label>'
        '<input name="letter" type="hidden" value=""></form>'
        '<div class="catalog-tools"><p id="catalog-count" class="meta">Loading catalog...</p>'
        '<nav id="letter-nav" class="letter-nav" aria-label="Filter by first letter"></nav></div>'
        '<div id="catalog-results" class="skill-grid"></div>'
        '<nav id="catalog-pagination" class="catalog-pagination" aria-label="Catalog pages"></nav>'
    )
    index_html = page(
        "Pakupai Trading Knowledge Library", index_body, "", "", domains,
        extra_head=f'<link rel="canonical" href="{BASE}/">',
        description=f"Search {total:,} unified trading concept and AI skill pages."
    ).replace("</body>", f"<script>{CATALOG_JS}</script></body>")
    (DOCS / "index.html").write_text(index_html, encoding="utf-8")
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
        "worked examples, relationships, and direct citations. The consolidated catalog and "
        "static JSON API are dependency-free generated views of the same canonical material.</p>"
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

    # ---- read-only market analysis contract ----
    analysis_body = (
        '<div class="crumbs"><a href="index.html">Home</a> / Analysis Context API</div>'
        '<h1>Read-only Market Analysis Context</h1>'
        '<p class="warning">This command fetches public Hyperliquid data for research context. '
        'It does not access wallets or accounts, place orders, calculate a position size, or issue a trade instruction.</p>'
        '<p>Run <code>python scripts/analyze_market.py --asset BTC --pretty</code> locally. '
        'The response separates observed venue data, deterministic calculations, regime context, '
        'inconclusive playbook fit, missing data, and safety warnings.</p>'
        '<p>The default coverage is BTC and ETH perpetuals using public mark/oracle price, current '
        'funding, current open interest, L2-book depth, and closed 15m/1h/4h candles. It labels '
        'unavailable history and user-selected anchors as unknown.</p>'
        '<h2>Machine-readable contract</h2>'
        '<p><a href="api/v1/analysis-context-contract.json">Open response contract JSON</a> · '
        '<a href="schemas/analysis-context-request.schema.json">Open request schema JSON</a></p>'
        f'<div class="json">{esc(json.dumps(analysis_context_contract, ensure_ascii=False, indent=2))}</div>'
    )
    (DOCS / "analysis.html").write_text(
        page("Read-only market analysis context", analysis_body, "", "analysis", domains,
             description="JSON-first, read-only Hyperliquid perpetual-market analysis context for AI research."),
        encoding="utf-8")
    written.add("analysis.html")

    # ---- compatibility routes for the former query and skill catalogs ----
    query_script = (
        "(function(){var p=new URLSearchParams(location.search);"
        "p.delete('type');p.delete('required_input');"
        "location.replace('index.html'+(p.toString()?'?'+p:''));})();"
    )
    (DOCS / "query.html").write_text(
        redirect_document("Structured concept search", "index.html", query_script),
        encoding="utf-8"
    )
    written.add("query.html")
    redirects.add("query.html")

    skill_dir = DOCS / "skills"
    skill_dir.mkdir()
    skills_script = (
        "(function(){var p=new URLSearchParams(location.search),skill=p.get('skill');"
        "if(skill&&!p.has('q'))p.set('q',skill.replace(/^tkl-/,'').replace(/-/g,' '));"
        "p.delete('skill');location.replace('../index.html'+(p.toString()?'?'+p:''));})();"
    )
    (skill_dir / "index.html").write_text(
        redirect_document("Trading concept catalog", "../index.html", skills_script),
        encoding="utf-8"
    )
    written.add("skills/index.html")
    redirects.add("skills/index.html")

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
        canonical_source = json.dumps(concept, ensure_ascii=False, indent=2) + "\n"
        github_folder = (
            "https://github.com/unperson-12359/trading-knowledge-library/tree/main/"
            + profile["package_path"]
        )
        related_section = (
            f'<div class="evidence-section"><h3>Related concepts</h3>'
            f'<ul>{"".join(related_links)}</ul></div>' if related_links else ""
        )
        domain_slug = profile["concept_id"].split("/", 1)[0]
        parameter_note = (
            '<div id="selected-period" class="parameter-note" hidden></div>'
            if profile["concept_id"] == "parameterized-analytics/n-period-simple-return"
            else ""
        )
        detail_body = (
            '<div class="crumbs"><a href="../../index.html">Library</a> / '
            f'<a href="../../index.html?domain={esc(domain_slug)}">{esc(profile["domain"])}</a> / '
            + esc(profile["display_name"]) + '</div>'
            f'<h1>{esc(profile["display_name"])}</h1>' + parameter_note +
            f'<p>{esc(profile["description"])}</p>'
            f'<div>{aliases}</div>'
            '<div class="skill-identity">'
            f'<div><strong>Skill package</strong><span>{esc(profile["skill_name"])}</span></div>'
            f'<div><strong>Domain</strong><span>{esc(profile["domain"])}</span></div>'
            f'<div><strong>Concept ID</strong><span>{esc(profile["concept_id"])}</span></div>'
            '</div>'
            '<nav class="skill-tabs" role="tablist" aria-label="Concept and skill files">'
            '<button class="skill-tab" data-skill-tab="concept" aria-controls="panel-concept" aria-selected="true">Trading concept</button>'
            '<button class="skill-tab" data-skill-tab="use" aria-controls="panel-use" aria-selected="false">Use skill</button>'
            '<button class="skill-tab" data-skill-tab="skill-md" aria-controls="panel-skill-md" aria-selected="false">SKILL.md</button>'
            '<button class="skill-tab" data-skill-tab="skill-json" aria-controls="panel-skill-json" aria-selected="false">skill.json</button>'
            '<button class="skill-tab" data-skill-tab="concept-json" aria-controls="panel-concept-json" aria-selected="false">concept.json</button>'
            '<button class="skill-tab" data-skill-tab="reference-json" aria-controls="panel-reference-json" aria-selected="false">reference.json</button>'
            '<button class="skill-tab" data-skill-tab="openai-yaml" aria-controls="panel-openai-yaml" aria-selected="false">openai.yaml</button>'
            '</nav>'
            '<section class="skill-panel" id="panel-concept" role="tabpanel">'
            '<h2>Trading concept</h2>'
            f'<p>{esc(concept["definition"])}</p>'
            f'<div class="field"><span class="label">Intuition</span><p>{esc(concept["intuition"])}</p></div>'
            f'<div class="field"><span class="label">Mechanics</span><p>{esc(concept["mechanics"])}</p></div>'
            + formula +
            f'<div class="evidence-section"><h3>Failure modes</h3><p>{esc(concept["failure_modes"])}</p></div>'
            f'<div class="evidence-section"><h3>Misconceptions</h3><p>{esc(concept["misconceptions"])}</p></div>'
            f'<div class="evidence-section"><h3>Example</h3><p>{esc(concept["example"])}</p></div>'
            f'<div class="evidence-section"><h3>Citations</h3><ul class="citation-list">{citations}</ul></div>'
            + related_section + '</section>'
            '<section class="skill-panel" id="panel-use" role="tabpanel" hidden>'
            '<h2>Use this skill</h2><div class="use-panel">'
            '<p>Use the catalog router in a repository that includes this library:</p>'
            '<div class="copy-row"><pre id="router-prompt" class="json">'
            + esc(router_prompt) +
            '</pre><button class="copy-button" data-copy="router-prompt">Copy prompt</button></div>'
            '<p class="meta">For a direct repository-local install, copy this package folder to '
            f'<code>.agents/skills/{esc(profile["skill_name"])}/</code>. '
            f'<a href="{esc(github_folder)}">Open the package on GitHub</a>.</p></div></section>'
            f'<section class="skill-panel" id="panel-skill-md" role="tabpanel" hidden><h2>SKILL.md</h2><pre class="json">{esc(skill_source)}</pre></section>'
            f'<section class="skill-panel" id="panel-skill-json" role="tabpanel" hidden><h2>skill.json</h2><pre class="json">{esc(profile_source)}</pre></section>'
            f'<section class="skill-panel" id="panel-concept-json" role="tabpanel" hidden><h2>Canonical concept.json</h2><p class="meta">The original concept object from the main library.</p><pre class="json">{esc(canonical_source)}</pre></section>'
            f'<section class="skill-panel" id="panel-reference-json" role="tabpanel" hidden><h2>Packaged reference.json</h2><pre class="json">{esc(reference_source)}</pre></section>'
            f'<section class="skill-panel" id="panel-openai-yaml" role="tabpanel" hidden><h2>agents/openai.yaml</h2><pre class="json">{esc(agent_source)}</pre></section>'
            f'<p class="skill-links"><a href="../../api/v1/skills/{esc(profile["skill_name"])}.json">'
            f'Open profile JSON</a> &middot; <a href="{esc(github_folder)}">GitHub source</a></p>'
        )
        detail_html = page(
            profile["display_name"], detail_body, "../../", "", domains,
            extra_head=(f'<link rel="canonical" href="{BASE}/skills/'
                        f'{esc(profile["skill_name"])}/">'),
            description=profile["description"],
        ).replace("</body>", f"<script>{COPY_JS}</script></body>")
        (detail_dir / "index.html").write_text(detail_html, encoding="utf-8")
        written.add(f'skills/{profile["skill_name"]}/index.html')

    # Retired numbered skill URLs retain lightweight redirects with the bound period.
    for alias in compatibility_aliases:
        alias_dir = skill_dir / alias["legacy_skill_name"]
        alias_dir.mkdir()
        periods = alias["parameters"]["periods"]
        fallback = f'../tkl-n-period-simple-return/?periods={periods}'
        script = (
            f"location.replace('../tkl-n-period-simple-return/?periods={periods}'"
            "+location.hash);"
        )
        rel = f'skills/{alias["legacy_skill_name"]}/index.html'
        (alias_dir / "index.html").write_text(
            redirect_document(alias["legacy_display_name"], fallback, script),
            encoding="utf-8",
        )
        written.add(rel)
        redirects.add(rel)

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
                if key != "master_index"
            }
            relationship_ids = []
            relationship_refs = []
            for relationship in entry.get("relationships", []):
                relationship_count += 1
                concept_id = relationship_lookup.get(relationship.casefold())
                if concept_id:
                    relationship_ids.append(concept_id)
                    resolved_relationship_count += 1
                    relationship_refs.append({
                        "label": relationship, "kind": "internal", "concept_id": concept_id,
                    })
                else:
                    vocabulary_term = external_lookup[relationship.casefold()]
                    relationship_refs.append({
                        "label": relationship, "kind": "external-term",
                        "term_id": vocabulary_term["id"],
                    })
            public_entry.update({
                "type": "concept",
                "url": concept_urls[entry["id"]],
                "skill_url": skill_urls.get(entry["id"]),
                "legacy_url": legacy_urls[entry["id"]],
                "core": entry["id"] in core_ids,
                "regime_annotation": core_collection["annotations"].get(entry["id"]),
                "relationship_ids": relationship_ids,
                "relationship_refs": relationship_refs,
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
    (api_dir / "relationship-vocabulary.json").write_text(
        json.dumps(relationship_vocabulary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    public_source_policy = dict(source_policy)
    public_source_policy["$schema"] = f"{BASE}/schemas/source-policy.schema.json"
    (api_dir / "source-policy.json").write_text(
        json.dumps(public_source_policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    public_citation_audit = dict(citation_audit)
    public_citation_audit["$schema"] = f"{BASE}/schemas/citation-audit.schema.json"
    (api_dir / "citation-audit.json").write_text(
        json.dumps(public_citation_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (api_dir / "analysis-context-contract.json").write_text(
        json.dumps(analysis_context_contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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

    public_aliases = []
    for alias in compatibility_aliases:
        periods = alias["parameters"]["periods"]
        public_alias = {
            "$schema": f"{BASE}/schemas/skill-alias.schema.json",
            "schema_version": 1,
            "type": "alias",
            **alias,
            "canonical_detail_url": (
                f"{BASE}/skills/{alias['canonical_skill_name']}/?periods={periods}"
            ),
            "canonical_profile_url": (
                f"{BASE}/api/v1/skills/{alias['canonical_skill_name']}.json"
            ),
        }
        public_aliases.append(public_alias)
        (skill_api_dir / f'{alias["legacy_skill_name"]}.json').write_text(
            json.dumps(public_alias, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    public_alias_catalog = {
        "$schema": f"{BASE}/schemas/skill-alias-catalog.schema.json",
        "schema_version": 1,
        "alias_count": len(public_aliases),
        "aliases": public_aliases,
    }
    (api_dir / "concept-aliases.json").write_text(
        json.dumps(public_alias_catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    public_skill_catalog = {
        "schema_version": 2,
        "concept_count": skill_manifest["concept_count"],
        "skill_count": len(public_skills),
        "alias_count": len(public_aliases),
        "skills": public_skills,
    }
    (api_dir / "skills.json").write_text(
        json.dumps(public_skill_catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (api_dir / "skill-architecture.json").write_text(
        json.dumps(skill_architecture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": 2,
        "generated": date.today().isoformat(),
        "counts": {"concepts": total, "core_concepts": len(core_ids), "concept_skills": len(public_skills), "compatibility_aliases": len(public_aliases), "playbooks": len(playbooks), "research_specs": len(research_specs), "datasets": len(dataset_manifests), "research_results": len(research_results)},
        "endpoints": {
            "concepts": "concepts.json", "core_perps": "core-perps.json",
            "regimes": "regimes.json", "playbooks": "playbooks.json",
            "research_specs": "research-specs.json", "datasets": "dataset-manifests.json",
            "research_results": "research-results.json", "skills": "skills.json",
            "concept_aliases": "concept-aliases.json", "relationship_vocabulary": "relationship-vocabulary.json",
            "source_policy": "source-policy.json", "citation_audit": "citation-audit.json",
            "analysis_context_contract": "analysis-context-contract.json",
            "skill_architecture": "skill-architecture.json"
        },
        "relationship_resolution": {
            "total_references": relationship_count,
            "resolved_references": resolved_relationship_count,
            "external_term_references": relationship_count - resolved_relationship_count,
            "external_terms": relationship_vocabulary["terms"],
        },
        "ai_disclosure": "Built and maintained with AI systems; verify cited sources independently. Nothing here is financial advice or evidence of profitability."
    }
    (api_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    urls = [
        f"{BASE}/{w.replace('index.html', '')}"
        for w in sorted(written - redirects)
    ]
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
            target_path = target.split("?", 1)[0]
            resolved = (fpath.parent / target_path).resolve()
            if target_path.endswith("/"):
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

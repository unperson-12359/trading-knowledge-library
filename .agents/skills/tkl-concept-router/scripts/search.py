#!/usr/bin/env python3
"""Search the local concept-skill manifest, with a public API fallback."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen

PUBLIC_CATALOG = (
    "https://unperson-12359.github.io/trading-knowledge-library/api/v1/skills.json"
)
PUBLIC_ALIASES = (
    "https://unperson-12359.github.io/trading-knowledge-library/api/v1/concept-aliases.json"
)
PARAMETERIZED_RETURN_ID = "parameterized-analytics/n-period-simple-return"
PARAMETERIZED_RETURN_SKILL = "tkl-n-period-simple-return"
PERIOD_RETURN_RE = re.compile(
    r"\b(?P<periods>\d+|n)[\s-]*periods?[\s-]+(?:(?:simple|price|holding[\s-]+period)[\s-]+)?returns?\b",
    re.IGNORECASE,
)


def repository_root(start=None):
    current = Path(start or __file__).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "skills" / "manifest.json").exists():
            return candidate
    return None


def expand_alias_families(payload):
    aliases = []
    for family in payload.get("families", []):
        parameter = family["parameter"]
        name = parameter["name"]
        for value in range(parameter["minimum"], parameter["maximum"] + 1):
            replacements = {name: value}
            aliases.append({
                "legacy_concept_id": family["legacy_concept_id_template"].format(**replacements),
                "legacy_skill_name": family["legacy_skill_name_template"].format(**replacements),
                "legacy_display_name": family["legacy_display_name_template"].format(**replacements),
                "legacy_terms": [
                    template.format(**replacements)
                    for template in family.get("legacy_term_templates", [])
                ],
                "canonical_concept_id": family["canonical_concept_id"],
                "canonical_skill_name": family["canonical_skill_name"],
                "parameters": {name: value},
            })
    return aliases


def load_catalog(start=None):
    root = repository_root(start)
    if root:
        payload = json.loads((root / "skills" / "manifest.json").read_text(encoding="utf-8"))
        alias_payload = json.loads(
            (root / "aliases" / "concept-aliases.json").read_text(encoding="utf-8")
        )
        return payload.get("skills", []), expand_alias_families(alias_payload), "local", root
    with urlopen(PUBLIC_CATALOG, timeout=15) as response:
        payload = json.load(response)
    with urlopen(PUBLIC_ALIASES, timeout=15) as response:
        alias_payload = json.load(response)
    return (
        payload.get("skills", payload if isinstance(payload, list) else []),
        alias_payload.get("aliases", []), "public-api", None,
    )


def tokens(value):
    return set(re.findall(r"[a-z0-9]+", str(value).casefold()))


def score_profile(profile, query):
    q = query.casefold().strip()
    if not q:
        return 0, []
    q_tokens = tokens(q)
    name = profile.get("display_name", "").casefold()
    concept_id = profile.get("concept_id", "").casefold()
    skill_name = profile.get("skill_name", "").casefold()
    triggers = [str(value).casefold() for value in profile.get("trigger_phrases", [])]
    description = profile.get("description", "").casefold()
    domain = profile.get("domain", "").casefold()
    score = 0
    reasons = []
    if q in {name, concept_id, skill_name}:
        score += 100
        reasons.append("exact identifier")
    if q == name or q in triggers:
        score += 80
        reasons.append("exact name or trigger")
    if q in name or q in concept_id:
        score += 35
        reasons.append("name or ID phrase")
    trigger_hits = sum(1 for trigger in triggers if q in trigger or trigger in q)
    if trigger_hits:
        score += min(30, trigger_hits * 10)
        reasons.append("trigger phrase")
    name_overlap = len(q_tokens & tokens(name))
    body_overlap = len(q_tokens & tokens(" ".join(triggers + [description, domain, concept_id])))
    if name_overlap:
        score += name_overlap * 12
        reasons.append("name terms")
    if body_overlap:
        score += body_overlap * 3
        reasons.append("catalog terms")
    return score, reasons


def parameter_binding(query):
    match = PERIOD_RETURN_RE.search(str(query))
    if not match:
        return None
    raw = match.group("periods").casefold()
    return {"periods": raw if raw == "n" else int(raw)}


def resolve_alias(aliases, concept_id=None, skill_name=None):
    for alias in aliases or []:
        if concept_id and alias.get("legacy_concept_id") == concept_id:
            return alias
        if skill_name and alias.get("legacy_skill_name") == skill_name:
            return alias
    return None


def search(profiles, query, limit=5, domain=None, core_only=False,
           concept_id=None, skill_name=None, aliases=None):
    alias = resolve_alias(aliases, concept_id, skill_name)
    binding = alias.get("parameters") if alias else parameter_binding(query)
    canonicalized_from = None
    if alias:
        canonicalized_from = concept_id or skill_name
        concept_id = alias["canonical_concept_id"]
        skill_name = alias["canonical_skill_name"]
    elif binding:
        canonicalized_from = query
    rows = []
    for profile in profiles:
        if domain and profile.get("domain", "").casefold() != domain.casefold():
            continue
        if core_only and not profile.get("core"):
            continue
        if concept_id and profile.get("concept_id") != concept_id:
            continue
        if skill_name and profile.get("skill_name") != skill_name:
            continue
        score, reasons = score_profile(profile, query)
        if binding and profile.get("concept_id") == PARAMETERIZED_RETURN_ID:
            score += 250
            reasons.insert(0, "parameterized return pattern")
        if score or concept_id or skill_name:
            rows.append((score, profile.get("display_name", "").casefold(), profile, reasons))
    rows.sort(key=lambda row: (-row[0], row[1], row[2].get("concept_id", "")))
    matches = []
    for row in rows[:limit]:
        match = dict(row[2], match_score=row[0], match_reasons=row[3])
        if binding and match.get("concept_id") == PARAMETERIZED_RETURN_ID:
            match["bound_parameters"] = binding
            match["canonicalized_from"] = canonicalized_from
        matches.append(match)
    return matches


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--domain")
    parser.add_argument("--core-only", action="store_true")
    parser.add_argument("--concept-id")
    parser.add_argument("--skill-name")
    args = parser.parse_args(argv)
    if not (args.query or args.concept_id or args.skill_name):
        parser.error("provide a query, --concept-id, or --skill-name")
    profiles, aliases, source, root = load_catalog()
    matches = search(
        profiles, args.query, max(1, args.limit), args.domain, args.core_only,
        args.concept_id, args.skill_name, aliases,
    )
    payload = {
        "schema_version": 2,
        "query": args.query,
        "catalog_source": source,
        "repository_root": str(root) if root else None,
        "match_count": len(matches),
        "matches": matches,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())

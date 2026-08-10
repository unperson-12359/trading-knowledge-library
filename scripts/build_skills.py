#!/usr/bin/env python3
"""Build and validate the installable concept-skill catalog."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
MANIFEST_PATH = SKILLS / "manifest.json"
ALIASES_PATH = ROOT / "aliases" / "concept-aliases.json"
CORE_PATH = ROOT / "collections" / "core-perps.json"
PARAMETERIZED_RETURN_ID = "parameterized-analytics/n-period-simple-return"
INTENTS = ["explain", "compare", "apply", "diagnose-misconception"]
OUTPUT_FIELDS = [
    "concept_id", "intent", "summary", "facts", "inferences", "unknowns",
    "failure_modes", "misconceptions", "citations", "warning",
]
WARNING = (
    "Educational research and decision support only; not financial advice, "
    "a trade recommendation, or evidence of profitability."
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value or "concept"


def canonical_bytes(concept):
    return json.dumps(
        concept, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_hash(concept):
    return hashlib.sha256(canonical_bytes(concept)).hexdigest()


def load_concepts(root=ROOT):
    records = []
    for path in sorted((root / "concepts").glob("*.json")):
        for concept in read_json(path):
            records.append((concept, path.stem, path.relative_to(root).as_posix()))
    return records


def ordered_records(root=ROOT):
    records = load_concepts(root)
    core_ids = set(read_json(root / "collections" / "core-perps.json")["concept_ids"])
    return sorted(records, key=lambda row: (
        0 if row[0]["id"] in core_ids else 1,
        row[0]["master_index"],
        row[0]["id"],
    ))


def unique_term_lookup(records):
    candidates = {}
    for concept, _, _ in records:
        for term in [concept["name"], *concept.get("aliases", [])]:
            candidates.setdefault(term.casefold(), set()).add(concept["id"])
    return {
        term: next(iter(ids)) for term, ids in candidates.items() if len(ids) == 1
    }


def expand_aliases(root=ROOT):
    """Expand compact alias families into one machine-readable row per old ID."""
    payload = read_json(root / "aliases" / "concept-aliases.json")
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


def skill_name_for(concept, used=None):
    base = "tkl-" + slugify(concept["id"].split("/")[-1])
    if len(base) > 63:
        digest = hashlib.sha256(concept["id"].encode()).hexdigest()[:8]
        base = base[:54].rstrip("-") + "-" + digest
    if used is not None and base in used:
        digest = hashlib.sha256(concept["id"].encode()).hexdigest()[:8]
        base = base[:54].rstrip("-") + "-" + digest
    return base


def context_requirements(concept):
    domain = concept["domain"].casefold()
    required = ["the user's question or claim", "the intended analysis context"]
    optional = ["market and venue", "timeframe", "current observations", "risk constraints"]
    if concept["id"] == PARAMETERIZED_RETURN_ID:
        required.append("periods (a positive integer lookback)")
        optional.extend(["price field", "adjustment policy", "sampling frequency"])
    if any(term in domain for term in ("execution", "microstructure", "order")):
        optional.extend(["order type", "spread and liquidity conditions"])
    if any(term in domain for term in ("crypto", "contract", "derivative")):
        optional.extend(["contract specification", "funding and margin state"])
    if any(term in domain for term in ("indicator", "technical", "chart", "candlestick")):
        optional.extend(["indicator parameters", "trend and volatility regime"])
    return {"required": required, "optional": list(dict.fromkeys(optional))}


def build_profile(concept, domain_slug, source_path, core, lookup, used):
    name = skill_name_for(concept, used)
    used.add(name)
    concept_slug = slugify(concept["id"].split("/")[-1])
    triggers = list(dict.fromkeys([
        concept["name"], *concept.get("aliases", []),
        f"explain {concept['name']}", f"apply {concept['name']} to a trading question",
        f"common misconception about {concept['name']}",
    ]))
    related = []
    for relationship in concept.get("relationships", []):
        related_id = lookup.get(relationship.casefold())
        if related_id and related_id != concept["id"]:
            related.append(related_id)
    if concept["id"] == PARAMETERIZED_RETURN_ID:
        description = (
            "Calculate, explain, compare, or apply an N-period simple return for any "
            "positive-integer lookback. Use for requests such as 20-period return, "
            "multi-period simple return, lookback return, rolling return, or period "
            "simple returns; require the period count and sampling frequency."
        )
    else:
        description = (
            f"Explain, compare, or apply {concept['name']} using the library's structured "
            f"{concept['domain']} reference, including failure modes and misconceptions."
        )
    return {
        "$schema": "../../../../schemas/concept-skill.schema.json",
        "schema_version": 2,
        "version": 2,
        "skill_name": name,
        "concept_id": concept["id"],
        "display_name": concept["name"],
        "domain": concept["domain"],
        "description": description,
        "trigger_phrases": triggers,
        "supported_intents": INTENTS,
        "context_requirements": context_requirements(concept),
        "workflow": [
            "Identify whether the request asks to explain, compare, apply, or diagnose a misconception.",
            "Read references/concept.json and verify its canonical_sha256 matches this profile.",
            "Use the definition, mechanics, relationships, and citations as sourced facts.",
            "Request or label missing context before applying the concept to a market situation.",
            "Separate sourced facts from analytical inferences and unknown live conditions.",
            "State the concept's failure modes and misconceptions before giving a practical implication.",
            "Cite the carried sources and return JSON when the user requests machine-readable output.",
        ],
        "constraints": [
            "Do not invent live market data, venue rules, or user positions.",
            "Do not place orders or claim certainty or guaranteed profitability.",
            "Do not present educational analysis as personalized financial advice.",
            "Do not treat the concept alone as a complete entry, exit, or sizing rule.",
            "Flag stale or venue-specific facts that require current official documentation.",
        ],
        "output_contract": {
            "format": "human-readable-or-json-on-request",
            "required_fields": OUTPUT_FIELDS,
        },
        "core": core,
        "package_path": f"skills/concepts/{domain_slug}/{concept_slug}",
        "canonical": {"source_path": source_path, "sha256": canonical_hash(concept)},
        "related_concept_ids": list(dict.fromkeys(related)),
    }


def skill_markdown(profile):
    description = json.dumps(profile["description"], ensure_ascii=False)
    parameter_step = ""
    if profile["concept_id"] == PARAMETERIZED_RETURN_ID:
        parameter_step = (
            "\nBefore calculating or interpreting the return, require `periods` as a "
            "positive integer and identify the sampling frequency. Treat `n=1` as a "
            "valid explicit parameter; route an unqualified simple-return question to "
            "the foundational Simple return concept.\n"
        )
    return f'''---
name: {profile["skill_name"]}
description: {description}
---

# {profile["display_name"]}

Use this skill for research and decision support involving **{profile["display_name"]}**.
{parameter_step}
1. Read `skill.json` for the supported intents, required context, workflow, constraints, and output contract.
2. Read `references/concept.json` for the self-contained concept evidence and citations.
3. Keep sourced facts separate from inferences and unknown live conditions.
4. Include failure modes and misconceptions whenever the concept is applied.
5. Return the answer as JSON when requested.

Do not use this concept alone as a trade instruction. {WARNING}
'''


def openai_yaml(profile):
    short = f"Apply {profile['display_name']} with evidence and caveats"
    if len(short) > 64:
        short = f"Apply {profile['display_name']} with evidence"[:64].rstrip()
    prompt = (
        f"Use ${profile['skill_name']} to answer this question with the concept "
        "evidence, failure modes, and citations."
    )
    return (
        "interface:\n"
        f"  display_name: {json.dumps(profile['display_name'], ensure_ascii=False)}\n"
        f"  short_description: {json.dumps(short, ensure_ascii=False)}\n"
        f"  default_prompt: {json.dumps(prompt, ensure_ascii=False)}\n"
        "policy:\n"
        "  allow_implicit_invocation: false\n"
    )


def initialize_package(profile, package):
    initializer = (
        Path.home() / ".codex" / "skills" / ".system" / "skill-creator"
        / "scripts" / "init_skill.py"
    )
    if initializer.is_file():
        subprocess.run([
            sys.executable, str(initializer), profile["skill_name"],
            "--path", str(package.parent), "--resources", "references",
            "--interface", f"display_name={profile['display_name']}",
            "--interface", "short_description=Apply a trading concept with evidence and caveats",
            "--interface", f"default_prompt=Use ${profile['skill_name']} with its evidence and citations.",
        ], check=True, capture_output=True, text=True)
        generated = package.parent / profile["skill_name"]
        if generated != package:
            generated.rename(package)
    else:
        (package / "agents").mkdir(parents=True)
        (package / "references").mkdir()


def write_package(profile, concept, root=ROOT):
    package = root / profile["package_path"]
    if not package.exists():
        initialize_package(profile, package)
    (package / "agents").mkdir(parents=True, exist_ok=True)
    (package / "references").mkdir(parents=True, exist_ok=True)
    write_json(package / "skill.json", profile)
    (package / "SKILL.md").write_text(skill_markdown(profile), encoding="utf-8")
    (package / "agents" / "openai.yaml").write_text(openai_yaml(profile), encoding="utf-8")
    reference = {
        "schema_version": 1,
        "concept_id": concept["id"],
        "canonical_sha256": profile["canonical"]["sha256"],
        "source_path": profile["canonical"]["source_path"],
        "concept": {key: value for key, value in concept.items()
                    if key not in {"source_hint", "master_index"}},
    }
    write_json(package / "references" / "concept.json", reference)


def expected_profiles(root=ROOT):
    records = ordered_records(root)
    core_ids = set(read_json(root / "collections" / "core-perps.json")["concept_ids"])
    lookup = unique_term_lookup(records)
    used = set()
    profiles = []
    for concept, domain_slug, source_path in records:
        profiles.append(build_profile(
            concept, domain_slug, source_path, concept["id"] in core_ids, lookup, used
        ))
    return records, profiles


def build_catalog(root=ROOT):
    root = Path(root)
    manifest_path = root / "skills" / "manifest.json"
    old_profiles = []
    if manifest_path.is_file():
        old_profiles = read_json(manifest_path).get("skills", [])
    records, profiles = expected_profiles(root)
    concepts = {row[0]["id"]: row[0] for row in records}
    for profile in profiles:
        write_package(profile, concepts[profile["concept_id"]], root)

    expected_paths = {profile["package_path"] for profile in profiles}
    package_root = (root / "skills" / "concepts").resolve()
    for old in old_profiles:
        relative = old.get("package_path")
        if not relative or relative in expected_paths:
            continue
        candidate = (root / relative).resolve()
        if candidate.is_relative_to(package_root) and candidate.is_dir():
            shutil.rmtree(candidate)

    aliases = expand_aliases(root)
    manifest = {
        "$schema": "../schemas/skill-manifest.schema.json",
        "schema_version": 2,
        "concept_count": len(records),
        "skill_count": len(profiles),
        "alias_count": len(aliases),
        "skills": profiles,
    }
    write_json(manifest_path, manifest)
    return manifest


def parse_frontmatter(text):
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return None
    block = text.split("\n---\n", 1)[0].splitlines()[1:]
    return [match.group(1) for line in block if (match := re.match(r"^([a-z_]+):", line))]


def validate_catalog(root=ROOT):
    root = Path(root)
    errors = []
    try:
        manifest = read_json(root / "skills" / "manifest.json")
        architecture = read_json(root / "skills" / "architecture.json")
        aliases = expand_aliases(root)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return [f"skill catalog metadata unreadable: {exc}"]
    records, expected = expected_profiles(root)
    profiles = manifest.get("skills", [])
    if architecture.get("schema_version") != 2 or "catalog" not in architecture:
        errors.append("skill architecture must use the current catalog model")
    if manifest.get("schema_version") != 2:
        errors.append("skill manifest schema_version must be 2")
    if manifest.get("concept_count") != len(records):
        errors.append("skill manifest concept_count does not match canonical concepts")
    if manifest.get("skill_count") != len(profiles) or len(profiles) != len(records):
        errors.append("skill manifest must contain one skill per canonical concept")
    if manifest.get("alias_count") != len(aliases):
        errors.append("skill manifest alias_count does not match compatibility aliases")
    if profiles != expected:
        errors.append("skill manifest is not the expected deterministic catalog")
    names = [profile.get("skill_name") for profile in profiles]
    if len(names) != len(set(names)):
        errors.append("concept skill names are not unique")

    record_by_id = {row[0]["id"]: row for row in records}
    required_profile = {
        "$schema", "schema_version", "version", "skill_name", "concept_id",
        "display_name", "domain", "description", "trigger_phrases",
        "supported_intents", "context_requirements", "workflow", "constraints",
        "output_contract", "core", "package_path", "canonical",
        "related_concept_ids",
    }
    expected_paths = set()
    for index, profile in enumerate(profiles, 1):
        label = profile.get("concept_id", f"record {index}")
        if set(profile) != required_profile:
            errors.append(f"{label}: profile fields do not match schema contract")
        if profile.get("schema_version") != 2 or profile.get("version") != 2:
            errors.append(f"{label}: profile version must be 2")
        skill_name = profile.get("skill_name", "")
        if not re.fullmatch(r"[a-z0-9-]{1,63}", skill_name):
            errors.append(f"{label}: invalid skill name")
        if profile.get("supported_intents") != INTENTS:
            errors.append(f"{label}: supported intents changed")
        package = root / profile.get("package_path", "missing")
        expected_paths.add(package.resolve())
        expected_files = [
            package / "SKILL.md", package / "skill.json",
            package / "agents" / "openai.yaml", package / "references" / "concept.json",
        ]
        for path in expected_files:
            if not path.is_file():
                errors.append(f"{label}: missing {path.relative_to(root)}")
        if not all(path.is_file() for path in expected_files):
            continue
        if read_json(package / "skill.json") != profile:
            errors.append(f"{label}: skill.json differs from manifest")
        if parse_frontmatter((package / "SKILL.md").read_text(encoding="utf-8")) != ["name", "description"]:
            errors.append(f"{label}: SKILL.md frontmatter must contain only name and description")
        yaml = (package / "agents" / "openai.yaml").read_text(encoding="utf-8")
        if f"${skill_name}" not in yaml or "allow_implicit_invocation: false" not in yaml:
            errors.append(f"{label}: openai.yaml invocation policy or prompt is invalid")
        reference = read_json(package / "references" / "concept.json")
        row = record_by_id.get(label)
        if not row:
            errors.append(f"{label}: canonical concept is missing")
            continue
        digest = canonical_hash(row[0])
        if digest != profile.get("canonical", {}).get("sha256"):
            errors.append(f"{label}: canonical hash drift")
        if reference.get("canonical_sha256") != digest:
            errors.append(f"{label}: reference hash drift")

    package_root = root / "skills" / "concepts"
    actual_paths = {path.parent.resolve() for path in package_root.glob("*/*/skill.json")}
    stale = actual_paths - expected_paths
    if stale:
        errors.append(f"{len(stale)} stale concept skill packages remain")

    canonical_ids = set(record_by_id)
    canonical_names = set(names)
    if len(aliases) != 63:
        errors.append("numbered return compatibility family must expand to 63 aliases")
    for alias in aliases:
        if alias["legacy_concept_id"] in canonical_ids or alias["legacy_skill_name"] in canonical_names:
            errors.append(f"{alias['legacy_concept_id']}: alias still exists as a canonical entry")
        if alias["canonical_concept_id"] not in canonical_ids:
            errors.append(f"{alias['legacy_concept_id']}: canonical concept is missing")
        if alias["canonical_skill_name"] not in canonical_names:
            errors.append(f"{alias['legacy_skill_name']}: canonical skill is missing")
    parameterized = next((p for p in profiles if p["concept_id"] == PARAMETERIZED_RETURN_ID), None)
    if not parameterized or "periods (a positive integer lookback)" not in parameterized["context_requirements"]["required"]:
        errors.append("N-period simple return skill must require the periods parameter")
    for obsolete in ("progress.json", "batches", "evals"):
        if (root / "skills" / obsolete).exists():
            errors.append(f"obsolete rollout artifact remains: skills/{obsolete}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="rebuild the deterministic full catalog")
    sub.add_parser("validate", help="validate all skill metadata and packages")
    sub.add_parser("status", help="print current catalog counts")
    args = parser.parse_args(argv)
    if args.command == "build":
        manifest = build_catalog()
        print(
            f"built {manifest['skill_count']} concept skills and "
            f"{manifest['alias_count']} compatibility aliases"
        )
    errors = validate_catalog()
    manifest = read_json(MANIFEST_PATH)
    print(
        f"concept skills: {manifest.get('skill_count', 0)}; "
        f"compatibility aliases: {manifest.get('alias_count', 0)}"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("skill catalog valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

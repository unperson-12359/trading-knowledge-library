#!/usr/bin/env python3
"""Generate and validate installable concept-skill packages in batches of 20."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONCEPTS = ROOT / "concepts"
SKILLS = ROOT / "skills"
PROGRESS_PATH = SKILLS / "progress.json"
MANIFEST_PATH = SKILLS / "manifest.json"
CORE_PATH = ROOT / "collections" / "core-perps.json"
BATCH_SIZE = 20
TARGET_COUNT = 1500
TOTAL_BATCHES = 75
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
    if any(term in domain for term in ("execution", "microstructure", "order")):
        optional.extend(["order type", "spread and liquidity conditions"])
    if any(term in domain for term in ("crypto", "contract", "derivative")):
        optional.extend(["contract specification", "funding and margin state"])
    if any(term in domain for term in ("indicator", "technical", "chart", "candlestick")):
        optional.extend(["indicator parameters", "trend and volatility regime"])
    return {"required": required, "optional": list(dict.fromkeys(optional))}


def build_profile(concept, domain_slug, source_path, batch_number, core, lookup, used):
    name = skill_name_for(concept, used)
    used.add(name)
    concept_slug = slugify(concept["id"].split("/")[-1])
    package_path = f"skills/concepts/{domain_slug}/{concept_slug}"
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
    description = (
        f"Explain, compare, or apply {concept['name']} using the library's structured "
        f"{concept['domain']} reference, including failure modes and misconceptions."
    )
    return {
        "$schema": "../../../../schemas/concept-skill.schema.json",
        "schema_version": 1,
        "version": 1,
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
        "batch_number": batch_number,
        "package_path": package_path,
        "canonical": {
            "source_path": source_path,
            "sha256": canonical_hash(concept),
        },
        "related_concept_ids": list(dict.fromkeys(related)),
    }


def skill_markdown(profile):
    description = json.dumps(profile["description"], ensure_ascii=False)
    return f'''---
name: {profile["skill_name"]}
description: {description}
---

# {profile["display_name"]}

Use this skill for research and decision support involving **{profile["display_name"]}**.

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


def write_package(profile, concept, root=ROOT):
    package = root / profile["package_path"]
    if package.exists():
        raise FileExistsError(f"refusing to overwrite existing package: {package}")
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


def build_eval(batch_number, profiles):
    cases = []
    for profile in profiles:
        cases.append({
            "skill_name": profile["skill_name"],
            "concept_id": profile["concept_id"],
            "positive_queries": [
                profile["display_name"], f'explain {profile["display_name"]}',
            ],
            "expected_intents": INTENTS,
        })
    return {"schema_version": 1, "batch_number": batch_number, "cases": cases}


def rebuild_evals(root=ROOT):
    manifest = read_json(root / "skills" / "manifest.json")
    by_batch = {}
    for profile in manifest["skills"]:
        by_batch.setdefault(profile["batch_number"], []).append(profile)
    for batch_number, profiles in sorted(by_batch.items()):
        write_json(
            root / "skills" / "evals" / f"batch-{batch_number:03d}.json",
            build_eval(batch_number, profiles),
        )
    return len(by_batch)


def next_batch(root=ROOT):
    progress_path = root / "skills" / "progress.json"
    manifest_path = root / "skills" / "manifest.json"
    progress = read_json(progress_path)
    manifest = read_json(manifest_path)
    batch_number = progress["next_batch"]
    if batch_number is None:
        raise RuntimeError("all 75 batches are already complete")
    records = ordered_records(root)
    start = (batch_number - 1) * BATCH_SIZE
    selected = records[start:start + BATCH_SIZE]
    if len(selected) != BATCH_SIZE:
        raise RuntimeError(f"batch {batch_number} contains {len(selected)}, expected 20")
    core_ids = set(read_json(root / "collections" / "core-perps.json")["concept_ids"])
    lookup = unique_term_lookup(records)
    used = {profile["skill_name"] for profile in manifest["skills"]}
    profiles = []
    for concept, domain_slug, source_path in selected:
        profile = build_profile(
            concept, domain_slug, source_path, batch_number,
            concept["id"] in core_ids, lookup, used,
        )
        write_package(profile, concept, root)
        profiles.append(profile)
    batch = {
        "schema_version": 1,
        "batch_number": batch_number,
        "count": len(profiles),
        "range": {"start": start + 1, "end": start + len(profiles)},
        "concept_ids": [profile["concept_id"] for profile in profiles],
        "skill_names": [profile["skill_name"] for profile in profiles],
        "canonical_sha256": hashlib.sha256(
            "\n".join(profile["canonical"]["sha256"] for profile in profiles).encode()
        ).hexdigest(),
    }
    write_json(root / "skills" / "batches" / f"batch-{batch_number:03d}.json", batch)
    write_json(root / "skills" / "evals" / f"batch-{batch_number:03d}.json",
               build_eval(batch_number, profiles))
    manifest["skills"].extend(profiles)
    manifest["completed_count"] = len(manifest["skills"])
    write_json(manifest_path, manifest)
    progress["batches"].append(batch)
    progress["completed_batches"] = batch_number
    progress["completed_count"] = len(manifest["skills"])
    progress["next_batch"] = batch_number + 1 if batch_number < TOTAL_BATCHES else None
    write_json(progress_path, progress)
    return batch


def parse_frontmatter(text):
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return None
    block = text.split("\n---\n", 1)[0].splitlines()[1:]
    keys = []
    for line in block:
        match = re.match(r"^([a-z_]+):", line)
        if match:
            keys.append(match.group(1))
    return keys


def validate_catalog(root=ROOT):
    root = Path(root)
    errors = []
    try:
        progress = read_json(root / "skills" / "progress.json")
        manifest = read_json(root / "skills" / "manifest.json")
        architecture = read_json(root / "skills" / "architecture.json")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return [f"skill catalog metadata unreadable: {exc}"]
    profiles = manifest.get("skills", [])
    if architecture.get("batching", {}).get("batch_size") != BATCH_SIZE:
        errors.append("skill architecture batch size must be 20")
    if manifest.get("completed_count") != len(profiles):
        errors.append("skill manifest completed_count does not match skills")
    if progress.get("completed_count") != len(profiles):
        errors.append("skill progress completed_count does not match manifest")
    if progress.get("completed_batches") != len(progress.get("batches", [])):
        errors.append("skill progress completed_batches does not match batch records")
    expected = ordered_records(root)[:len(profiles)]
    expected_ids = [row[0]["id"] for row in expected]
    actual_ids = [profile.get("concept_id") for profile in profiles]
    if actual_ids != expected_ids:
        errors.append("skill manifest is not the expected core-first deterministic prefix")
    names = [profile.get("skill_name") for profile in profiles]
    if len(names) != len(set(names)):
        errors.append("concept skill names are not unique")
    record_by_id = {row[0]["id"]: row for row in load_concepts(root)}
    required_profile = {
        "$schema", "schema_version", "version", "skill_name", "concept_id",
        "display_name", "domain", "description", "trigger_phrases",
        "supported_intents", "context_requirements", "workflow", "constraints",
        "output_contract", "core", "batch_number", "package_path", "canonical",
        "related_concept_ids",
    }
    for index, profile in enumerate(profiles, 1):
        label = profile.get("concept_id", f"record {index}")
        if set(profile) != required_profile:
            errors.append(f"{label}: profile fields do not match schema contract")
        skill_name = profile.get("skill_name", "")
        if not re.fullmatch(r"[a-z0-9-]{1,63}", skill_name):
            errors.append(f"{label}: invalid skill name")
        if profile.get("supported_intents") != INTENTS:
            errors.append(f"{label}: supported intents changed")
        if len(profile.get("workflow", [])) < 5 or len(profile.get("constraints", [])) < 4:
            errors.append(f"{label}: workflow or constraints are incomplete")
        if len(profile.get("trigger_phrases", [])) < 2:
            errors.append(f"{label}: needs at least two trigger phrases")
        package = root / profile.get("package_path", "missing")
        expected_files = [
            package / "SKILL.md", package / "skill.json",
            package / "agents" / "openai.yaml",
            package / "references" / "concept.json",
        ]
        for path in expected_files:
            if not path.is_file():
                errors.append(f"{label}: missing {path.relative_to(root)}")
        if not all(path.is_file() for path in expected_files):
            continue
        stored = read_json(package / "skill.json")
        if stored != profile:
            errors.append(f"{label}: skill.json differs from manifest")
        keys = parse_frontmatter((package / "SKILL.md").read_text(encoding="utf-8"))
        if keys != ["name", "description"]:
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
    completed_batches = progress.get("completed_batches", 0)
    if len(profiles) != completed_batches * BATCH_SIZE:
        errors.append("every completed skill batch must contain exactly 20 concepts")
    for number in range(1, completed_batches + 1):
        batch_path = root / "skills" / "batches" / f"batch-{number:03d}.json"
        eval_path = root / "skills" / "evals" / f"batch-{number:03d}.json"
        if not batch_path.is_file() or not eval_path.is_file():
            errors.append(f"batch {number}: manifest or eval fixture missing")
            continue
        batch = read_json(batch_path)
        evaluation = read_json(eval_path)
        if batch.get("count") != BATCH_SIZE or len(batch.get("concept_ids", [])) != BATCH_SIZE:
            errors.append(f"batch {number}: must contain exactly 20 concepts")
        if len(evaluation.get("cases", [])) != BATCH_SIZE:
            errors.append(f"batch {number}: must contain exactly 20 eval cases")
    expected_next = completed_batches + 1 if completed_batches < TOTAL_BATCHES else None
    if progress.get("next_batch") != expected_next:
        errors.append("skill progress next_batch is inconsistent")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("next-batch", help="generate the next deterministic batch of 20")
    sub.add_parser("validate", help="validate all skill metadata and packages")
    sub.add_parser("status", help="print rollout progress")
    sub.add_parser("rebuild-evals", help="rebuild deterministic routing fixtures")
    args = parser.parse_args(argv)
    if args.command == "next-batch":
        batch = next_batch()
        print(json.dumps(batch, ensure_ascii=False, indent=2))
        return 0
    if args.command == "rebuild-evals":
        count = rebuild_evals()
        print(f"rebuilt routing fixtures for {count} batches")
        return 0
    errors = validate_catalog()
    progress = read_json(PROGRESS_PATH)
    print(
        f"concept skills: {progress['completed_count']}/{progress['target_count']} "
        f"in {progress['completed_batches']}/{progress['total_batches']} batches"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("skill catalog valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

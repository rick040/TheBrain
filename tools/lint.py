#!/usr/bin/env python3
"""Validate every vault note against the universal frontmatter contract
and its type's extra fields (docs/02-data-structure-and-flow.md §4-§5).

Usage:
    python3 tools/lint.py [--path vault]

Exit code is non-zero if any note fails. Used by hooks/pre-commit and
.github/workflows/lint.yml — see docs/03-engineering-build-spec.md §6.4.
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

EXCLUDED_DIR_NAMES = {"_templates", "_system", "_dashboards", "inbox"}

UNIVERSAL_REQUIRED = [
    "id",
    "type",
    "created",
    "updated",
    "source",
    "visibility",
    "freshness",
    "tags",
    "entities",
    "links",
    "status",
]

SOURCE_ENUM = {
    "manual",
    "gmail",
    "web",
    "screenshot",
    "voice",
    "owntracks",
    "health",
    "coach",
    "evaluator",
}
VISIBILITY_ENUM = {"interactive", "brain-only", "sensitive"}
FRESHNESS_ENUM = {"timeless", "dated", "pointer"}
STATUS_ENUM = {"active", "done", "archived", "revised", "retired"}

ID_PATTERN = re.compile(r"^\d{8}-\d{4}$")
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)")

# type -> {folder, extra_required (field must be present, value may be blank),
#          enums: {field: allowed values}}
# Mirrors docs/02-data-structure-and-flow.md §5 exactly.
TYPE_SPEC: dict[str, dict] = {
    "daily": {
        "folder": "daily",
        "extra_required": ["mood", "energy", "wins", "blocks"],
    },
    "client": {
        "folder": "crm/clients",
        "extra_required": ["name", "stage", "rate", "contacts", "projects"],
    },
    "project": {
        "folder": "crm/projects",
        "extra_required": ["client", "stage", "deliverables", "budget_hours", "rate"],
    },
    "invoice": {
        "folder": "crm/invoices",
        "extra_required": [
            "number", "client", "project", "period", "hours", "rate",
            "subtotal", "vat_rate", "vat", "total", "paid", "due",
        ],
    },
    "vision": {
        "folder": "goals",
        "extra_required": ["horizons"],
    },
    "okr": {
        "folder": "goals/okrs",
        "extra_required": ["period", "objective", "key_results", "linked_habits"],
    },
    "habit": {
        "folder": "goals/habits",
        "extra_required": ["name", "cadence", "streak", "linked_kr"],
    },
    "trait": {
        "folder": "self/current",
        "extra_required": [
            "domain", "statement", "polarity", "confidence", "contexts",
            "evidence", "desired_link",
        ],
        "enums": {"polarity": {"strength", "tension", "neutral"}},
    },
    "desired": {
        "folder": "self/desired",
        "extra_required": ["domain", "statement", "derivation", "commitment"],
        "enums": {"derivation": {"seed", "inferred"}},
    },
    "gap": {
        "folder": "self/gap",
        "extra_required": ["current", "desired", "size", "tension", "proposal", "hold"],
        "enums": {"size": {"subtle", "moderate", "large"}},
    },
    "decision": {
        "folder": "self/decisions",
        "extra_required": ["options", "chosen", "expected", "review_on", "outcome"],
    },
    "experiment": {
        "folder": "self/experiments",
        "extra_required": ["hypothesis", "protocol", "ends", "result"],
    },
    "review": {
        "folder": "self/reviews",
        "extra_required": ["period", "wins", "misses", "adjustments"],
    },
    "idea": {
        "folder": "ideas",
        "extra_required": ["verdict", "idea_score", "fit_score", "report_status"],
    },
    "program": {
        "folder": "health/training",
        "extra_required": ["split", "weeks", "progression_rule"],
    },
    "note": {
        "folder": "knowledge/notes",
        "extra_required": [],
    },
    "source": {
        "folder": "knowledge/sources",
        "extra_required": ["url", "author", "captured_from"],
    },
    "person": {
        "folder": "people",
        "extra_required": ["relationship", "last_contact"],
    },
}


def iter_notes(vault_path: Path):
    for md in sorted(vault_path.rglob("*.md")):
        rel = md.relative_to(vault_path)
        if rel.name == "README.md" and len(rel.parts) == 1:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
            continue
        yield md


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---"):
        return None, "file does not start with '---' frontmatter delimiter"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "malformed frontmatter (missing closing '---')"
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        return None, f"invalid YAML: {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter did not parse to a mapping"
    return data, ""


def check_iso8601(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def lint_note(md: Path, data: dict, errors: list[str]) -> None:
    def err(msg: str) -> None:
        errors.append(f"{md}: {msg}")

    for field in UNIVERSAL_REQUIRED:
        if field not in data:
            err(f"missing required field '{field}'")

    note_type = data.get("type")
    if note_type is not None and note_type not in TYPE_SPEC:
        err(f"unknown type '{note_type}' (not in the note-type catalog)")

    note_id = data.get("id")
    if note_id is not None and not ID_PATTERN.match(str(note_id)):
        err(f"id '{note_id}' does not match YYYYMMDD-HHMM")

    for field in ("created", "updated"):
        if field in data and data[field] is not None and not check_iso8601(data[field]):
            err(f"'{field}' value '{data[field]}' is not ISO 8601")

    for field, enum in (
        ("source", SOURCE_ENUM),
        ("visibility", VISIBILITY_ENUM),
        ("freshness", FRESHNESS_ENUM),
        ("status", STATUS_ENUM),
    ):
        val = data.get(field)
        if val is not None and val not in enum:
            err(f"'{field}' value '{val}' not in {sorted(enum)}")

    for field in ("tags", "entities", "links"):
        if field in data and data[field] is not None and not isinstance(data[field], list):
            err(f"'{field}' must be a list (got {type(data[field]).__name__})")

    if note_type in TYPE_SPEC:
        spec = TYPE_SPEC[note_type]
        for field in spec["extra_required"]:
            if field not in data:
                err(f"missing '{note_type}'-specific field '{field}'")
        for field, enum in spec.get("enums", {}).items():
            val = data.get(field)
            if val is not None and val not in enum:
                err(f"'{field}' value '{val}' not in {sorted(enum)}")


def check_links(md: Path, raw_text: str, note_stems: set[str], errors: list[str]) -> None:
    for match in WIKILINK_PATTERN.finditer(raw_text):
        target = match.group(1).strip()
        stem = target.rsplit("/", 1)[-1]
        if stem not in note_stems:
            errors.append(f"{md}: broken link [[{target}]] — no note with stem '{stem}' found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="vault", help="vault root (default: vault)")
    args = parser.parse_args()

    vault_path = Path(args.path)
    if not vault_path.is_dir():
        print(f"error: '{vault_path}' is not a directory", file=sys.stderr)
        return 2

    all_stems = {p.stem for p in vault_path.rglob("*.md")}

    errors: list[str] = []
    checked = 0
    for md in iter_notes(vault_path):
        checked += 1
        text = md.read_text(encoding="utf-8")
        data, parse_err = parse_frontmatter(text)
        if parse_err:
            errors.append(f"{md}: {parse_err}")
            continue
        lint_note(md, data, errors)
        check_links(md, text, all_stems, errors)

    if errors:
        print(f"lint FAILED — {len(errors)} problem(s) across {checked} note(s):\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"lint passed — {checked} note(s) OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

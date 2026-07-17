"""Weekly gap-review job — the gap engine (docs/01-build-plan.md Part B4,
docs/03-engineering-build-spec.md §8.3).

    diff self/current <-> self/desired -> upsert self/gap/*
    for each gap with hold=false: propose an OKR + keystone habit
    for gaps with no current-trait evidence yet ("uncertain"): propose an
        identity experiment instead of a goal (you don't have data to aim
        at yet — go gather some)

Nuance rules enforced, not aspirational:
    - never deletes a trait or a gap note (upsert only)
    - never auto-resolves a hold:true gap (B2, B6 — some tensions are
      meant to be lived with, not fixed)
    - every OKR/habit/experiment this writes is a DRAFT (tagged
      `proposed`) until confirmed via Telegram (app/bot/confirm.py) — see
      §12: "never silent writes to self/ or money"

Honest scope note: this needs self/current + self/desired to actually
have content in them to do anything. Phase 2 (the onboarding interview)
is parked, so on a fresh vault this job runs and finds nothing to do —
that's correct behavior, not a bug (see run()'s dry vault behavior).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.common import frontmatter
from app.llm import llm

PROPOSED_TAG = "proposed"

GAP_ASSESS_PROMPT = """You are assessing the gap between who someone is
now and who they want to become, in ONE life domain. Be nuanced — this is
not a pass/fail judgment.

Desired (aspirational): {desired_statement}

Current traits observed in this domain:
{current_summary}

Respond with ONLY a JSON object (no markdown fences):
{{
  "size": "subtle" | "moderate" | "large",
  "tension": "one honest sentence describing the gap or the tension",
  "hold": true or false,   // true if this is a contradiction to ACCEPT, not close
  "propose_okr": null or {{"objective": "...", "key_result": "...", "habit_name": "...", "habit_cadence": "..."}}
}}
Only include "propose_okr" (non-null) if hold is false and the gap is
worth an active goal right now — otherwise null.
"""


def _iter_domain_notes(vault_path: Path, subfolder: str) -> list[tuple[Path, dict]]:
    folder = vault_path / "self" / subfolder
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob("*.md")):
        fm, _ = frontmatter.read_note(path)
        out.append((path, fm))
    return out


def load_current_by_domain(vault_path: Path) -> dict[str, list[tuple[Path, dict]]]:
    by_domain: dict[str, list[tuple[Path, dict]]] = {}
    for path, fm in _iter_domain_notes(vault_path, "current"):
        domain = fm.get("domain")
        if domain:
            by_domain.setdefault(domain, []).append((path, fm))
    return by_domain


def load_desired(vault_path: Path) -> list[dict]:
    return [fm for _, fm in _iter_domain_notes(vault_path, "desired") if fm.get("domain")]


def _summarize_current(traits: list[dict]) -> str:
    if not traits:
        return "(none observed yet)"
    lines = []
    for t in traits:
        ctx = ", ".join(t.get("contexts") or []) or "no specific context recorded"
        lines.append(f"- {t.get('statement')} [{t.get('polarity')}, confidence {t.get('confidence')}, when: {ctx}]")
    return "\n".join(lines)


def _parse_json_response(response: str) -> dict:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```(json)?\n|\n```$", "", response.strip())
        return json.loads(cleaned)


def assess_gap(desired: dict, current_traits: list[tuple[Path, dict]]) -> dict:
    """Cheap short-circuit: no current-trait evidence at all in this
    domain -> "uncertain", no LLM call needed. Otherwise ask llm() for a
    nuanced assessment (see GAP_ASSESS_PROMPT)."""
    if not current_traits:
        return {"status": "uncertain", "size": None, "tension": None, "hold": False, "propose_okr": None}

    response = llm(
        GAP_ASSESS_PROMPT.format(
            desired_statement=desired.get("statement", ""),
            current_summary=_summarize_current([fm for _, fm in current_traits]),
        ),
        tier="strong",
        max_tokens=400,
    )
    result = _parse_json_response(response)
    result["status"] = "assessed"
    return result


def upsert_gap_note(
    vault_path: Path,
    domain: str,
    desired_path: Path,
    current_traits: list[tuple[Path, dict]],
    assessment: dict,
) -> Path:
    """Upsert, not create-always: re-running this on the same domain
    updates the SAME note rather than duplicating it."""
    gap_path = vault_path / "self" / "gap" / f"gap--{domain}.md"
    existing_fm = None
    if gap_path.is_file():
        existing_fm, _ = frontmatter.read_note(gap_path)

    if existing_fm and existing_fm.get("hold") is True:
        # A held tension is something the user chose to accept — don't
        # silently flip it back to an open gap just because the LLM's
        # phrasing this week differs slightly (B2/B6).
        return gap_path

    if existing_fm:
        fm = existing_fm
        fm["updated"] = frontmatter.now_iso()
    else:
        fm, _ = frontmatter.new_note_from_template(vault_path, "gap")

    fm["current"] = [f"[[{p.stem}]]" for p, _ in current_traits]
    fm["desired"] = f"[[{desired_path.stem}]]"
    fm["size"] = assessment.get("size")
    fm["tension"] = assessment.get("tension")
    fm["hold"] = bool(assessment.get("hold", False))
    fm["entities"] = fm.get("entities") or []
    frontmatter.write_note(gap_path, fm)
    return gap_path


def propose_okr_and_habit(vault_path: Path, domain: str, proposal: dict) -> tuple[Path, Path]:
    okr_fm, _ = frontmatter.new_note_from_template(
        vault_path,
        "okr",
        overrides={
            "objective": proposal["objective"],
            "key_results": [{"kr": proposal["key_result"], "target": 1, "current": 0}],
            "tags": [PROPOSED_TAG],
        },
    )
    okr_slug = re.sub(r"[^a-z0-9]+", "-", proposal["objective"].lower()).strip("-")[:40]
    okr_path = vault_path / "goals" / "okrs" / f"okr--{okr_slug}.md"
    frontmatter.write_note(okr_path, okr_fm)

    habit_fm, _ = frontmatter.new_note_from_template(
        vault_path,
        "habit",
        overrides={
            "name": proposal["habit_name"],
            "cadence": proposal["habit_cadence"],
            "streak": 0,
            "linked_kr": proposal["key_result"],
            "tags": [PROPOSED_TAG],
        },
    )
    habit_slug = re.sub(r"[^a-z0-9]+", "-", proposal["habit_name"].lower()).strip("-")[:40]
    habit_path = vault_path / "goals" / "habits" / f"habit--{habit_slug}.md"
    frontmatter.write_note(habit_path, habit_fm)

    return okr_path, habit_path


def propose_experiment(vault_path: Path, domain: str, desired: dict) -> Path:
    fm, _ = frontmatter.new_note_from_template(
        vault_path,
        "experiment",
        overrides={
            "hypothesis": (
                f"No current-trait evidence yet for '{desired.get('statement')}' "
                f"({domain}) — this experiment gathers some."
            ),
            "protocol": "2 weeks: log related activity via the vault/bot, then review.",
            "tags": [PROPOSED_TAG],
        },
    )
    path = vault_path / "self" / "experiments" / f"exp--{domain}-baseline.md"
    frontmatter.write_note(path, fm)
    return path


def run(vault_path: Path, *, dry_run: bool = False) -> dict:
    desired_notes = _iter_domain_notes(vault_path, "desired")
    current_by_domain = load_current_by_domain(vault_path)

    gaps_updated, okrs_proposed, habits_proposed, experiments_proposed = [], [], [], []

    for desired_path, desired_fm in desired_notes:
        domain = desired_fm.get("domain")
        if not domain:
            continue
        current_traits = current_by_domain.get(domain, [])
        assessment = assess_gap(desired_fm, current_traits)

        if dry_run:
            continue

        if assessment["status"] == "uncertain":
            experiments_proposed.append(propose_experiment(vault_path, domain, desired_fm))
            continue

        gap_path = upsert_gap_note(vault_path, domain, desired_path, current_traits, assessment)
        gaps_updated.append(gap_path)

        if not assessment.get("hold") and assessment.get("propose_okr"):
            okr_path, habit_path = propose_okr_and_habit(vault_path, domain, assessment["propose_okr"])
            okrs_proposed.append(okr_path)
            habits_proposed.append(habit_path)

    return {
        "domains_considered": len(desired_notes),
        "gaps_updated": gaps_updated,
        "okrs_proposed": okrs_proposed,
        "habits_proposed": habits_proposed,
        "experiments_proposed": experiments_proposed,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="vault")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run(Path(args.path), dry_run=args.dry_run)
    print(
        f"considered {result['domains_considered']} desired-self domain(s): "
        f"{len(result['gaps_updated'])} gap note(s) updated, "
        f"{len(result['okrs_proposed'])} OKR proposal(s), "
        f"{len(result['experiments_proposed'])} experiment proposal(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

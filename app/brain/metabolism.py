"""Nightly metabolism job (docs/03-engineering-build-spec.md §6.3).

Scope, honestly stated: the full spec ("reconcile with existing notes on
same entity, resolve/flag contradictions") is a lot of judgment work that
genuinely needs a mature self-model to reconcile against — Phase 2 is
parked, so there isn't real self/current data yet to reconcile. This v1
implements the two parts that are useful and testable regardless:

1. Freshness — a `dated` fact that hasn't been touched in a while gets
   flagged (tag `needs-refresh`), never silently trusted forever, never
   silently deleted (P6/P7: nuance and schema-by-convention are structural,
   not best-effort).
2. Tag-merge proposals — near-duplicate tags across the vault (e.g.
   "cli-tool" vs "cli-tools") are PROPOSED, never auto-merged; you decide.

Both write a dated report note into self/reviews/ so Obsidian/Dataview
show what the nightly pass found — no custom UI needed for this (Phase 9).
Idempotent: re-running the same night doesn't re-flag or re-report twice.
"""
from __future__ import annotations

import datetime
import difflib
from collections import Counter
from pathlib import Path

from app.common import frontmatter

EXCLUDED_DIR_NAMES = {"_templates", "_system", "_dashboards", "inbox"}
DEFAULT_MAX_AGE_DAYS = 90
STALE_TAG = "needs-refresh"


def _iter_notes(vault_path: Path):
    for md in sorted(vault_path.rglob("*.md")):
        rel = md.relative_to(vault_path)
        if rel.name == "README.md" and len(rel.parts) == 1:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
            continue
        yield md


def find_stale_notes(
    vault_path: Path, *, max_age_days: int = DEFAULT_MAX_AGE_DAYS, today: datetime.date | None = None
) -> list[Path]:
    """Flags (mutates) `dated` notes whose `updated` is older than
    max_age_days, by adding the STALE_TAG — idempotent, never re-adds it,
    never touches `timeless`/`pointer` facts."""
    today = today or datetime.date.today()
    flagged = []
    for path in _iter_notes(vault_path):
        fm, body = frontmatter.read_note(path)
        if fm.get("freshness") != "dated":
            continue
        updated = fm.get("updated")
        if not updated:
            continue
        updated_date = datetime.datetime.fromisoformat(updated).date()
        if (today - updated_date).days < max_age_days:
            continue
        tags = fm.get("tags") or []
        if STALE_TAG in tags:
            continue  # already flagged, idempotent
        fm["tags"] = [*tags, STALE_TAG]
        frontmatter.write_note(path, fm, body)
        flagged.append(path)
    return flagged


def propose_tag_merges(vault_path: Path, *, threshold: float = 0.85) -> list[tuple[str, str, int, int]]:
    """Read-only: (tag_a, tag_b, count_a, count_b) pairs that look like
    near-duplicates, most-used first. Never mutates anything — you (or a
    future confirm step) decide whether/how to merge."""
    counts: Counter[str] = Counter()
    for path in _iter_notes(vault_path):
        fm, _ = frontmatter.read_note(path)
        counts.update(fm.get("tags") or [])

    tags = sorted(counts)
    proposals = []
    seen_pairs = set()
    for i, tag_a in enumerate(tags):
        matches = difflib.get_close_matches(tag_a, tags[i + 1 :], n=3, cutoff=threshold)
        for tag_b in matches:
            pair = tuple(sorted((tag_a, tag_b)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            proposals.append((pair[0], pair[1], counts[pair[0]], counts[pair[1]]))
    proposals.sort(key=lambda p: -(p[2] + p[3]))
    return proposals


def write_report(
    vault_path: Path,
    stale: list[Path],
    tag_merges: list[tuple[str, str, int, int]],
    *,
    when: datetime.datetime | None = None,
) -> Path:
    when = when or datetime.datetime.now()
    lines = ["## Metabolism run", ""]
    if stale:
        lines.append(f"**{len(stale)} note(s) flagged `{STALE_TAG}`** (dated, untouched a while):")
        lines += [f"- [[{p.stem}]]" for p in stale]
    else:
        lines.append("No notes newly flagged as stale.")
    lines.append("")
    if tag_merges:
        lines.append("**Possible tag merges to review** (not applied automatically):")
        lines += [f"- `{a}` ({ca}) <-> `{b}` ({cb})" for a, b, ca, cb in tag_merges]
    else:
        lines.append("No tag-merge candidates found.")

    fm, _ = frontmatter.new_note_from_template(
        vault_path,
        "review",
        overrides={
            "period": when.date().isoformat(),
            "wins": [],
            "misses": [],
            "adjustments": [f"reviewed {len(stale)} stale note(s), {len(tag_merges)} tag-merge candidate(s)"],
            "tags": ["metabolism"],
        },
    )
    report_path = vault_path / "self" / "reviews" / f"review--metabolism-{when.strftime('%Y%m%d-%H%M')}.md"
    frontmatter.write_note(report_path, fm, "\n".join(lines))
    return report_path


def run(vault_path: Path, *, max_age_days: int = DEFAULT_MAX_AGE_DAYS, dry_run: bool = False) -> dict:
    """DoD (docs/03-engineering-build-spec.md §6.3): idempotent, no data
    loss, contradictions/findings surfaced not silently applied, diff is
    reviewable (it's a git diff plus a review note)."""
    if dry_run:
        stale: list[Path] = []
        for path in _iter_notes(vault_path):
            fm, _ = frontmatter.read_note(path)
            if fm.get("freshness") != "dated" or not fm.get("updated"):
                continue
            updated_date = datetime.datetime.fromisoformat(fm["updated"]).date()
            if (datetime.date.today() - updated_date).days >= max_age_days and STALE_TAG not in (fm.get("tags") or []):
                stale.append(path)
    else:
        stale = find_stale_notes(vault_path, max_age_days=max_age_days)

    tag_merges = propose_tag_merges(vault_path)
    report_path = None if dry_run else write_report(vault_path, stale, tag_merges)
    return {"stale": stale, "tag_merges": tag_merges, "report": report_path}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="vault")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run(Path(args.path), max_age_days=args.max_age_days, dry_run=args.dry_run)
    print(f"stale: {len(result['stale'])}, tag-merge candidates: {len(result['tag_merges'])}")
    if result["report"]:
        print(f"report: {result['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

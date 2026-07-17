"""Decision journal (docs/01-build-plan.md Part E, docs/03-engineering
-build-spec.md §8.5): decisions logged with an `expected` outcome and a
`review_on` date; this module finds the ones due and — once you tell the
coach the actual outcome — feeds accuracy back into
self/current/decision-style (that write-back needs Phase 2's self-model
to exist for real; until then this just surfaces what's due)."""
from __future__ import annotations

import datetime
from pathlib import Path

from app.common import frontmatter


def due_for_review(vault_path: Path, *, today: datetime.date | None = None) -> list[Path]:
    today = today or datetime.date.today()
    folder = vault_path / "self" / "decisions"
    if not folder.is_dir():
        return []
    due = []
    for path in sorted(folder.glob("*.md")):
        fm, _ = frontmatter.read_note(path)
        if fm.get("status") != "active":
            continue
        if fm.get("outcome"):
            continue  # already recorded
        review_on = fm.get("review_on")
        if not review_on:
            continue
        if datetime.date.fromisoformat(review_on) <= today:
            due.append(path)
    return due


def record_outcome(path: Path, outcome: str) -> None:
    fm, body = frontmatter.read_note(path)
    fm["outcome"] = outcome
    fm["updated"] = frontmatter.now_iso()
    frontmatter.write_note(path, fm, body)

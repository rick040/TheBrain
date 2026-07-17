"""Resurfacing / spaced repetition (docs/01-build-plan.md Part E): old
ideas and notes resurface at useful intervals — "you had a near-identical
idea in March; here's why you parked it." v1 is the honest, simple half
of that: find untouched-for-a-while candidates. The "near-identical"
similarity matching is a Phase 6-adjacent enhancement (would want the
embeddings already stored by app/embedder.py) left for later rather than
half-built now.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from app.common import frontmatter

CANDIDATE_FOLDERS = ("ideas", "knowledge/notes")


def resurface_candidates(
    vault_path: Path, *, min_age_days: int = 90, max_results: int = 3, today: datetime.date | None = None
) -> list[Path]:
    today = today or datetime.date.today()
    candidates = []
    for sub in CANDIDATE_FOLDERS:
        folder = vault_path / sub
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            fm, _ = frontmatter.read_note(path)
            if fm.get("status") != "active":
                continue
            updated = fm.get("updated")
            if not updated:
                continue
            age_days = (today - datetime.datetime.fromisoformat(updated).date()).days
            if age_days >= min_age_days:
                candidates.append((age_days, path))
    candidates.sort(key=lambda pair: -pair[0])  # oldest (most overdue) first
    return [path for _age, path in candidates[:max_results]]

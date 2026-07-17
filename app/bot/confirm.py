"""Propose -> confirm plumbing, shared by the gap engine (Phase 4) and the
coach (Phase 5) — docs/03-engineering-build-spec.md §12: "All writes to
self/ and anything involving money go through a propose -> confirm step —
the brain never silently edits your identity model or generates an
invoice without you approving it."

The mechanism: a proposal is just a normal note with `proposed` in its
`tags`. This module only knows how to (a) find them and (b) confirm/
reject one — it has no Telegram dependency, so it's testable on its own;
app/bot/telegram_bot.py wires it to `/review` + inline buttons.
"""
from __future__ import annotations

from pathlib import Path

from app.common import frontmatter

PROPOSED_TAG = "proposed"
EXCLUDED_DIR_NAMES = {"_templates", "_system", "_dashboards", "inbox"}


def list_pending(vault_path: Path) -> list[Path]:
    pending = []
    for md in sorted(vault_path.rglob("*.md")):
        rel = md.relative_to(vault_path)
        if rel.name == "README.md" and len(rel.parts) == 1:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
            continue
        fm, _ = frontmatter.read_note(md)
        if PROPOSED_TAG in (fm.get("tags") or []):
            pending.append(md)
    return pending


def describe(path: Path) -> str:
    fm, _ = frontmatter.read_note(path)
    note_type = fm.get("type", "note")
    if note_type == "okr":
        return f"OKR: {fm.get('objective', path.stem)}"
    if note_type == "habit":
        return f"Habit: {fm.get('name', path.stem)} ({fm.get('cadence', '?')})"
    if note_type == "experiment":
        return f"Experiment: {fm.get('hypothesis', path.stem)[:80]}"
    if note_type == "gap":
        return f"Gap: {fm.get('tension', path.stem)}"
    return f"{note_type}: {path.stem}"


def confirm(path: Path) -> None:
    fm, body = frontmatter.read_note(path)
    fm["tags"] = [t for t in (fm.get("tags") or []) if t != PROPOSED_TAG]
    fm["updated"] = frontmatter.now_iso()
    frontmatter.write_note(path, fm, body)


def reject(path: Path) -> None:
    fm, body = frontmatter.read_note(path)
    fm["tags"] = [t for t in (fm.get("tags") or []) if t != PROPOSED_TAG]
    fm["status"] = "archived"
    fm["updated"] = frontmatter.now_iso()
    frontmatter.write_note(path, fm, body)

"""Read/write vault notes: YAML frontmatter + Markdown body.

Shared by the normalizer and the Telegram bot so every writer produces
notes that pass tools/lint.py (docs/02-data-structure-and-flow.md §4).
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import yaml


def new_id(when: datetime.datetime | None = None) -> str:
    when = when or datetime.datetime.now()
    return when.strftime("%Y%m%d-%H%M")


def now_iso() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat(timespec="minutes")


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Split a note into (frontmatter dict, body). Raises ValueError if
    the file doesn't start with a '---' frontmatter block."""
    if not text.startswith("---"):
        raise ValueError("note does not start with '---' frontmatter delimiter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("malformed frontmatter (missing closing '---')")
    data = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    return data, body


def render(fm: dict[str, Any], body: str = "") -> str:
    yaml_block = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    body = body.strip("\n")
    if body:
        return f"---\n{yaml_block}\n---\n\n{body}\n"
    return f"---\n{yaml_block}\n---\n"


def read_note(path: Path) -> tuple[dict[str, Any], str]:
    return parse(path.read_text(encoding="utf-8"))


def write_note(path: Path, fm: dict[str, Any], body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(fm, body), encoding="utf-8")


def load_template(vault_path: Path, note_type: str) -> dict[str, Any]:
    """The blank frontmatter stub for a type, from vault/_templates/."""
    template_path = vault_path / "_templates" / f"{note_type}.md"
    fm, _ = parse(template_path.read_text(encoding="utf-8"))
    return fm


def new_note_from_template(
    vault_path: Path,
    note_type: str,
    *,
    overrides: dict[str, Any] | None = None,
    body: str = "",
) -> tuple[dict[str, Any], str]:
    """Start from the type's template, stamp id/created/updated, apply
    overrides. Caller decides the destination folder/filename."""
    fm = load_template(vault_path, note_type)
    note_id = new_id()
    fm["id"] = note_id
    fm["created"] = now_iso()
    fm["updated"] = fm["created"]
    fm.setdefault("tags", [])
    fm.setdefault("entities", [])
    fm.setdefault("links", [])
    fm.setdefault("status", "active")
    if overrides:
        fm.update(overrides)
    return fm, body

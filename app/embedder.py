"""Compute + store embeddings (docs/03-engineering-build-spec.md §6.2).

Called on-write by the normalizer, and can be run as a batch job to
(re-)embed the whole vault (e.g. after Phase 0's seed notes, or after
switching the embedding provider in vault/_system/config.yaml).
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.common import frontmatter
from app.llm import get_embedding

logger = logging.getLogger(__name__)

EXCLUDED_DIR_NAMES = {"_templates", "_system", "_dashboards", "inbox"}


def embed_note(vault_path: Path, note_path: Path, db=None) -> None:
    """Embed one note's body and upsert it, ref'd by its vault-relative
    path (matches the `ref` the RAG query in db.search_embeddings expects)."""
    fm, body = frontmatter.read_note(note_path)
    text = f"{fm.get('type', '')}\n{body}".strip()
    if not text:
        return
    vec = get_embedding(text)
    ref = str(note_path.relative_to(vault_path))
    if db is not None:
        db.upsert_embedding(ref, vec, fm.get("type", "note"))
    logger.info("embedded %s (%d dims)", ref, len(vec))


def iter_embeddable_notes(vault_path: Path):
    for md in sorted(vault_path.rglob("*.md")):
        rel = md.relative_to(vault_path)
        if rel.name == "README.md" and len(rel.parts) == 1:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts[:-1]):
            continue
        yield md


def reembed_vault(vault_path: Path, db=None) -> int:
    count = 0
    for md in iter_embeddable_notes(vault_path):
        embed_note(vault_path, md, db=db)
        count += 1
    return count


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="vault")
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="compute embeddings but skip writing to Postgres (dry run / no .env yet)",
    )
    args = parser.parse_args()

    db = None
    if not args.no_db:
        from app.common.db import DB

        db = DB()

    n = reembed_vault(Path(args.path), db=db)
    print(f"embedded {n} note(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

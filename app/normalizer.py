"""Normalize one dropped inbox item into a vault note (docs/03-engineering
-build-spec.md §6.1). Extraction step depends on what was dropped; OCR/
transcription are optional extras (lazy-imported) so this module works
without those heavy dependencies installed until you actually drop an
image or voice note.

    drop in inbox/ -> detect type -> extract text
                    -> llm() structures {title, tags, entities}
                    -> write knowledge/{notes,sources}/<type>--<slug>.md
                    -> embed -> move original to inbox/_processed/
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path

from app.common import frontmatter
from app.embedder import embed_note
from app.llm import llm

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"^https?://\S+$")

TEXT_EXTENSIONS = {".txt", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".ogg"}
PDF_EXTENSIONS = {".pdf"}

STRUCTURE_PROMPT = """You are structuring a raw capture for a personal
knowledge vault. Given the raw text below, respond with ONLY a JSON
object (no markdown fences, no commentary) with these keys:
  "title": a short slug-friendly title (3-6 words)
  "tags": a list of 1-4 lowercase kebab-case tags
  "entities": a list of 0-3 named entities (people/orgs/projects) mentioned
  "summary": one sentence summarizing the capture

Raw text:
---
{text}
---
"""


class UnsupportedDrop(Exception):
    pass


def extract_text(path: Path) -> tuple[str, str]:
    """Returns (raw_text, extraction_method)."""
    suffix = path.suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        text = path.read_text(encoding="utf-8").strip()
        if URL_PATTERN.match(text):
            return _extract_url(text), "trafilatura"
        return text, "passthrough"

    if suffix in IMAGE_EXTENSIONS:
        return _extract_image(path), "ocr"

    if suffix in AUDIO_EXTENSIONS:
        return _extract_audio(path), "whisper"

    if suffix in PDF_EXTENSIONS:
        return _extract_pdf(path), "pdf-text"

    raise UnsupportedDrop(f"don't know how to extract text from '{path.name}' ({suffix})")


def _extract_url(url: str) -> str:
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise UnsupportedDrop(f"could not fetch '{url}'")
    extracted = trafilatura.extract(downloaded, include_comments=False)
    if not extracted:
        raise UnsupportedDrop(f"trafilatura found no article text at '{url}'")
    return f"{url}\n\n{extracted}"


def _extract_image(path: Path) -> str:
    import pytesseract
    from PIL import Image

    text = pytesseract.image_to_string(Image.open(path))
    if not text.strip():
        raise UnsupportedDrop(f"OCR found no text in '{path.name}'")
    return text.strip()


def _extract_audio(path: Path) -> str:
    from faster_whisper import WhisperModel

    model = WhisperModel("base")
    segments, _ = model.transcribe(str(path))
    text = " ".join(seg.text for seg in segments).strip()
    if not text:
        raise UnsupportedDrop(f"transcription found no speech in '{path.name}'")
    return text


def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if len(text) < 20:
        raise UnsupportedDrop(
            f"'{path.name}' looks like a scanned PDF with no extractable text — "
            "OCR-over-PDF isn't wired up yet, drop page images instead for now."
        )
    return text


def structure(raw_text: str) -> dict:
    response = llm(STRUCTURE_PROMPT.format(text=raw_text[:6000]), tier="default", max_tokens=300)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Cheap models occasionally wrap JSON in fences despite instructions.
        cleaned = response.strip().strip("`")
        cleaned = re.sub(r"^json\n", "", cleaned)
        return json.loads(cleaned)


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def process_drop(vault_path: Path, drop_path: Path, db=None) -> Path:
    """Full pipeline for one file. Returns the created note's path."""
    raw_text, method = extract_text(drop_path)
    meta = structure(raw_text)

    is_source = method in ("trafilatura", "ocr", "whisper", "pdf-text") and method != "passthrough"
    note_type = "source" if is_source else "note"
    folder = "knowledge/sources" if is_source else "knowledge/notes"

    slug = slugify(meta.get("title", drop_path.stem))
    note_path = vault_path / folder / f"{note_type}--{slug}.md"
    n = 2
    while note_path.exists():
        note_path = vault_path / folder / f"{note_type}--{slug}-{n}.md"
        n += 1

    fm, _ = frontmatter.new_note_from_template(
        vault_path,
        note_type,
        overrides={
            "source": {"trafilatura": "web", "ocr": "screenshot", "whisper": "voice",
                       "pdf-text": "screenshot", "passthrough": "manual"}[method],
            "tags": meta.get("tags", []),
            "entities": meta.get("entities", []),
            **({"url": raw_text.split("\n", 1)[0]} if note_type == "source" and method == "trafilatura" else {}),
        },
    )
    body = f"{meta.get('summary', '')}\n\n{raw_text}".strip()
    frontmatter.write_note(note_path, fm, body)
    logger.info("normalized %s -> %s (via %s)", drop_path.name, note_path, method)

    embed_note(vault_path, note_path, db=db)

    processed_dir = vault_path / "inbox" / "_processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(drop_path), str(processed_dir / drop_path.name))

    return note_path

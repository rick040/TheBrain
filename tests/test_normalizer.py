import json
from pathlib import Path

import pytest

from app import normalizer


def test_slugify_basic():
    assert normalizer.slugify("Hourly Stretch Reminder CLI") == "hourly-stretch-reminder-cli"


def test_slugify_falls_back_when_empty():
    assert normalizer.slugify("!!!") == "untitled"


def test_extract_text_passthrough_for_plain_txt(tmp_path):
    p = tmp_path / "thought.txt"
    p.write_text("just a plain thought", encoding="utf-8")
    text, method = normalizer.extract_text(p)
    assert text == "just a plain thought"
    assert method == "passthrough"


def test_extract_text_unsupported_suffix_raises(tmp_path):
    p = tmp_path / "weird.xyz"
    p.write_text("?", encoding="utf-8")
    with pytest.raises(normalizer.UnsupportedDrop):
        normalizer.extract_text(p)


def test_structure_parses_llm_json(monkeypatch):
    fake_response = json.dumps(
        {"title": "Test Title", "tags": ["a"], "entities": [], "summary": "a summary"}
    )
    monkeypatch.setattr(normalizer, "llm", lambda *a, **k: fake_response)
    result = normalizer.structure("raw text")
    assert result["title"] == "Test Title"
    assert result["tags"] == ["a"]


def test_structure_strips_markdown_fences(monkeypatch):
    fenced = "```json\n" + json.dumps({"title": "T", "tags": [], "entities": [], "summary": "s"}) + "\n```"
    monkeypatch.setattr(normalizer, "llm", lambda *a, **k: fenced)
    result = normalizer.structure("raw text")
    assert result["title"] == "T"


def test_process_drop_writes_note_and_moves_original(monkeypatch, tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "_templates").mkdir(parents=True)
    (vault_path / "_templates" / "note.md").write_text(
        "---\nid:\ntype: note\ncreated:\nupdated:\nsource: manual\n"
        "visibility: interactive\nfreshness: dated\ntags: []\nentities: []\n"
        "links: []\nstatus: active\n---\n",
        encoding="utf-8",
    )
    (vault_path / "inbox").mkdir()
    drop = vault_path / "inbox" / "capture.txt"
    drop.write_text("a captured thought about testing", encoding="utf-8")

    fake_response = json.dumps(
        {"title": "Captured Thought", "tags": ["test"], "entities": [], "summary": "a summary"}
    )
    monkeypatch.setattr(normalizer, "llm", lambda *a, **k: fake_response)
    monkeypatch.setattr(normalizer, "embed_note", lambda *a, **k: None)  # no DB in this test

    note_path = normalizer.process_drop(vault_path, drop, db=None)

    assert note_path.exists()
    assert note_path.parent.name == "notes"
    assert not drop.exists()
    assert (vault_path / "inbox" / "_processed" / "capture.txt").exists()

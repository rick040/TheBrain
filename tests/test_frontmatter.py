from pathlib import Path

import pytest

from app.common import frontmatter

VAULT_PATH = Path(__file__).resolve().parents[1] / "vault"


def test_render_and_parse_round_trip():
    fm = {"id": "20260716-0900", "type": "note", "tags": ["a", "b"], "entities": []}
    text = frontmatter.render(fm, "body text here")
    parsed_fm, parsed_body = frontmatter.parse(text)
    assert parsed_fm == fm
    assert parsed_body.strip() == "body text here"


def test_parse_rejects_missing_frontmatter():
    with pytest.raises(ValueError):
        frontmatter.parse("just some text, no frontmatter")


def test_new_id_matches_lint_pattern():
    note_id = frontmatter.new_id()
    assert len(note_id) == 13  # YYYYMMDD-HHMM
    assert note_id[8] == "-"


@pytest.mark.parametrize("note_type", ["note", "source", "client", "project", "habit", "trait", "gap"])
def test_load_template_for_every_type_that_exists(note_type):
    fm = frontmatter.load_template(VAULT_PATH, note_type)
    assert fm["type"] == note_type


def test_new_note_from_template_stamps_id_and_defaults():
    fm, body = frontmatter.new_note_from_template(
        VAULT_PATH, "note", overrides={"tags": ["test"]}
    )
    assert fm["id"]
    assert fm["created"] == fm["updated"]
    assert fm["tags"] == ["test"]
    assert fm["status"] == "active"
    assert body == ""

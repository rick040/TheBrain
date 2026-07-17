from app.bot import confirm
from app.common import frontmatter

UNIVERSAL = dict(
    created="2026-07-01T09:00",
    updated="2026-07-01T09:00",
    source="manual",
    visibility="interactive",
    freshness="dated",
    entities=[],
    links=[],
    status="active",
)


def _write(vault_path, rel_path, *, note_type, tags, **extra):
    fm = {"id": "20260701-0900", "type": note_type, "tags": tags, **UNIVERSAL, **extra}
    frontmatter.write_note(vault_path / rel_path, fm)
    return vault_path / rel_path


def test_list_pending_finds_proposed_tagged_notes(tmp_path):
    vault_path = tmp_path / "vault"
    _write(vault_path, "goals/okrs/okr--a.md", note_type="okr", tags=["proposed"], objective="x", key_results=[], linked_habits=[], period="2026-Q3")
    _write(vault_path, "goals/okrs/okr--b.md", note_type="okr", tags=[], objective="y", key_results=[], linked_habits=[], period="2026-Q3")

    pending = confirm.list_pending(vault_path)
    assert len(pending) == 1
    assert pending[0].name == "okr--a.md"


def test_list_pending_excludes_templates_and_system(tmp_path):
    vault_path = tmp_path / "vault"
    _write(vault_path, "_templates/okr.md", note_type="okr", tags=["proposed"], objective="", key_results=[], linked_habits=[], period="")
    pending = confirm.list_pending(vault_path)
    assert pending == []


def test_confirm_removes_proposed_tag_keeps_status_active(tmp_path):
    vault_path = tmp_path / "vault"
    path = _write(
        vault_path, "goals/habits/habit--a.md", note_type="habit", tags=["proposed"],
        name="Deep work", cadence="daily", streak=0, linked_kr=None,
    )
    confirm.confirm(path)
    fm, _ = frontmatter.read_note(path)
    assert "proposed" not in fm["tags"]
    assert fm["status"] == "active"


def test_reject_archives_and_removes_proposed_tag(tmp_path):
    vault_path = tmp_path / "vault"
    path = _write(
        vault_path, "self/experiments/exp--a.md", note_type="experiment", tags=["proposed"],
        hypothesis="h", protocol="p", ends=None, result=None,
    )
    confirm.reject(path)
    fm, _ = frontmatter.read_note(path)
    assert "proposed" not in fm["tags"]
    assert fm["status"] == "archived"


def test_describe_formats_by_type(tmp_path):
    vault_path = tmp_path / "vault"
    okr_path = _write(
        vault_path, "goals/okrs/okr--x.md", note_type="okr", tags=["proposed"],
        objective="Ship the thing", key_results=[], linked_habits=[], period="2026-Q3",
    )
    habit_path = _write(
        vault_path, "goals/habits/habit--x.md", note_type="habit", tags=["proposed"],
        name="Morning pages", cadence="daily", streak=0, linked_kr=None,
    )
    assert "Ship the thing" in confirm.describe(okr_path)
    assert "Morning pages" in confirm.describe(habit_path)

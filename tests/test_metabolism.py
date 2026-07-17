import datetime

from app.brain import metabolism
from app.common import frontmatter

UNIVERSAL = dict(
    source="manual",
    visibility="interactive",
    tags=[],
    entities=[],
    links=[],
    status="active",
)


def _write_note(vault_path, rel_path, *, freshness, updated, note_type="note", tags=None):
    fm = {
        "id": "20260101-0900",
        "type": note_type,
        "created": updated,
        "updated": updated,
        "freshness": freshness,
        **{**UNIVERSAL, "tags": tags or []},
    }
    frontmatter.write_note(vault_path / rel_path, fm)
    return vault_path / rel_path


def test_find_stale_notes_flags_old_dated_facts(tmp_path):
    vault_path = tmp_path / "vault"
    _write_note(
        vault_path, "knowledge/notes/note--old.md",
        freshness="dated", updated="2026-01-01T09:00",
    )
    stale = metabolism.find_stale_notes(vault_path, max_age_days=90, today=datetime.date(2026, 7, 1))
    assert len(stale) == 1
    fm, _ = frontmatter.read_note(stale[0])
    assert metabolism.STALE_TAG in fm["tags"]


def test_find_stale_notes_is_idempotent(tmp_path):
    vault_path = tmp_path / "vault"
    _write_note(vault_path, "knowledge/notes/note--old.md", freshness="dated", updated="2026-01-01T09:00")
    today = datetime.date(2026, 7, 1)
    first = metabolism.find_stale_notes(vault_path, max_age_days=90, today=today)
    second = metabolism.find_stale_notes(vault_path, max_age_days=90, today=today)
    assert len(first) == 1
    assert len(second) == 0  # already flagged, not re-flagged


def test_find_stale_notes_ignores_timeless_and_pointer(tmp_path):
    vault_path = tmp_path / "vault"
    _write_note(vault_path, "knowledge/notes/note--a.md", freshness="timeless", updated="2020-01-01T09:00")
    _write_note(vault_path, "knowledge/notes/note--b.md", freshness="pointer", updated="2020-01-01T09:00")
    stale = metabolism.find_stale_notes(vault_path, max_age_days=90, today=datetime.date(2026, 7, 1))
    assert stale == []


def test_find_stale_notes_ignores_recent_dated_facts(tmp_path):
    vault_path = tmp_path / "vault"
    _write_note(vault_path, "knowledge/notes/note--recent.md", freshness="dated", updated="2026-06-25T09:00")
    stale = metabolism.find_stale_notes(vault_path, max_age_days=90, today=datetime.date(2026, 7, 1))
    assert stale == []


def test_propose_tag_merges_finds_near_duplicates(tmp_path):
    vault_path = tmp_path / "vault"
    _write_note(vault_path, "knowledge/notes/note--a.md", freshness="dated", updated="2026-07-01T09:00", tags=["cli-tool"])
    _write_note(vault_path, "knowledge/notes/note--b.md", freshness="dated", updated="2026-07-01T09:00", tags=["cli-tools"])
    _write_note(vault_path, "knowledge/notes/note--c.md", freshness="dated", updated="2026-07-01T09:00", tags=["wellness"])
    proposals = metabolism.propose_tag_merges(vault_path, threshold=0.8)
    pairs = [(a, b) for a, b, _, _ in proposals]
    assert ("cli-tool", "cli-tools") in pairs
    assert not any("wellness" in p for p in pairs)


def test_run_dry_run_does_not_mutate(tmp_path):
    vault_path = tmp_path / "vault"
    path = _write_note(vault_path, "knowledge/notes/note--old.md", freshness="dated", updated="2026-01-01T09:00")
    before = path.read_text(encoding="utf-8")
    result = metabolism.run(vault_path, max_age_days=90, dry_run=True)
    after = path.read_text(encoding="utf-8")
    assert before == after
    assert len(result["stale"]) == 1  # still reports what it WOULD do
    assert result["report"] is None


def test_run_writes_a_report_note(tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "_templates").mkdir(parents=True)
    (vault_path / "_templates" / "review.md").write_text(
        "---\nid:\ntype: review\ncreated:\nupdated:\nsource: manual\n"
        "visibility: interactive\nfreshness: dated\ntags: []\nentities: []\n"
        "links: []\nstatus: active\nperiod:\nwins: []\nmisses: []\nadjustments: []\n---\n",
        encoding="utf-8",
    )
    _write_note(vault_path, "knowledge/notes/note--old.md", freshness="dated", updated="2026-01-01T09:00")
    result = metabolism.run(vault_path, max_age_days=90, dry_run=False)
    assert result["report"].is_file()
    assert "review--metabolism-" in result["report"].name

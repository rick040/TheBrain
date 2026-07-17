import datetime

from app.brain import decisions
from app.common import frontmatter

UNIVERSAL = dict(
    created="2026-07-01T09:00",
    updated="2026-07-01T09:00",
    source="manual",
    visibility="interactive",
    freshness="dated",
    tags=[],
    entities=[],
    links=[],
    status="active",
)


def _write_decision(vault_path, slug, *, review_on, outcome=None, status="active"):
    fm = {
        "id": "20260701-0900", "type": "decision", **{**UNIVERSAL, "status": status},
        "options": ["a", "b"], "chosen": "a", "expected": "it works out",
        "review_on": review_on, "outcome": outcome,
    }
    frontmatter.write_note(vault_path / "self" / "decisions" / f"decision--{slug}.md", fm)
    return vault_path / "self" / "decisions" / f"decision--{slug}.md"


def test_due_for_review_includes_past_due_undecided(tmp_path):
    vault_path = tmp_path / "vault"
    _write_decision(vault_path, "past", review_on="2026-07-01")
    _write_decision(vault_path, "future", review_on="2026-12-01")
    _write_decision(vault_path, "already-recorded", review_on="2026-07-01", outcome="worked out fine")

    due = decisions.due_for_review(vault_path, today=datetime.date(2026, 7, 17))
    names = {p.stem for p in due}
    assert names == {"decision--past"}


def test_due_for_review_ignores_non_active(tmp_path):
    vault_path = tmp_path / "vault"
    _write_decision(vault_path, "archived", review_on="2026-07-01", status="archived")
    due = decisions.due_for_review(vault_path, today=datetime.date(2026, 7, 17))
    assert due == []


def test_record_outcome_sets_field(tmp_path):
    vault_path = tmp_path / "vault"
    path = _write_decision(vault_path, "past", review_on="2026-07-01")
    decisions.record_outcome(path, "turned out better than expected")
    fm, _ = frontmatter.read_note(path)
    assert fm["outcome"] == "turned out better than expected"

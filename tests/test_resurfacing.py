import datetime

from app.brain import resurfacing
from app.common import frontmatter

UNIVERSAL = dict(
    created="2026-01-01T09:00",
    source="manual",
    visibility="interactive",
    freshness="dated",
    tags=[],
    entities=[],
    links=[],
    status="active",
)


def _write_idea(vault_path, slug, *, updated):
    fm = {
        "id": "20260101-0900", "type": "idea", **{**UNIVERSAL, "updated": updated},
        "verdict": None, "idea_score": None, "fit_score": None, "report_status": "none",
    }
    frontmatter.write_note(vault_path / "ideas" / f"idea--{slug}.md", fm)


def test_resurface_candidates_orders_oldest_first(tmp_path):
    vault_path = tmp_path / "vault"
    _write_idea(vault_path, "old", updated="2026-01-01T09:00")
    _write_idea(vault_path, "older", updated="2025-06-01T09:00")
    _write_idea(vault_path, "recent", updated="2026-07-10T09:00")

    result = resurfacing.resurface_candidates(vault_path, min_age_days=90, today=datetime.date(2026, 7, 17))
    names = [p.stem for p in result]
    assert names == ["idea--older", "idea--old"]  # oldest (most overdue) first, recent excluded


def test_resurface_candidates_respects_max_results(tmp_path):
    vault_path = tmp_path / "vault"
    for i in range(5):
        _write_idea(vault_path, f"idea{i}", updated="2025-01-01T09:00")
    result = resurfacing.resurface_candidates(vault_path, min_age_days=90, max_results=2, today=datetime.date(2026, 7, 17))
    assert len(result) == 2


def test_resurface_candidates_empty_when_nothing_old_enough(tmp_path):
    vault_path = tmp_path / "vault"
    _write_idea(vault_path, "fresh", updated="2026-07-15T09:00")
    result = resurfacing.resurface_candidates(vault_path, min_age_days=90, today=datetime.date(2026, 7, 17))
    assert result == []

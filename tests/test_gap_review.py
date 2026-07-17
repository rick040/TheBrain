import json
import shutil
from pathlib import Path

import pytest

from app.brain import gap_review
from app.common import frontmatter

REPO_ROOT = Path(__file__).resolve().parents[1]

UNIVERSAL = dict(
    created="2026-07-01T09:00",
    updated="2026-07-01T09:00",
    source="manual",
    visibility="sensitive",
    freshness="timeless",
    tags=[],
    entities=[],
    links=[],
    status="active",
)


@pytest.fixture
def vault_path(tmp_path):
    vp = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "vault" / "_templates", vp / "_templates")
    return vp


def _write_trait(vault_path, slug, *, domain, statement, polarity="tension", confidence=0.6):
    fm = {
        "id": "20260701-0900",
        "type": "trait",
        **UNIVERSAL,
        "domain": domain,
        "statement": statement,
        "polarity": polarity,
        "confidence": confidence,
        "contexts": [],
        "evidence": [],
        "desired_link": None,
    }
    frontmatter.write_note(vault_path / "self" / "current" / f"{slug}.md", fm)


def _write_desired(vault_path, slug, *, domain, statement):
    fm = {
        "id": "20260701-0900",
        "type": "desired",
        **UNIVERSAL,
        "domain": domain,
        "statement": statement,
        "derivation": "seed",
        "commitment": None,
    }
    frontmatter.write_note(vault_path / "self" / "desired" / f"{slug}.md", fm)
    return vault_path / "self" / "desired" / f"{slug}.md"


def test_assess_gap_uncertain_when_no_current_traits_skips_llm(vault_path, monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("llm() should not be called when there's no current-trait evidence")

    monkeypatch.setattr(gap_review, "llm", boom)
    result = gap_review.assess_gap({"statement": "wants X", "domain": "working-style"}, [])
    assert result["status"] == "uncertain"


def test_assess_gap_calls_llm_and_parses(vault_path, monkeypatch):
    fake_response = json.dumps(
        {"size": "moderate", "tension": "a tension", "hold": False,
         "propose_okr": {"objective": "Finish things", "key_result": "Ship 3 projects",
                          "habit_name": "Daily wrap-up", "habit_cadence": "daily"}}
    )
    monkeypatch.setattr(gap_review, "llm", lambda *a, **k: fake_response)
    desired_path = _write_desired(vault_path, "identity", domain="working-style", statement="finisher")
    _write_trait(vault_path, "working-style--fades", domain="working-style", statement="fades after 2 weeks")
    current = gap_review.load_current_by_domain(vault_path)["working-style"]
    result = gap_review.assess_gap({"statement": "finisher", "domain": "working-style"}, current)
    assert result["status"] == "assessed"
    assert result["size"] == "moderate"
    assert result["propose_okr"]["objective"] == "Finish things"


def test_upsert_gap_note_creates_with_real_links(vault_path):
    desired_path = _write_desired(vault_path, "identity", domain="working-style", statement="finisher")
    _write_trait(vault_path, "working-style--fades", domain="working-style", statement="fades after 2 weeks")
    current = gap_review.load_current_by_domain(vault_path)["working-style"]

    assessment = {"size": "moderate", "tension": "text", "hold": False}
    gap_path = gap_review.upsert_gap_note(vault_path, "working-style", desired_path, current, assessment)

    fm, _ = frontmatter.read_note(gap_path)
    assert fm["hold"] is False
    assert "[[working-style--fades]]" in fm["current"]
    assert fm["desired"] == "[[identity]]"


def test_upsert_gap_note_never_overwrites_a_held_gap(vault_path):
    desired_path = _write_desired(vault_path, "identity", domain="working-style", statement="finisher")
    _write_trait(vault_path, "working-style--fades", domain="working-style", statement="fades")
    current = gap_review.load_current_by_domain(vault_path)["working-style"]

    gap_path = gap_review.upsert_gap_note(
        vault_path, "working-style", desired_path, current, {"size": "subtle", "tension": "held tension", "hold": True}
    )
    fm_before, _ = frontmatter.read_note(gap_path)
    assert fm_before["hold"] is True

    # A later run says hold=False — but a user-accepted held tension must not flip back silently.
    gap_review.upsert_gap_note(
        vault_path, "working-style", desired_path, current, {"size": "large", "tension": "different", "hold": False}
    )
    fm_after, _ = frontmatter.read_note(gap_path)
    assert fm_after["hold"] is True
    assert fm_after["tension"] == "held tension"


def test_propose_okr_and_habit_are_tagged_proposed(vault_path):
    okr_path, habit_path = gap_review.propose_okr_and_habit(
        vault_path, "working-style",
        {"objective": "Finish things", "key_result": "Ship 3 projects",
         "habit_name": "Daily wrap-up", "habit_cadence": "daily"},
    )
    okr_fm, _ = frontmatter.read_note(okr_path)
    habit_fm, _ = frontmatter.read_note(habit_path)
    assert gap_review.PROPOSED_TAG in okr_fm["tags"]
    assert gap_review.PROPOSED_TAG in habit_fm["tags"]
    assert okr_fm["objective"] == "Finish things"
    assert habit_fm["cadence"] == "daily"


def test_propose_experiment_is_tagged_proposed(vault_path):
    path = gap_review.propose_experiment(vault_path, "working-style", {"statement": "finisher"})
    fm, _ = frontmatter.read_note(path)
    assert gap_review.PROPOSED_TAG in fm["tags"]
    assert "finisher" in fm["hypothesis"]


def test_run_end_to_end_uncertain_domain_gets_an_experiment_not_a_gap(vault_path):
    _write_desired(vault_path, "north-star", domain="fitness", statement="consistently active")
    result = gap_review.run(vault_path, dry_run=False)
    assert result["domains_considered"] == 1
    assert len(result["experiments_proposed"]) == 1
    assert result["gaps_updated"] == []


def test_run_dry_run_writes_nothing(vault_path, monkeypatch):
    fake_response = json.dumps(
        {"size": "moderate", "tension": "t", "hold": False, "propose_okr": None}
    )
    monkeypatch.setattr(gap_review, "llm", lambda *a, **k: fake_response)
    _write_desired(vault_path, "identity", domain="working-style", statement="finisher")
    _write_trait(vault_path, "working-style--fades", domain="working-style", statement="fades")

    gap_dir = vault_path / "self" / "gap"
    before = sorted(gap_dir.glob("*.md")) if gap_dir.is_dir() else []
    gap_review.run(vault_path, dry_run=True)
    after = sorted(gap_dir.glob("*.md")) if gap_dir.is_dir() else []
    assert before == after == []

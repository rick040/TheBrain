import json

import pytest

from app.evaluator import idea_intake
from app.common import frontmatter

FAKE_VERDICT = {
    "intake_questions": ["What problem?", "For whom?", "Unfair advantage?"],
    "verdict": "Conditional Go",
    "idea_score": 7,
    "fit_score": 6,
    "why": "Solid niche, unproven distribution.",
    "biggest_risk": "Customer acquisition cost",
    "must_be_true": "A cheap channel to the first 10 customers exists",
}


def test_load_self_context_empty_vault(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    context = idea_intake._load_self_context(vault_path)
    assert "no self-model data yet" in context


def test_load_self_context_reads_traits(tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "self" / "current").mkdir(parents=True)
    fm = {
        "id": "20260701-0900", "type": "trait", "created": "2026-07-01T09:00", "updated": "2026-07-01T09:00",
        "source": "manual", "visibility": "sensitive", "freshness": "timeless", "tags": [], "entities": [],
        "links": [], "status": "active", "domain": "skills", "statement": "Strong at backend systems",
        "polarity": "strength", "confidence": 0.7, "contexts": [], "evidence": [], "desired_link": None,
    }
    frontmatter.write_note(vault_path / "self" / "current" / "skills--backend.md", fm)
    context = idea_intake._load_self_context(vault_path)
    assert "Strong at backend systems" in context


def test_fast_verdict_parses_llm_json(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    monkeypatch.setattr(idea_intake, "llm", lambda *a, **k: json.dumps(FAKE_VERDICT))
    result = idea_intake.fast_verdict(vault_path, "A CLI that reminds you to stretch")
    assert result["verdict"] == "Conditional Go"
    assert result["idea_score"] == 7


def test_fast_verdict_strips_markdown_fences(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    fenced = "```json\n" + json.dumps(FAKE_VERDICT) + "\n```"
    monkeypatch.setattr(idea_intake, "llm", lambda *a, **k: fenced)
    result = idea_intake.fast_verdict(vault_path, "idea")
    assert result["fit_score"] == 6


def test_format_verdict_card_contains_key_fields():
    card = idea_intake.format_verdict_card(FAKE_VERDICT)
    assert "Conditional Go" in card
    assert "7/10" in card
    assert "6/10" in card
    assert "Customer acquisition cost" in card
    assert "What problem?" in card
    assert "biz-eval Skill" in card

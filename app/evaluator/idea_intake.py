"""Stage 1+2 of the Business-Idea Evaluator (docs/03-engineering-build
-spec.md §9): intake + a fast, no-web verdict — the part that runs
inside the Telegram bot itself, no MCP server needed. Stage 3 (the deep,
web-researched report) is the MCP server + `biz-eval` Skill
(app/evaluator/mcp_server.py, .claude/skills/biz-eval/SKILL.md), run from
Claude Code/Desktop, not here.

Honest simplification: the spec describes an interactive back-and-forth
intake (5-8 questions, one at a time). A single Telegram command can't
hold that conversation state cleanly without a lot of extra machinery, so
this asks for everything in one shot: given the idea description (plus
whatever self-model context exists), it returns the intake questions AND
a preliminary verdict together, clearly labeled preliminary. Answering
the questions in more detail and re-running /idea sharpens it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.llm import llm

FAST_VERDICT_PROMPT = """You are a sharp, honest startup analyst doing a
FAST intake pass on a business idea — no web research, just judgment.

Idea, as described: {idea_text}

What's known about the person evaluating it (may be empty — treat gaps
as unknowns, not red flags):
{self_context}

Respond with ONLY a JSON object (no markdown fences):
{{
  "intake_questions": ["5 to 8 sharp questions you'd want answered before a deep report"],
  "verdict": "Go" | "Conditional Go" | "No-Go",
  "idea_score": 1-10,
  "fit_score": 1-10,
  "why": "one or two honest sentences",
  "biggest_risk": "one sentence",
  "must_be_true": "the one assumption that, if wrong, kills this"
}}
Be honest, not encouraging — an inflated verdict is worse than a blunt one.
"""


def _load_self_context(vault_path: Path) -> str:
    """Best-effort — self/current is likely empty until Phase 2 seeds it;
    an empty context is a normal, expected input here, not an error."""
    blocks = []
    current_dir = vault_path / "self" / "current"
    if current_dir.is_dir():
        for path in sorted(current_dir.glob("*.md"))[:10]:
            from app.common import frontmatter

            fm, _ = frontmatter.read_note(path)
            if fm.get("statement"):
                blocks.append(f"- ({fm.get('domain')}) {fm.get('statement')}")
    return "\n".join(blocks) or "(no self-model data yet — Phase 2 hasn't been seeded)"


def _parse_json_response(response: str) -> dict:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```(json)?\n|\n```$", "", response.strip())
        return json.loads(cleaned)


def fast_verdict(vault_path: Path, idea_text: str) -> dict:
    self_context = _load_self_context(vault_path)
    response = llm(
        FAST_VERDICT_PROMPT.format(idea_text=idea_text, self_context=self_context),
        tier="default",
        max_tokens=600,
    )
    return _parse_json_response(response)


def format_verdict_card(verdict: dict) -> str:
    lines = [
        f"Verdict: {verdict['verdict']}  ·  Idea {verdict['idea_score']}/10  ·  Fit {verdict['fit_score']}/10",
        "",
        verdict["why"],
        "",
        f"Biggest risk: {verdict['biggest_risk']}",
        f"Must be true: {verdict['must_be_true']}",
        "",
        "Intake questions worth answering before a deep report:",
    ]
    lines += [f"  {i+1}. {q}" for i, q in enumerate(verdict.get("intake_questions", []))]
    lines.append("")
    lines.append(
        "For the deep, web-researched report: use the biz-eval Skill in "
        "Claude Code/Desktop (connects to app/evaluator/mcp_server.py) — "
        "that needs real web research, which this bot alone can't do well."
    )
    return "\n".join(lines)

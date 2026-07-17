"""MCP server for the Business-Idea Evaluator (Phase 6 — docs/03-
engineering-build-spec.md §9). Exposes SCOPED vault access — only
self/current, self/desired, and ideas/, never finances/clients/health —
plus a URL-fetch tool, to the `biz-eval` Claude Skill
(.claude/skills/biz-eval/SKILL.md).

Run with: python3 -m app.evaluator.mcp_server
Then connect it as an MCP server in Claude Code/Desktop and invoke the
biz-eval skill ("evaluate this idea: ...").

Honest scope note: `fetch_url` reads a page you already have the address
for — it is NOT a search engine. Real web SEARCH (discovering pages for
a query, needed for the deep report's market sizing) needs a search API
key (Brave/Serper/etc.) this build doesn't have configured; use whatever
web-search tool is available in your Claude Code/Desktop session for
discovery, and this tool to fetch+extract specific pages to cite.
"""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.common import frontmatter
from app.normalizer import _extract_url

VAULT_PATH = Path("vault")
READABLE_PREFIXES = ("self/current", "self/desired", "ideas")

mcp = FastMCP("thebrain-biz-eval")


def _is_in_scope(rel_path: str) -> bool:
    return rel_path.startswith(READABLE_PREFIXES)


def read_vault_note(path: str) -> str:
    """Read a note from the scoped vault area (self/current/, self/desired/,
    ideas/ only — never finances, clients, or health)."""
    if not _is_in_scope(path):
        raise ValueError(f"'{path}' is outside the evaluator's scope (self/current, self/desired, ideas only)")
    full = VAULT_PATH / path
    if not full.is_file():
        raise FileNotFoundError(path)
    return full.read_text(encoding="utf-8")


def list_self_model() -> list[str]:
    """Available self/current + self/desired note paths, so the skill can
    decide what's relevant to THIS idea before reading full notes."""
    paths: list[str] = []
    for sub in ("self/current", "self/desired"):
        folder = VAULT_PATH / sub
        if folder.is_dir():
            paths += [str(p.relative_to(VAULT_PATH)) for p in sorted(folder.glob("*.md"))]
    return paths


def list_past_ideas() -> list[str]:
    """Past idea slugs, so a new idea can be checked against ones already
    captured (build plan Part E: "you had a similar idea in March...")."""
    folder = VAULT_PATH / "ideas"
    if not folder.is_dir():
        return []
    return [p.stem for p in sorted(folder.glob("idea--*.md"))]


def write_idea_report(slug: str, report_body: str) -> str:
    """Write the deep-report BODY for an existing ideas/idea--<slug>.md
    note (created by /idea via the Telegram bot first — this tool doesn't
    create the frontmatter/verdict, only appends the researched report)."""
    path = VAULT_PATH / "ideas" / f"idea--{slug}.md"
    if not path.is_file():
        raise FileNotFoundError(f"no idea note at {path} — capture it with /idea in Telegram first")
    fm, _ = frontmatter.read_note(path)
    fm["report_status"] = "done"
    fm["updated"] = frontmatter.now_iso()
    frontmatter.write_note(path, fm, report_body)
    return str(path.relative_to(VAULT_PATH))


def fetch_url(url: str) -> str:
    """Fetch + extract the readable text of a URL, for citing sources in
    the deep report. Not a search engine — you need the URL already."""
    return _extract_url(url)


for _fn in (read_vault_note, list_self_model, list_past_ideas, write_idea_report, fetch_url):
    mcp.tool()(_fn)


if __name__ == "__main__":
    mcp.run()

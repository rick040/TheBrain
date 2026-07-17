import subprocess
import sys
from pathlib import Path

import pytest

from app.evaluator import mcp_server
from app.common import frontmatter

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def vault(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    monkeypatch.setattr(mcp_server, "VAULT_PATH", vault_path)
    return vault_path


def test_read_vault_note_refuses_out_of_scope_paths(vault):
    with pytest.raises(ValueError):
        mcp_server.read_vault_note("crm/invoices/secret.md")


def test_read_vault_note_reads_in_scope_files(vault):
    (vault / "self" / "current").mkdir(parents=True)
    (vault / "self" / "current" / "values.md").write_text("---\ntype: trait\n---\nhello", encoding="utf-8")
    text = mcp_server.read_vault_note("self/current/values.md")
    assert "hello" in text


def test_read_vault_note_missing_file_raises(vault):
    with pytest.raises(FileNotFoundError):
        mcp_server.read_vault_note("self/current/nope.md")


def test_list_self_model_empty_and_populated(vault):
    assert mcp_server.list_self_model() == []
    (vault / "self" / "desired").mkdir(parents=True)
    (vault / "self" / "desired" / "north-star.md").write_text("---\ntype: desired\n---\n", encoding="utf-8")
    assert mcp_server.list_self_model() == ["self/desired/north-star.md"]


def test_list_past_ideas(vault):
    assert mcp_server.list_past_ideas() == []
    (vault / "ideas").mkdir(parents=True)
    (vault / "ideas" / "idea--widget.md").write_text("---\ntype: idea\n---\n", encoding="utf-8")
    assert mcp_server.list_past_ideas() == ["idea--widget"]


def test_write_idea_report_refuses_if_note_missing(vault):
    with pytest.raises(FileNotFoundError):
        mcp_server.write_idea_report("nonexistent", "report body")


def test_write_idea_report_writes_body_and_updates_status(vault):
    (vault / "ideas").mkdir(parents=True)
    fm = {
        "id": "20260701-0900", "type": "idea", "created": "2026-07-01T09:00", "updated": "2026-07-01T09:00",
        "source": "manual", "visibility": "interactive", "freshness": "dated", "tags": [], "entities": [],
        "links": [], "status": "active", "verdict": "Conditional Go", "idea_score": 6, "fit_score": 6,
        "report_status": "none",
    }
    path = vault / "ideas" / "idea--widget.md"
    frontmatter.write_note(path, fm, "preliminary intake text")

    result = mcp_server.write_idea_report("widget", "# Deep report\nMarket looks fine.")
    assert result == "ideas/idea--widget.md"

    new_fm, body = frontmatter.read_note(path)
    assert new_fm["report_status"] == "done"
    assert "Deep report" in body


def test_fetch_url_delegates_to_normalizer_extraction(vault, monkeypatch):
    monkeypatch.setattr(mcp_server, "_extract_url", lambda url: f"extracted: {url}")
    assert mcp_server.fetch_url("https://example.com") == "extracted: https://example.com"


def test_mcp_server_exposes_tools_over_real_protocol():
    """Slower, subprocess-based: confirms the FastMCP wiring genuinely
    speaks MCP, not just that the plain functions work in isolation."""
    script = f"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="{sys.executable}", args=["-m", "app.evaluator.mcp_server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(",".join(sorted(t.name for t in tools.tools)))

asyncio.run(main())
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    tool_names = result.stdout.strip().splitlines()[-1].split(",")
    assert set(tool_names) == {
        "read_vault_note", "list_self_model", "list_past_ideas", "write_idea_report", "fetch_url",
    }

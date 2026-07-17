import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_lint_passes_on_the_real_vault():
    result = subprocess.run(
        [sys.executable, "tools/lint.py", "--path", "vault"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_lint_fails_on_a_broken_note(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "knowledge").mkdir()
    (vault / "knowledge" / "notes").mkdir()
    (vault / "knowledge" / "notes" / "note--broken.md").write_text(
        "---\nid: not-valid\ntype: bogus\ncreated: x\nupdated: x\nsource: manual\n"
        "visibility: interactive\nfreshness: dated\ntags: []\nentities: []\n"
        "links: []\nstatus: active\n---\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "tools/lint.py", "--path", str(vault)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "not-valid" in result.stdout

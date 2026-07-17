"""Closes the loop on Phase 3: the exact same steps app/bot/telegram_bot.py's
/invoice handler runs (compute -> write note -> render PDF), checked against
the real tools/lint.py so a bug in the invoice frontmatter shape can't slip
through the unit tests in test_billing.py alone."""
import shutil
import subprocess
import sys
from pathlib import Path

from app.common import frontmatter
from app.crm import billing
from app.crm.invoice_pdf import render_invoice_pdf
from tests.fakes import FakeDB
from tests.test_billing import UNIVERSAL, _event, _write_client, _write_project

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bot_invoice_flow_produces_a_lint_passing_note(tmp_path):
    vault_path = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "vault" / "_templates", vault_path / "_templates")

    _write_project(vault_path, "acme-website", client="[[client--acme]]", budget_hours=40, rate=85)
    _write_client(vault_path, "acme", country="NL")
    db = FakeDB([_event("2026-07-10T09:00:00", 10.0, "acme-website")])

    invoice_data = billing.compute_invoice(vault_path, db, "acme-website", 2026, 7)

    fm, _ = frontmatter.new_note_from_template(
        vault_path, "invoice", overrides={"visibility": "sensitive", **invoice_data}
    )
    invoice_path = vault_path / "crm" / "invoices" / f"invoice--{invoice_data['number']}.md"
    frontmatter.write_note(invoice_path, fm)

    pdf_path = vault_path / "crm" / "invoices" / f"invoice--{invoice_data['number']}.pdf"
    render_invoice_pdf(invoice_data, pdf_path)

    assert invoice_path.is_file()
    assert pdf_path.is_file()
    assert fm["visibility"] == "sensitive"

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "lint.py"), "--path", str(vault_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

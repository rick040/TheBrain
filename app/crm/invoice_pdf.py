"""Render an NL-compliant invoice PDF from a computed invoice dict
(app.crm.billing.compute_invoice) — docs/03-engineering-build-spec.md §10.

Required fields baked in: your name + address, KVK number, BTW-id, client
name + address, invoice date + number, line items, subtotal, BTW 21% (or
a reverse-charge line for EU B2B), total, payment term, IBAN. This module
only renders a file — writing the invoice note and deciding whether to
send it anywhere is the caller's job, and nothing here sends anything.
"""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from app.common.config import get_env


def _business_info() -> dict:
    return {
        "name": get_env("BUSINESS_NAME", default="(set BUSINESS_NAME in .env)"),
        "address": get_env("BUSINESS_ADDRESS", default="(set BUSINESS_ADDRESS in .env)"),
        "kvk": get_env("BUSINESS_KVK_NUMBER", default="(set BUSINESS_KVK_NUMBER in .env)"),
        "vat_id": get_env("BUSINESS_BTW_ID", default="(set BUSINESS_BTW_ID in .env)"),
        "iban": get_env("BUSINESS_IBAN", default="(set BUSINESS_IBAN in .env)"),
    }


def render_invoice_pdf(invoice: dict, output_path: Path) -> Path:
    business = _business_info()
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Invoice {invoice['number']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, business["name"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for line in business["address"].split(","):
        pdf.cell(0, 5, line.strip(), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"KVK: {business['kvk']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"BTW-id: {business['vat_id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Bill to:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, invoice.get("client_name") or "(client)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.cell(60, 5, "Invoice date:")
    pdf.cell(0, 5, invoice["issue_date"], new_x="LMARGIN", new_y="NEXT")
    pdf.cell(60, 5, "Due date:")
    pdf.cell(0, 5, invoice["due"], new_x="LMARGIN", new_y="NEXT")
    pdf.cell(60, 5, "Period:")
    pdf.cell(0, 5, invoice["period"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Line items table
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(90, 7, "Description", border="B")
    pdf.cell(30, 7, "Hours", border="B", align="R")
    pdf.cell(30, 7, "Rate", border="B", align="R")
    pdf.cell(30, 7, "Amount", border="B", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    project_desc = invoice["project"].strip('"').strip("[]")
    pdf.cell(90, 7, f"{project_desc} ({invoice['period']})")
    pdf.cell(30, 7, f"{invoice['hours']:.2f}", align="R")
    pdf.cell(30, 7, f"EUR {invoice['rate']:.2f}", align="R")
    pdf.cell(30, 7, f"EUR {invoice['subtotal']:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.cell(150, 6, "Subtotal", align="R")
    pdf.cell(30, 6, f"EUR {invoice['subtotal']:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    if invoice["reverse_charge"]:
        pdf.cell(150, 6, "BTW verlegd (EU reverse charge, 0%)", align="R")
        pdf.cell(30, 6, "EUR 0.00", align="R", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(150, 6, f"BTW ({invoice['vat_rate']}%)", align="R")
        pdf.cell(30, 6, f"EUR {invoice['vat']:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(150, 7, "Total", align="R")
    pdf.cell(30, 7, f"EUR {invoice['total']:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)

    pdf.ln(10)
    pdf.cell(0, 5, f"Payment term: 30 days. IBAN: {business['iban']}", new_x="LMARGIN", new_y="NEXT")
    if invoice["reverse_charge"]:
        pdf.multi_cell(
            0, 5,
            "VAT reverse-charged to the recipient under the EU reverse-charge "
            "mechanism for intra-Community B2B services (Article 44 EU VAT Directive).",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path

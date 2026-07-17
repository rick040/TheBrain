from app.crm.invoice_pdf import render_invoice_pdf

BASE_INVOICE = {
    "number": "2026-001",
    "client_name": "Acme BV",
    "project": "[[project--acme-website]]",
    "period": "2026-07",
    "issue_date": "2026-07-17",
    "due": "2026-08-16",
    "hours": 10.0,
    "rate": 85.0,
    "subtotal": 850.0,
    "vat_rate": 21,
    "vat": 178.5,
    "total": 1028.5,
    "reverse_charge": False,
}


def _text(pdf_path):
    from pypdf import PdfReader

    return PdfReader(str(pdf_path)).pages[0].extract_text()


def test_render_invoice_contains_key_fields(tmp_path):
    out = render_invoice_pdf(BASE_INVOICE, tmp_path / "invoice.pdf")
    assert out.is_file()
    text = _text(out)
    assert "2026-001" in text
    assert "Acme BV" in text
    assert "850.00" in text
    assert "178.50" in text
    assert "1028.50" in text
    assert "21%" in text


def test_render_invoice_reverse_charge_shows_zero_vat_and_notice(tmp_path):
    invoice = dict(BASE_INVOICE, reverse_charge=True, vat_rate=0, vat=0, total=BASE_INVOICE["subtotal"])
    out = render_invoice_pdf(invoice, tmp_path / "invoice-rc.pdf")
    text = _text(out)
    assert "BTW verlegd" in text
    assert "reverse charge" in text.lower()
    assert "0.00" in text

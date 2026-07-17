import datetime

from app.common import frontmatter
from app.crm import billing
from tests.fakes import FakeDB

UNIVERSAL = dict(
    created="2026-07-01T09:00",
    updated="2026-07-01T09:00",
    source="manual",
    visibility="interactive",
    freshness="dated",
    tags=[],
    entities=[],
    links=[],
    status="active",
)


def _write_project(vault_path, slug, *, client="[[client--acme]]", budget_hours=40, rate=85):
    fm = {
        "id": "20260701-0900",
        "type": "project",
        **UNIVERSAL,
        "client": client,
        "stage": "active",
        "deliverables": [],
        "budget_hours": budget_hours,
        "rate": rate,
    }
    frontmatter.write_note(vault_path / "crm" / "projects" / f"project--{slug}.md", fm)


def _write_client(vault_path, slug, *, country="NL", vat_id=None, name="Acme BV"):
    fm = {
        "id": "20260701-0900",
        "type": "client",
        **UNIVERSAL,
        "name": name,
        "stage": "active",
        "rate": 85,
        "contacts": [],
        "projects": [],
        "country": country,
        "vat_id": vat_id,
    }
    frontmatter.write_note(vault_path / "crm" / "clients" / f"client--{slug}.md", fm)


def _event(ts, hours, project, user_id="test-user-id"):
    return {
        "kind": "time_entry",
        "value": hours,
        "ts": ts,
        "meta": {"project": project},
        "user_id": user_id,
    }


def test_hours_logged_sums_and_filters_by_project(tmp_path):
    events = [
        _event("2026-07-01T09:00:00", 2.0, "acme-website"),
        _event("2026-07-05T09:00:00", 1.5, "acme-website"),
        _event("2026-07-05T09:00:00", 4.0, "other-project"),
    ]
    db = FakeDB(events)
    assert billing.hours_logged(db, "acme-website") == 3.5
    assert billing.hours_logged(db, "other-project") == 4.0
    assert billing.hours_logged(db, "nonexistent") == 0.0


def test_hours_logged_filters_by_year_and_month(tmp_path):
    events = [
        _event("2026-06-15T09:00:00", 3.0, "acme-website"),
        _event("2026-07-01T09:00:00", 2.0, "acme-website"),
        _event("2027-07-01T09:00:00", 9.0, "acme-website"),
    ]
    db = FakeDB(events)
    assert billing.hours_logged(db, "acme-website", year=2026, month=7) == 2.0
    assert billing.hours_logged(db, "acme-website", year=2026) == 5.0


def test_budget_status_computes_remaining(tmp_path):
    vault_path = tmp_path / "vault"
    _write_project(vault_path, "acme-website", budget_hours=40, rate=85)
    db = FakeDB([_event("2026-07-01T09:00:00", 12.5, "acme-website")])

    status = billing.budget_status(vault_path, db, "acme-website")
    assert status["logged_hours"] == 12.5
    assert status["budget_hours"] == 40
    assert status["remaining_hours"] == 27.5
    assert status["rate"] == 85


def test_next_invoice_number_is_sequential_and_persists(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    assert billing.next_invoice_number(vault_path, 2026) == "2026-001"
    assert billing.next_invoice_number(vault_path, 2026) == "2026-002"
    # a different year starts its own sequence
    assert billing.next_invoice_number(vault_path, 2027) == "2027-001"
    assert billing.next_invoice_number(vault_path, 2026) == "2026-003"


def test_compute_invoice_math_no_reverse_charge(tmp_path):
    vault_path = tmp_path / "vault"
    _write_project(vault_path, "acme-website", client="[[client--acme]]", budget_hours=40, rate=85)
    _write_client(vault_path, "acme", country="NL")
    db = FakeDB([_event("2026-07-10T09:00:00", 10.0, "acme-website")])

    result = billing.compute_invoice(
        vault_path, db, "acme-website", 2026, 7, today=datetime.date(2026, 7, 17)
    )
    assert result["hours"] == 10.0
    assert result["subtotal"] == 850.0
    assert result["reverse_charge"] is False
    assert result["vat_rate"] == 21
    assert result["vat"] == 178.5
    assert result["total"] == 1028.5
    assert result["due"] == "2026-08-16"
    assert result["number"] == "2026-001"


def test_compute_invoice_reverse_charge_when_eu_client_has_vat_id(tmp_path):
    vault_path = tmp_path / "vault"
    _write_project(vault_path, "eu-project", client="[[client--eurocorp]]", budget_hours=20, rate=100)
    _write_client(vault_path, "eurocorp", country="DE", vat_id="DE123456789", name="EuroCorp GmbH")
    db = FakeDB([_event("2026-07-10T09:00:00", 5.0, "eu-project")])

    result = billing.compute_invoice(vault_path, db, "eu-project", 2026, 7)
    assert result["reverse_charge"] is True
    assert result["vat_rate"] == 0
    assert result["vat"] == 0
    assert result["total"] == result["subtotal"] == 500.0
    assert result["client_name"] == "EuroCorp GmbH"


def test_compute_invoice_missing_project_raises(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    db = FakeDB([])
    try:
        billing.compute_invoice(vault_path, db, "does-not-exist", 2026, 7)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass

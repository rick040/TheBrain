"""Billing rollup + NL-compliant invoice numbering/computation
(docs/03-engineering-build-spec.md §6/§10 — Phase 3).

Time is tracked per PROJECT (not client), because budget_hours/rate live
on the project note. Invoicing is period-based (a calendar month) against
Postgres time_entry events — events are never mutated/marked-invoiced,
staying append-only per the spine's "everything is an event" principle
(docs/01-build-plan.md Part A). Numbering is a persistent counter file,
not a scan of existing invoice notes, so NL's "sequential, no gaps" rule
holds even if an invoice note is later edited or deleted.
"""
from __future__ import annotations

import datetime
from pathlib import Path

import yaml

from app.common import frontmatter

COUNTER_PATH_NAME = "_system/invoice_counters.yaml"
DEFAULT_PAYMENT_TERM_DAYS = 30


def _slug_from_wikilink(link: str | None) -> str | None:
    if not link:
        return None
    name = link.strip().strip("[]").strip('"')
    return name.split("--", 1)[1] if "--" in name else name


def load_project(vault_path: Path, project_slug: str) -> dict:
    path = vault_path / "crm" / "projects" / f"project--{project_slug}.md"
    if not path.is_file():
        raise FileNotFoundError(f"no project note at {path}")
    fm, _ = frontmatter.read_note(path)
    return fm


def load_client_for_project(vault_path: Path, project: dict) -> dict | None:
    client_slug = _slug_from_wikilink(project.get("client"))
    if not client_slug:
        return None
    path = vault_path / "crm" / "clients" / f"client--{client_slug}.md"
    if not path.is_file():
        return None
    fm, _ = frontmatter.read_note(path)
    return fm


def hours_logged(db, project_slug: str, *, year: int | None = None, month: int | None = None) -> float:
    """Sum time_entry hours for a project, optionally restricted to one
    calendar month. Reads straight from Postgres (P5: two stores — this
    never gets re-derived back into the vault note)."""
    rows = (
        db.client.table("events")
        .select("value, ts")
        .eq("kind", "time_entry")
        .eq("user_id", db.user_id)
        .contains("meta", {"project": project_slug})
        .execute()
        .data
    )
    total = 0.0
    for row in rows:
        if year is not None:
            ts = datetime.datetime.fromisoformat(row["ts"])
            if ts.year != year or (month is not None and ts.month != month):
                continue
        total += float(row["value"] or 0)
    return total


def budget_status(vault_path: Path, db, project_slug: str) -> dict:
    project = load_project(vault_path, project_slug)
    logged = hours_logged(db, project_slug)
    budget = float(project.get("budget_hours") or 0)
    return {
        "project": project_slug,
        "logged_hours": logged,
        "budget_hours": budget,
        "remaining_hours": budget - logged,
        "rate": project.get("rate"),
    }


def _load_counters(vault_path: Path) -> dict:
    path = vault_path / COUNTER_PATH_NAME
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _save_counters(vault_path: Path, counters: dict) -> None:
    path = vault_path / COUNTER_PATH_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(counters, sort_keys=True), encoding="utf-8")


def next_invoice_number(vault_path: Path, year: int) -> str:
    counters = _load_counters(vault_path)
    counters[year] = counters.get(year, 0) + 1
    _save_counters(vault_path, counters)
    return f"{year}-{counters[year]:03d}"


def compute_invoice(
    vault_path: Path,
    db,
    project_slug: str,
    year: int,
    month: int,
    *,
    reverse_charge: bool | None = None,
    today: datetime.date | None = None,
) -> dict:
    """Draft invoice fields for one project/month. Never writes anything
    itself — the caller writes the note + renders the PDF and shows it
    for approval (§10 DoD: 'always presented to the user for approval;
    never auto-sent')."""
    project = load_project(vault_path, project_slug)
    client = load_client_for_project(vault_path, project)

    if reverse_charge is None:
        country = (client or {}).get("country", "NL")
        vat_id = (client or {}).get("vat_id")
        reverse_charge = bool(vat_id) and country != "NL"

    hours = hours_logged(db, project_slug, year=year, month=month)
    rate = float(project.get("rate") or 0)
    subtotal = round(hours * rate, 2)
    vat_rate = 0 if reverse_charge else 21
    vat = round(subtotal * vat_rate / 100, 2)
    total = round(subtotal + vat, 2)

    number = next_invoice_number(vault_path, year)
    issue_date = today or datetime.date.today()
    due = (issue_date + datetime.timedelta(days=DEFAULT_PAYMENT_TERM_DAYS)).isoformat()

    return {
        "number": number,
        "client": project.get("client"),
        "client_name": (client or {}).get("name"),
        "project": f"[[project--{project_slug}]]",
        "period": f"{year}-{month:02d}",
        "hours": hours,
        "rate": rate,
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat": vat,
        "total": total,
        "paid": False,
        "issue_date": issue_date.isoformat(),
        "due": due,
        "reverse_charge": reverse_charge,
    }

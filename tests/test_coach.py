import datetime

from app.brain import coach
from app.common import frontmatter
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


def _write_project(vault_path, slug, *, deliverables, status="active"):
    fm = {
        "id": "20260701-0900", "type": "project", **UNIVERSAL, "status": status,
        "client": "[[client--x]]", "stage": "active", "deliverables": deliverables,
        "budget_hours": 40, "rate": 85,
    }
    frontmatter.write_note(vault_path / "crm" / "projects" / f"project--{slug}.md", fm)


def _write_habit(vault_path, slug, *, name, cadence, streak=0, tags=None):
    fm = {
        "id": "20260701-0900", "type": "habit", **{**UNIVERSAL, "tags": tags or []},
        "name": name, "cadence": cadence, "streak": streak, "linked_kr": None, "log": "postgres",
    }
    frontmatter.write_note(vault_path / "goals" / "habits" / f"habit--{slug}.md", fm)


def _write_gap(vault_path, slug, *, size, tension, hold=False):
    fm = {
        "id": "20260701-0900", "type": "gap", **{**UNIVERSAL, "visibility": "sensitive"},
        "current": [], "desired": None, "size": size, "tension": tension, "proposal": None, "hold": hold,
    }
    frontmatter.write_note(vault_path / "self" / "gap" / f"gap--{slug}.md", fm)


def _write_client(vault_path, slug, *, stage, updated):
    fm = {
        "id": "20260701-0900", "type": "client", **{**UNIVERSAL, "updated": updated},
        "name": slug.title(), "stage": stage, "rate": 85, "contacts": [], "projects": [],
        "country": "NL", "vat_id": None,
    }
    frontmatter.write_note(vault_path / "crm" / "clients" / f"client--{slug}.md", fm)


def test_compose_morning_brief_on_empty_vault(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    brief = coach.compose_morning_brief(vault_path)
    assert "No open deliverables tracked." in brief
    assert "becoming, not today's score" in brief


def test_compose_morning_brief_lists_deliverables_sorted_by_due_date(tmp_path):
    vault_path = tmp_path / "vault"
    _write_project(
        vault_path, "acme",
        deliverables=[
            {"task": "Later task", "due": "2026-09-01", "done": False},
            {"task": "Sooner task", "due": "2026-07-20", "done": False},
            {"task": "Done already", "due": "2026-07-01", "done": True},
        ],
    )
    brief = coach.compose_morning_brief(vault_path)
    sooner_idx = brief.index("Sooner task")
    later_idx = brief.index("Later task")
    assert sooner_idx < later_idx
    assert "Done already" not in brief


def test_compose_morning_brief_flags_zero_streak_habits(tmp_path):
    vault_path = tmp_path / "vault"
    _write_habit(vault_path, "reading", name="Reading", cadence="daily", streak=0)
    _write_habit(vault_path, "gym", name="Gym", cadence="4x/week", streak=5)
    brief = coach.compose_morning_brief(vault_path)
    assert "Reading" in brief
    assert "Gym" not in brief


def test_compose_morning_brief_ignores_proposed_habits(tmp_path):
    vault_path = tmp_path / "vault"
    _write_habit(vault_path, "draft", name="Draft habit", cadence="daily", streak=0, tags=["proposed"])
    brief = coach.compose_morning_brief(vault_path)
    assert "Draft habit" not in brief


def test_compose_morning_brief_surfaces_largest_non_held_gap(tmp_path):
    vault_path = tmp_path / "vault"
    _write_gap(vault_path, "subtle-one", size="subtle", tension="minor thing")
    _write_gap(vault_path, "large-one", size="large", tension="the big one")
    _write_gap(vault_path, "held-one", size="large", tension="accepted tension", hold=True)
    brief = coach.compose_morning_brief(vault_path)
    assert "the big one" in brief
    assert "accepted tension" not in brief


def test_is_quiet_hours_simple_window():
    config = {"coach": {"quiet_windows": [["22:00", "23:59"]]}}
    assert coach.is_quiet_hours(config, datetime.datetime(2026, 7, 17, 22, 30))
    assert not coach.is_quiet_hours(config, datetime.datetime(2026, 7, 17, 10, 0))


def test_is_quiet_hours_wraps_midnight():
    config = {"coach": {"quiet_windows": [["22:00", "07:00"]]}}
    assert coach.is_quiet_hours(config, datetime.datetime(2026, 7, 17, 23, 30))
    assert coach.is_quiet_hours(config, datetime.datetime(2026, 7, 17, 5, 0))
    assert not coach.is_quiet_hours(config, datetime.datetime(2026, 7, 17, 12, 0))


def test_stale_leads_fires_past_threshold(tmp_path):
    vault_path = tmp_path / "vault"
    _write_client(vault_path, "cold", stage="proposal", updated="2026-06-01T09:00")
    _write_client(vault_path, "fresh", stage="proposal", updated="2026-07-15T09:00")
    config = {"thresholds": {"stale_lead_days": 7}}
    nudges = coach._stale_leads(vault_path, config, today=datetime.date(2026, 7, 17))
    assert any("Cold" in n for n in nudges)
    assert not any("Fresh" in n for n in nudges)


def test_unbilled_hours_fires_past_threshold(tmp_path):
    vault_path = tmp_path / "vault"
    _write_project(vault_path, "acme-website", deliverables=[])
    events = [
        {"kind": "time_entry", "value": 12.0, "ts": "2026-07-05T09:00:00",
         "meta": {"project": "acme-website"}, "user_id": "test-user-id"},
    ]
    db = FakeDB(events)
    config = {"thresholds": {"unbilled_hours_alert": 10}}
    nudges = coach._unbilled_hours(vault_path, db, config, year=2026, month=7)
    assert any("acme-website" in n for n in nudges)


def test_missed_habits_fires_when_under_half_expected(tmp_path):
    vault_path = tmp_path / "vault"
    _write_habit(vault_path, "reading", name="Reading", cadence="daily")
    events = [
        {"kind": "habit_tick", "ts": "2026-07-15T09:00:00", "meta": {"habit": "Reading"}, "user_id": "test-user-id"},
    ]
    db = FakeDB(events)
    nudges = coach._missed_habits(vault_path, db, today=datetime.date(2026, 7, 17))
    assert any("Reading" in n for n in nudges)


def test_collect_nudges_respects_quiet_hours(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    _write_client(vault_path, "cold", stage="proposal", updated="2026-01-01T09:00")
    config = {
        "thresholds": {"stale_lead_days": 7, "unbilled_hours_alert": 10},
        "coach": {"escalation": True, "quiet_windows": [["00:00", "23:59"]]},
    }
    db = FakeDB([])
    assert coach.collect_nudges(vault_path, db, config) == []


def test_collect_nudges_respects_escalation_off(tmp_path):
    vault_path = tmp_path / "vault"
    _write_client(vault_path, "cold", stage="proposal", updated="2026-01-01T09:00")
    config = {"thresholds": {"stale_lead_days": 7}, "coach": {"escalation": False, "quiet_windows": []}}
    db = FakeDB([])
    assert coach.collect_nudges(vault_path, db, config) == []


def test_send_telegram_message_posts_to_the_right_url(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    coach.send_telegram_message("hello")

    assert len(calls) == 1
    url, payload, _ = calls[0]
    assert url == "https://api.telegram.org/bottest-token/sendMessage"
    assert payload == {"chat_id": "12345", "text": "hello"}

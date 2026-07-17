import datetime
import json
import shutil
from pathlib import Path

import pytest

from app.brain import reviews
from app.common import frontmatter
from tests.fakes import FakeDB
from tests.test_billing import UNIVERSAL as PROJECT_UNIVERSAL
from tests.test_billing import _write_project

REPO_ROOT = Path(__file__).resolve().parents[1]

FAKE_NARRATIVE = {
    "wins": ["Shipped the homepage"],
    "misses": ["Reading habit slipped"],
    "adjustments": ["Block mornings for deep work"],
}


@pytest.fixture
def vault_path(tmp_path):
    vp = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "vault" / "_templates", vp / "_templates")
    return vp


def _time_event(ts, hours, project):
    return {"kind": "time_entry", "value": hours, "ts": ts, "meta": {"project": project}, "user_id": "test-user-id"}


def _habit_event(ts, habit):
    return {"kind": "habit_tick", "ts": ts, "meta": {"habit": habit}, "user_id": "test-user-id"}


def test_collect_period_stats_sums_hours_and_ticks_within_range(vault_path):
    _write_project(vault_path, "acme-website", budget_hours=40, rate=85)
    events = [
        _time_event("2026-07-10T09:00:00", 3.0, "acme-website"),
        _time_event("2026-06-01T09:00:00", 5.0, "acme-website"),  # outside range
        _habit_event("2026-07-11T09:00:00", "Reading"),
    ]
    db = FakeDB(events)
    stats = reviews.collect_period_stats(vault_path, db, datetime.date(2026, 7, 10), datetime.date(2026, 7, 17))
    assert stats["project_hours"] == {"acme-website": 3.0}
    assert stats["total_hours"] == 3.0
    assert stats["habit_ticks"] == {"Reading": 1}


def test_compose_review_calls_llm_and_returns_stats(vault_path, monkeypatch):
    monkeypatch.setattr(reviews, "llm", lambda *a, **k: json.dumps(FAKE_NARRATIVE))
    db = FakeDB([_time_event("2026-07-10T09:00:00", 2.0, "acme")])
    review = reviews.compose_review(vault_path, db, datetime.date(2026, 7, 10), datetime.date(2026, 7, 17))
    assert review["wins"] == FAKE_NARRATIVE["wins"]
    assert review["misses"] == FAKE_NARRATIVE["misses"]
    assert "stats" in review


def test_write_review_produces_a_lint_passing_note(vault_path, monkeypatch):
    monkeypatch.setattr(reviews, "llm", lambda *a, **k: json.dumps(FAKE_NARRATIVE))
    db = FakeDB([])
    path = reviews.write_review(vault_path, db, datetime.date(2026, 7, 10), datetime.date(2026, 7, 17))
    assert path.is_file()
    fm, body = frontmatter.read_note(path)
    assert fm["wins"] == FAKE_NARRATIVE["wins"]
    assert "Hours logged" in body

    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "lint.py"), "--path", str(vault_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

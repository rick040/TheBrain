import shutil
from pathlib import Path

import pytest

from app.brain import snapshot
from app.common import frontmatter
from tests.fakes import FakeDB
from tests.test_billing import _write_project

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def vault_path(tmp_path):
    vp = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "vault" / "_templates", vp / "_templates")
    return vp


def _lift_event(ts, exercise, load):
    return {"kind": "lift", "ts": ts, "meta": {"exercise": exercise, "scheme": "5x5", "load": load}, "user_id": "test-user-id"}


def test_write_billing_snapshot_lists_active_projects(vault_path):
    _write_project(vault_path, "acme-website", budget_hours=40, rate=85)
    db = FakeDB([{"kind": "time_entry", "value": 10.0, "ts": "2026-07-10T09:00:00",
                  "meta": {"project": "acme-website"}, "user_id": "test-user-id"}])
    path = snapshot.write_billing_snapshot(vault_path, db)
    assert path.is_file()
    _fm, body = frontmatter.read_note(path)
    assert "acme-website" in body
    assert "10.0h" in body
    assert "40.0h" in body


def test_write_billing_snapshot_is_overwritten_not_duplicated(vault_path):
    _write_project(vault_path, "acme-website", budget_hours=40, rate=85)
    db = FakeDB([])
    first = snapshot.write_billing_snapshot(vault_path, db)
    second = snapshot.write_billing_snapshot(vault_path, db)
    assert first == second
    assert len(list((vault_path / "_dashboards").glob("billing-snapshot*"))) == 1


def test_write_health_snapshot_lists_exercises_with_history(vault_path):
    db = FakeDB([_lift_event("2026-07-10T09:00:00", "squat", "80kg")])
    path = snapshot.write_health_snapshot(vault_path, db)
    _fm, body = frontmatter.read_note(path)
    assert "squat" in body
    assert "82.5kg" in body


def test_write_health_snapshot_empty_when_no_lift_history(vault_path):
    db = FakeDB([])
    path = snapshot.write_health_snapshot(vault_path, db)
    _fm, body = frontmatter.read_note(path)
    assert "Suggested next" in body  # header still present, just no rows

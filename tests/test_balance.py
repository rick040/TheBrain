import datetime

from app.brain import balance
from tests.fakes import FakeDB


def _event(kind, ts, user_id="test-user-id"):
    return {"kind": kind, "ts": ts, "value": None, "meta": {}, "user_id": user_id}


def test_area_activity_counts_buckets_by_kind():
    events = [
        _event("time_entry", "2026-07-10T09:00:00"),
        _event("time_entry", "2026-07-11T09:00:00"),
        _event("habit_tick", "2026-07-12T09:00:00"),
    ]
    db = FakeDB(events)
    counts = balance.area_activity_counts(db, days=30, today=datetime.date(2026, 7, 17))
    assert counts == {"work": 2, "habits": 1}


def test_area_activity_counts_respects_window(tmp_path=None):
    events = [
        _event("time_entry", "2026-01-01T09:00:00"),  # outside 30-day window
        _event("time_entry", "2026-07-15T09:00:00"),
    ]
    db = FakeDB(events)
    counts = balance.area_activity_counts(db, days=30, today=datetime.date(2026, 7, 17))
    assert counts == {"work": 1}


def test_flag_imbalance_fires_when_one_area_dominates_and_others_silent():
    counts = {"work": 9, "habits": 1}
    warning = balance.flag_imbalance(counts, dominant_share=0.7)
    assert warning is not None
    assert "work" in warning
    assert "health" in warning  # a known area with zero activity


def test_flag_imbalance_silent_when_balanced():
    counts = {"work": 5, "health": 4, "habits": 3, "finance": 2}
    assert balance.flag_imbalance(counts, dominant_share=0.7) is None


def test_flag_imbalance_silent_when_no_data():
    assert balance.flag_imbalance({}) is None

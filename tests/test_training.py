from app.health import training
from tests.fakes import FakeDB


def test_parse_load_variants():
    assert training.parse_load("80kg") == 80.0
    assert training.parse_load("82.5kg") == 82.5
    assert training.parse_load("80") == 80.0
    assert training.parse_load("") is None
    assert training.parse_load(None) is None


def test_parse_scheme_variants():
    assert training.parse_scheme("5x5") == (5, 5)
    assert training.parse_scheme("3 x 10") == (3, 10)
    assert training.parse_scheme("garbage") is None


def _lift_event(ts, exercise, load, scheme="5x5", user_id="test-user-id"):
    return {"kind": "lift", "ts": ts, "meta": {"exercise": exercise, "scheme": scheme, "load": load}, "user_id": user_id}


def _sleep_event(ts, hours, user_id="test-user-id"):
    return {"kind": "sleep", "ts": ts, "value": hours, "meta": {}, "user_id": user_id}


def test_last_session_picks_most_recent():
    events = [
        _lift_event("2026-07-01T09:00:00", "squat", "80kg"),
        _lift_event("2026-07-10T09:00:00", "squat", "82.5kg"),
        _lift_event("2026-07-05T09:00:00", "bench", "60kg"),
    ]
    db = FakeDB(events)
    last = training.last_session(db, "squat")
    assert last["meta"]["load"] == "82.5kg"


def test_last_session_none_when_no_history():
    db = FakeDB([])
    assert training.last_session(db, "squat") is None


def test_should_deload_false_when_no_sleep_data():
    db = FakeDB([])
    assert training.should_deload(db) is False


def test_should_deload_true_when_average_sleep_low(monkeypatch):
    import datetime

    now = datetime.datetime(2026, 7, 17, 9, 0)

    class FrozenDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(training, "datetime", type("dt", (), {"datetime": FrozenDatetime, "timedelta": datetime.timedelta}))
    events = [
        _sleep_event("2026-07-15T07:00:00", 5.0),
        _sleep_event("2026-07-16T07:00:00", 5.5),
    ]
    db = FakeDB(events)
    assert training.should_deload(db) is True


def test_suggest_next_load_no_history():
    db = FakeDB([])
    result = training.suggest_next_load(db, "squat")
    assert result["suggestion"] is None
    assert "no prior session" in result["reason"]


def test_suggest_next_load_progresses_without_sleep_data():
    events = [_lift_event("2026-07-10T09:00:00", "squat", "80kg")]
    db = FakeDB(events)
    result = training.suggest_next_load(db, "squat", increment_kg=2.5)
    assert result["suggestion"] == 82.5
    assert "progressive overload" in result["reason"]


def test_suggest_next_load_deloads_on_poor_sleep(monkeypatch):
    import datetime

    now = datetime.datetime(2026, 7, 17, 9, 0)

    class FrozenDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(training, "datetime", type("dt", (), {"datetime": FrozenDatetime, "timedelta": datetime.timedelta}))
    events = [
        _lift_event("2026-07-10T09:00:00", "squat", "80kg"),
        _sleep_event("2026-07-15T07:00:00", 5.0),
        _sleep_event("2026-07-16T07:00:00", 5.0),
    ]
    db = FakeDB(events)
    result = training.suggest_next_load(db, "squat")
    assert result["suggestion"] == 72.0
    assert "deload" in result["reason"]

"""Training engine (docs/03-engineering-build-spec.md Phase 7):
progressive overload on top of the `/lift` events already logged (Phase
1), plus a recovery-based deload check using `sleep` events from the
health-ingest Edge Function (supabase/functions/health-ingest/).

Honest scope note: without health-ingest actually receiving real data
(it needs INGEST_SECRET/THEBRAIN_USER_ID secrets set by hand — see
docs/05-manual-setup-checklist.md, and something on the phone POSTing to
it — see Health Connect export setup, same doc), there's no sleep signal
yet. This degrades gracefully: no data -> no deload guess, never a
fabricated one.
"""
from __future__ import annotations

import datetime
import re
import statistics

LOAD_PATTERN = re.compile(r"[\d.]+")
SCHEME_PATTERN = re.compile(r"(\d+)\s*x\s*(\d+)", re.IGNORECASE)

DEFAULT_INCREMENT_KG = 2.5
POOR_SLEEP_THRESHOLD_HOURS = 6.0
DELOAD_FACTOR = 0.9


def parse_load(load_str: str | None) -> float | None:
    match = LOAD_PATTERN.search(load_str or "")
    return float(match.group()) if match else None


def parse_scheme(scheme_str: str | None) -> tuple[int, int] | None:
    match = SCHEME_PATTERN.search(scheme_str or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def last_session(db, exercise: str) -> dict | None:
    rows = (
        db.client.table("events")
        .select("ts, meta")
        .eq("kind", "lift")
        .eq("user_id", db.user_id)
        .contains("meta", {"exercise": exercise})
        .execute()
        .data
    )
    if not rows:
        return None
    return max(rows, key=lambda r: r["ts"])


def recent_sleep_hours(db, *, days: int = 7) -> list[float]:
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    rows = (
        db.client.table("events")
        .select("ts, value")
        .eq("kind", "sleep")
        .eq("user_id", db.user_id)
        .gte("ts", cutoff)
        .execute()
        .data
    )
    return [float(r["value"]) for r in rows if r.get("value") is not None]


def should_deload(db, *, days: int = 7, threshold_hours: float = POOR_SLEEP_THRESHOLD_HOURS) -> bool:
    hours = recent_sleep_hours(db, days=days)
    if not hours:
        return False  # no signal -> don't guess
    return statistics.mean(hours) < threshold_hours


def suggest_next_load(db, exercise: str, *, increment_kg: float = DEFAULT_INCREMENT_KG) -> dict:
    """DoD (docs/03-engineering-build-spec.md Phase 7): logging a workout
    progresses the plan; deload triggers on a poor-sleep week WITH an
    explanation, never silently."""
    last = last_session(db, exercise)
    if last is None:
        return {"exercise": exercise, "suggestion": None, "reason": "no prior session logged for this exercise"}

    last_load = parse_load(last["meta"].get("load"))
    if last_load is None:
        return {
            "exercise": exercise, "suggestion": None,
            "reason": f"couldn't parse a load from '{last['meta'].get('load')}'",
        }

    if should_deload(db):
        return {
            "exercise": exercise,
            "suggestion": round(last_load * DELOAD_FACTOR, 1),
            "reason": f"deload — average sleep this week was under {POOR_SLEEP_THRESHOLD_HOURS}h",
        }

    return {
        "exercise": exercise,
        "suggestion": round(last_load + increment_kg, 1),
        "reason": f"progressive overload — +{increment_kg}kg from last session ({last_load}kg)",
    }

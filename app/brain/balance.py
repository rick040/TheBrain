"""Life-areas balance check (docs/01-build-plan.md Part E): keeps the
gap engine from optimizing one axis (work) while another (health,
relationships) quietly collapses.

Honest scope note: this is a heuristic proxy — it buckets Postgres event
`kind`s into coarse areas and flags when one dominates while others show
nothing. A real life-domain model (tagging every event/note with which
life area it belongs to) wants Phase 2's self-model and richer tagging
than exists yet; this is the useful thing buildable without that.
"""
from __future__ import annotations

import datetime

AREA_BY_KIND = {
    "time_entry": "work",
    "lift": "health",
    "steps": "health",
    "sleep": "health",
    "hr": "health",
    "habit_tick": "habits",
    "txn": "finance",
}
ALL_AREAS = sorted(set(AREA_BY_KIND.values()))


def area_activity_counts(db, *, days: int = 30, today: datetime.date | None = None) -> dict[str, int]:
    today = today or datetime.date.today()
    cutoff = (today - datetime.timedelta(days=days)).isoformat()
    rows = (
        db.client.table("events").select("kind, ts").eq("user_id", db.user_id).gte("ts", cutoff).execute().data
    )
    counts: dict[str, int] = {}
    for row in rows:
        area = AREA_BY_KIND.get(row["kind"], "other")
        counts[area] = counts.get(area, 0) + 1
    return counts


def flag_imbalance(counts: dict[str, int], *, dominant_share: float = 0.7) -> str | None:
    total = sum(counts.values())
    if total == 0:
        return None
    dominant_area, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    share = dominant_count / total
    if share < dominant_share:
        return None
    quiet_areas = [a for a in ALL_AREAS if a not in counts and a != dominant_area]
    if not quiet_areas:
        return None
    return (
        f"{dominant_area} is {dominant_count}/{total} ({share:.0%}) of logged activity "
        f"recently — {', '.join(quiet_areas)} show nothing. Worth a look?"
    )

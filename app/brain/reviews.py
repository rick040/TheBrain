"""Weekly/quarterly review ritual (docs/01-build-plan.md Part E): pulls
together what actually happened — hours logged, habits ticked, open
deliverables — into a DRAFT you edit, not a finished verdict handed to
you. Honest scope note: the schema doesn't record a "completed_on" date
for a deliverable (only `done: true/false`), so "open deliverables" below
is a current snapshot, not "completed this period" — that's an accurate
limitation, not a shortcut hidden from you.
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from app.common import frontmatter
from app.llm import llm

REVIEW_NARRATIVE_PROMPT = """You are helping someone reflect on their
week, from raw activity data — not judging, just reflecting back what
the data shows so they can add their own read of it.

Hours logged this period, by project: {project_hours}
Habit ticks this period: {habit_ticks}
Open deliverables right now (a snapshot, not period-specific): {open_deliverables}

Respond with ONLY a JSON object (no markdown fences):
{{
  "wins": ["1-3 honest observations worth calling a win"],
  "misses": ["0-3 honest observations worth noting, framed as information not failure"],
  "adjustments": ["0-3 concrete, small suggestions for next period"]
}}
"""


def _iter_notes(vault_path: Path, subfolder: str, note_type: str | None = None):
    folder = vault_path / subfolder
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob("*.md")):
        fm, _ = frontmatter.read_note(path)
        if note_type and fm.get("type") != note_type:
            continue
        yield path, fm


def _hours_in_range(db, project_slug: str, start: datetime.date, end: datetime.date) -> float:
    rows = (
        db.client.table("events").select("value, ts").eq("kind", "time_entry").eq("user_id", db.user_id)
        .contains("meta", {"project": project_slug}).execute().data
    )
    total = 0.0
    for row in rows:
        ts_date = datetime.datetime.fromisoformat(row["ts"]).date()
        if start <= ts_date <= end:
            total += float(row["value"] or 0)
    return total


def _habit_ticks_in_range(db, start: datetime.date, end: datetime.date) -> dict[str, int]:
    rows = (
        db.client.table("events").select("ts, meta").eq("kind", "habit_tick").eq("user_id", db.user_id).execute().data
    )
    counts: dict[str, int] = {}
    for row in rows:
        ts_date = datetime.datetime.fromisoformat(row["ts"]).date()
        if start <= ts_date <= end:
            habit = row.get("meta", {}).get("habit", "unknown")
            counts[habit] = counts.get(habit, 0) + 1
    return counts


def collect_period_stats(vault_path: Path, db, start: datetime.date, end: datetime.date) -> dict:
    project_hours = {}
    for path, fm in _iter_notes(vault_path, "crm/projects", "project"):
        if fm.get("status") != "active":
            continue
        slug = path.stem.split("--", 1)[1] if "--" in path.stem else path.stem
        hours = _hours_in_range(db, slug, start, end)
        if hours:
            project_hours[slug] = hours

    open_deliverables = sum(
        1
        for _path, fm in _iter_notes(vault_path, "crm/projects", "project")
        for d in (fm.get("deliverables") or [])
        if not d.get("done")
    )

    return {
        "project_hours": project_hours,
        "total_hours": sum(project_hours.values()),
        "habit_ticks": _habit_ticks_in_range(db, start, end),
        "open_deliverables": open_deliverables,
    }


def _parse_json_response(response: str) -> dict:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        cleaned = re.sub(r"^```(json)?\n|\n```$", "", response.strip())
        return json.loads(cleaned)


def compose_review(vault_path: Path, db, start: datetime.date, end: datetime.date) -> dict:
    stats = collect_period_stats(vault_path, db, start, end)
    response = llm(
        REVIEW_NARRATIVE_PROMPT.format(
            project_hours=stats["project_hours"] or "(none logged)",
            habit_ticks=stats["habit_ticks"] or "(none ticked)",
            open_deliverables=stats["open_deliverables"],
        ),
        tier="default",
        max_tokens=400,
    )
    narrative = _parse_json_response(response)
    return {
        "period": f"{start.isoformat()}..{end.isoformat()}",
        "wins": narrative.get("wins", []),
        "misses": narrative.get("misses", []),
        "adjustments": narrative.get("adjustments", []),
        "stats": stats,
    }


def write_review(vault_path: Path, db, start: datetime.date, end: datetime.date) -> Path:
    review = compose_review(vault_path, db, start, end)
    fm, _ = frontmatter.new_note_from_template(
        vault_path,
        "review",
        overrides={
            "period": review["period"],
            "wins": review["wins"],
            "misses": review["misses"],
            "adjustments": review["adjustments"],
        },
    )
    body = (
        f"Hours logged: {review['stats']['total_hours']:.1f} across "
        f"{len(review['stats']['project_hours'])} project(s). "
        f"Open deliverables (snapshot): {review['stats']['open_deliverables']}."
    )
    path = vault_path / "self" / "reviews" / f"review--{start.isoformat()}.md"
    frontmatter.write_note(path, fm, body)
    return path

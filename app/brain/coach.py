"""Daily coach (docs/03-engineering-build-spec.md §8.6): a morning brief +
threshold-triggered live nudges over Telegram, with a hard self-compassion
guardrail — an aggressive coach plus a gap engine is the single most
common way systems like this get abandoned (docs/01-build-plan.md Part B6).

Honest scope note: with Phase 2 parked there's no self/current
energy-mood profile yet, so "time it to your energy" and `quiet_windows`
fall back to whatever you set by hand in vault/_system/config.yaml until
that model exists for real — this is a graceful degradation, not a bug.

Run as a cron/systemd job (see systemd/README.md), not inside the
long-running bot process:
    python3 -m app.brain.coach --morning-brief   # send now
    python3 -m app.brain.coach --nudges          # check thresholds, send any that fire
    python3 -m app.brain.coach --morning-brief --dry-run   # print instead of sending
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

from app.common import frontmatter
from app.common.config import get_env, load_vault_config


def _iter_notes(vault_path: Path, subfolder: str, note_type: str | None = None):
    folder = vault_path / subfolder
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob("*.md")):
        fm, _ = frontmatter.read_note(path)
        if note_type and fm.get("type") != note_type:
            continue
        yield path, fm


def _frame(message: str) -> str:
    """The self-compassion guardrail isn't a nicety — it's enforced here,
    not left to prompt-writing. See Part B6: framed as becoming, not
    failing; every brief ends this way, no exceptions."""
    return f"{message}\n\nOne thing at a time — this is about becoming, not today's score."


# ---------- Morning brief ----------

def _open_deliverables(vault_path: Path) -> list[dict]:
    items = []
    for path, fm in _iter_notes(vault_path, "crm/projects", "project"):
        if fm.get("status") != "active":
            continue
        for d in fm.get("deliverables") or []:
            if d.get("done"):
                continue
            due = d.get("due")
            due_date = datetime.date.fromisoformat(due) if due else None
            items.append({"project": path.stem, "task": d.get("task"), "due": due_date})
    items.sort(key=lambda i: (i["due"] is None, i["due"] or datetime.date.max))
    return items


def _habit_streaks_at_risk(vault_path: Path) -> list[str]:
    """Phase 1/4 don't (yet) write live streak counts from Postgres back
    into the habit note automatically — this reads whatever's last saved,
    which is honest about what it can see without that wiring."""
    at_risk = []
    for path, fm in _iter_notes(vault_path, "goals/habits", "habit"):
        if fm.get("status") != "active" or "proposed" in (fm.get("tags") or []):
            continue
        if not (fm.get("streak") or 0):
            at_risk.append(fm.get("name", path.stem))
    return at_risk


def _top_gap(vault_path: Path) -> dict | None:
    size_rank = {"large": 3, "moderate": 2, "subtle": 1, None: 0}
    best = None
    for _path, fm in _iter_notes(vault_path, "self/gap", "gap"):
        if fm.get("hold") or fm.get("status") != "active":
            continue
        if best is None or size_rank.get(fm.get("size")) > size_rank.get(best.get("size")):
            best = fm
    return best


def compose_morning_brief(vault_path: Path) -> str:
    today = datetime.date.today()
    deliverables = _open_deliverables(vault_path)
    at_risk = _habit_streaks_at_risk(vault_path)
    gap = _top_gap(vault_path)

    lines = [f"Morning brief — {today.isoformat()}", ""]
    if deliverables:
        lines.append("Open deliverables:")
        for item in deliverables[:5]:
            due_str = item["due"].isoformat() if item["due"] else "no due date"
            lines.append(f"  - {item['task']} ({item['project']}, due {due_str})")
    else:
        lines.append("No open deliverables tracked.")

    if at_risk:
        lines.append("")
        lines.append(f"Habits with no streak going yet: {', '.join(at_risk)}.")

    if gap:
        lines.append("")
        lines.append(f"Today's gap to keep in view: {gap.get('tension')}")

    return _frame("\n".join(lines))


# ---------- Live nudges (threshold triggers) ----------

def _stale_leads(vault_path: Path, config: dict, today: datetime.date | None = None) -> list[str]:
    today = today or datetime.date.today()
    stale_days = config.get("thresholds", {}).get("stale_lead_days", 7)
    nudges = []
    for path, fm in _iter_notes(vault_path, "crm/clients", "client"):
        if fm.get("stage") not in ("lead", "proposal"):
            continue
        updated = fm.get("updated")
        if not updated:
            continue
        age_days = (today - datetime.datetime.fromisoformat(updated).date()).days
        if age_days >= stale_days:
            nudges.append(
                f"{fm.get('name', path.stem)} has been '{fm.get('stage')}' for "
                f"{age_days} days — worth a follow-up?"
            )
    return nudges


def _unbilled_hours(vault_path: Path, db, config: dict, *, year: int | None = None, month: int | None = None) -> list[str]:
    from app.crm import billing

    today = datetime.date.today()
    year, month = year or today.year, month or today.month
    threshold = config.get("thresholds", {}).get("unbilled_hours_alert", 10)
    nudges = []
    for path, fm in _iter_notes(vault_path, "crm/projects", "project"):
        if fm.get("status") != "active":
            continue
        slug = path.stem.split("--", 1)[1] if "--" in path.stem else path.stem
        hours = billing.hours_logged(db, slug, year=year, month=month)
        if hours >= threshold:
            nudges.append(
                f"{slug}: {hours:.1f}h logged this month — "
                f"consider /invoice {slug} {year}-{month:02d}."
            )
    return nudges


def _expected_ticks_per_week(cadence: str | None) -> float:
    cadence = (cadence or "").strip().lower()
    if cadence == "daily":
        return 7.0
    match = re.match(r"(\d+)x?/week", cadence)
    if match:
        return float(match.group(1))
    return 1.0  # unrecognized cadence — assume "once a week" rather than guessing high


def _missed_habits(vault_path: Path, db, *, today: datetime.date | None = None) -> list[str]:
    today = today or datetime.date.today()
    window_start = today - datetime.timedelta(days=7)
    nudges = []
    for path, fm in _iter_notes(vault_path, "goals/habits", "habit"):
        if fm.get("status") != "active" or "proposed" in (fm.get("tags") or []):
            continue
        name = fm.get("name", path.stem)
        rows = (
            db.client.table("events").select("ts").eq("kind", "habit_tick").eq("user_id", db.user_id)
            .contains("meta", {"habit": name}).execute().data
        )
        ticks_this_week = sum(
            1 for r in rows if datetime.datetime.fromisoformat(r["ts"]).date() >= window_start
        )
        expected = _expected_ticks_per_week(fm.get("cadence"))
        if ticks_this_week < expected * 0.5:
            nudges.append(f"{name}: {ticks_this_week:.0f}/{expected:.0f} expected this week so far.")
    return nudges


def is_quiet_hours(config: dict, now: datetime.datetime | None = None) -> bool:
    now = now or datetime.datetime.now()
    current = now.time()
    for window in config.get("coach", {}).get("quiet_windows") or []:
        start, end = (datetime.time.fromisoformat(t) for t in window)
        if start <= end:
            if start <= current <= end:
                return True
        elif current >= start or current <= end:  # wraps past midnight
            return True
    return False


def _decisions_due_nudges(vault_path: Path) -> list[str]:
    from app.brain import decisions

    due = decisions.due_for_review(vault_path)
    if not due:
        return []
    return [f"{len(due)} decision(s) due for review: {', '.join(p.stem for p in due)}"]


def _resurfacing_nudges(vault_path: Path) -> list[str]:
    from app.brain import resurfacing

    items = resurfacing.resurface_candidates(vault_path)
    return [f"Resurfacing: [[{p.stem}]] — untouched a while, still relevant?" for p in items]


def _balance_nudge(vault_path: Path, db) -> list[str]:
    from app.brain import balance

    counts = balance.area_activity_counts(db)
    warning = balance.flag_imbalance(counts)
    return [warning] if warning else []


def collect_nudges(vault_path: Path, db, config: dict | None = None) -> list[str]:
    config = config if config is not None else load_vault_config(vault_path / "_system" / "config.yaml")
    if not config.get("coach", {}).get("escalation", True):
        return []
    if is_quiet_hours(config):
        return []
    nudges = []
    nudges += _stale_leads(vault_path, config)
    nudges += _unbilled_hours(vault_path, db, config)
    nudges += _missed_habits(vault_path, db)
    nudges += _decisions_due_nudges(vault_path)
    nudges += _resurfacing_nudges(vault_path)
    nudges += _balance_nudge(vault_path, db)
    return nudges


# ---------- Telegram delivery (standalone — no bot polling loop needed) ----------

def send_telegram_message(text: str) -> None:
    import requests

    token = get_env("TELEGRAM_BOT_TOKEN", required=True)
    chat_id = get_env("TELEGRAM_CHAT_ID", required=True)
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    resp.raise_for_status()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="vault")
    parser.add_argument("--morning-brief", action="store_true")
    parser.add_argument("--nudges", action="store_true")
    parser.add_argument("--weekly-review", action="store_true", help="Phase 8: draft the past 7 days' review note")
    parser.add_argument("--dry-run", action="store_true", help="print instead of sending to Telegram")
    args = parser.parse_args()

    vault_path = Path(args.path)
    if args.morning_brief:
        text = compose_morning_brief(vault_path)
        print(text) if args.dry_run else send_telegram_message(text)
    if args.nudges:
        from app.common.db import DB

        db = DB()
        for nudge in collect_nudges(vault_path, db):
            print(nudge) if args.dry_run else send_telegram_message(_frame(nudge))
    if args.weekly_review:
        from app.brain import reviews
        from app.common.db import DB

        db = DB()
        end = datetime.date.today()
        start = end - datetime.timedelta(days=7)
        if args.dry_run:
            print(reviews.compose_review(vault_path, db, start, end))
        else:
            path = reviews.write_review(vault_path, db, start, end)
            send_telegram_message(f"Weekly review drafted: {path.relative_to(vault_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

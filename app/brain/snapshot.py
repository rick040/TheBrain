"""Visual layer, Phase 9 (docs/03-engineering-build-spec.md §11 Phase 9):
"start with Obsidian Bases/Dataview; custom web UI only if justified."
Dataview only reads vault files — it can't query Postgres directly — so
the piece Phase 9 actually needed was a small job that snapshots the
Postgres-backed facts (billing status, next lift suggestions) into plain
vault notes Dataview (and you, in Obsidian) can already read. Everything
else (pipeline, habits, gaps, deliverables) was already live-queryable
from Phase 0's dashboards with no code needed.

Overwrites the SAME snapshot note each run (not append-only growth) —
these are projections of current state, not events.
"""
from __future__ import annotations

from pathlib import Path

from app.common import frontmatter


def _iter_notes(vault_path: Path, subfolder: str, note_type: str | None = None):
    folder = vault_path / subfolder
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob("*.md")):
        fm, _ = frontmatter.read_note(path)
        if note_type and fm.get("type") != note_type:
            continue
        yield path, fm


def write_billing_snapshot(vault_path: Path, db) -> Path:
    from app.crm import billing

    lines = ["# Billing snapshot (auto-generated — overwritten each run, not for hand-editing)", ""]
    lines.append("| Project | Logged | Budget | Remaining |")
    lines.append("|---|---|---|---|")
    for path, fm in _iter_notes(vault_path, "crm/projects", "project"):
        if fm.get("status") != "active":
            continue
        slug = path.stem.split("--", 1)[1] if "--" in path.stem else path.stem
        status = billing.budget_status(vault_path, db, slug)
        lines.append(
            f"| [[{path.stem}]] | {status['logged_hours']:.1f}h | "
            f"{status['budget_hours']:.1f}h | {status['remaining_hours']:.1f}h |"
        )

    fm, _ = frontmatter.new_note_from_template(
        vault_path, "note", overrides={"tags": ["meta", "dashboard", "snapshot"], "freshness": "pointer"}
    )
    out_path = vault_path / "_dashboards" / "billing-snapshot.md"
    frontmatter.write_note(out_path, fm, "\n".join(lines))
    return out_path


def write_health_snapshot(vault_path: Path, db) -> Path:
    from app.health import training

    exercises = set()
    rows = db.client.table("events").select("meta").eq("kind", "lift").eq("user_id", db.user_id).execute().data
    for row in rows:
        exercise = row.get("meta", {}).get("exercise")
        if exercise:
            exercises.add(exercise)

    lines = ["# Health snapshot (auto-generated — overwritten each run)", ""]
    lines.append("| Exercise | Suggested next | Why |")
    lines.append("|---|---|---|")
    for exercise in sorted(exercises):
        result = training.suggest_next_load(db, exercise)
        suggestion = f"{result['suggestion']}kg" if result["suggestion"] is not None else "—"
        lines.append(f"| {exercise} | {suggestion} | {result['reason']} |")

    fm, _ = frontmatter.new_note_from_template(
        vault_path, "note", overrides={"tags": ["meta", "dashboard", "snapshot"], "freshness": "pointer"}
    )
    out_path = vault_path / "_dashboards" / "health-snapshot.md"
    frontmatter.write_note(out_path, fm, "\n".join(lines))
    return out_path


def main() -> int:
    import argparse

    from app.common.db import DB

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="vault")
    args = parser.parse_args()

    vault_path = Path(args.path)
    db = DB()
    billing_path = write_billing_snapshot(vault_path, db)
    health_path = write_health_snapshot(vault_path, db)
    print(f"wrote {billing_path}\nwrote {health_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

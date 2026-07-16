# The vault

This folder is a self-contained Obsidian vault. Open it directly in
Obsidian: **Open folder as vault** → select this `vault/` directory.

## First time setup

1. Settings → Community plugins → turn on community plugins → install and
   enable **Dataview** (the `.obsidian/community-plugins.json` in here
   already lists it, so Obsidian just needs you to approve the install).
2. Open `_dashboards/pipeline.md`, `deliverables.md`, `habits.md`, and
   `gaps.md` — each renders a live query once Dataview is on.
3. Everything tagged `example` (`crm/clients/client--example-co.md`,
   `crm/projects/project--example-co-website.md`, etc.) is seed content so
   the dashboards have something to show. Delete it once you've looked
   around — deleting it doesn't break anything.

## How to add a new note

Copy the matching file from `_templates/` into the right folder (see the
tree below), fill it in, and give it a real `id` (`YYYYMMDD-HHMM`,
`created`, `updated`). `tools/lint.py` (from the repo root) tells you if
you missed a required field.

## Folder map

| Folder | Holds |
|---|---|
| `inbox/` | drop zone for anything unprocessed (Phase 1+: a watcher normalizes it automatically) |
| `daily/` | daily notes + (Phase 5+) the coach's morning brief |
| `crm/` | clients, projects, invoices — the freelance-ops module |
| `goals/` | vision, OKRs, habits |
| `self/` | the self-model: `current/` (descriptive, brain-written), `desired/` (aspirational, interview-seeded), `gap/`, `decisions/`, `experiments/`, `reviews/` |
| `ideas/` | captured business ideas + (Phase 6+) evaluator reports |
| `health/` | training programs + workout logs |
| `knowledge/` | distilled notes and captured external sources |
| `people/` | non-client contacts |
| `_templates/` | one frontmatter stub per note type — never edit notes here directly, copy them |
| `_system/` | `taxonomy.md`, `config.yaml`, `lint-rules.md` — see the repo root `docs/` for the full spec these implement |
| `_dashboards/` | Dataview query boards |

Full rationale: `../docs/01-build-plan.md`. Full schema: `../docs/02-data-structure-and-flow.md`.

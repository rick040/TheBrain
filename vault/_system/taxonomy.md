# Taxonomy — canonical tags & entities

Not rigid. Add tags and entities freely as you capture things — this file
is just the *canonical* list so near-duplicates ("gym" vs "fitness") get
noticed and merged instead of silently forking. From Phase 4 onward the
nightly metabolism job proposes merges here automatically; until then,
tidy it by hand whenever you notice drift.

## Tags

Lowercase, kebab-case. Starter set (delete/extend freely):

- `example` — seed/demo notes shipped with Phase 0; safe to delete once you've looked around
- `meta` — notes about the system itself, not your life
- `follow-up` — needs a next action
- `recurring` — a pattern that's shown up more than once

## Entities

Named things the data is *about* — people, organizations, places, projects.
Entities are the join keys the brain uses to correlate across domains (a
`example-co` entity ties a client note, its project, and later its emails
and time entries together). Aliases let different sources refer to the
same entity without duplicating it.

| entity | aliases | notes |
|---|---|---|
| `example-co` | — | seed example (see `crm/clients/client--example-co.md`); delete once real clients exist |
| `belastingdienst` | `tax-office`, `government` | Dutch tax authority — useful once admin/home-admin data starts flowing in |

## How this grows

- Adding a new data source or note type may introduce new tags/entities —
  add them here as they show up (see `docs/02-data-structure-and-flow.md`
  §13a-§13e for the full extension checklists).
- If two tags or entities clearly mean the same thing, pick the clearer
  name, update the note frontmatter that used the other one, and delete
  the loser from this list.

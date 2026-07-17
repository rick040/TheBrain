---
id: 20260717-0900
type: note
created: 2026-07-17T09:00
updated: 2026-07-17T09:00
source: manual
visibility: interactive
freshness: pointer
tags: [meta, dashboard]
entities: []
links: []
status: active
---

# Goals

OKRs and their linked habits, live from `goals/`. Requires Dataview.

```dataview
TABLE
    objective AS Objective,
    period AS Period,
    linked_habits AS "Linked habits"
FROM "goals/okrs"
WHERE status = "active" AND !contains(tags, "proposed")
```

## Awaiting your review (proposed by the gap engine — see `/review` in Telegram)

```dataview
TABLE objective AS Objective, period AS Period
FROM "goals/okrs"
WHERE contains(tags, "proposed")
```

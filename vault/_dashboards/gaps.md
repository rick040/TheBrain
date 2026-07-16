---
id: 20260716-0833
type: note
created: 2026-07-16T08:33
updated: 2026-07-16T08:33
source: manual
visibility: interactive
freshness: pointer
tags: [meta, dashboard]
entities: []
links: []
status: active
---

# Gaps

`self/gap/` is `sensitive` — this board is for your own review, not
something to leave open on a shared screen (see `docs/02-data-structure-and-flow.md`
§9). Two sections: gaps the (future, Phase 4) gap engine would propose a
fix for, and gaps you've chosen to hold as a tension rather than close —
see `01-build-plan.md` Part B2 for why that distinction matters. Requires
Dataview.

## Open (`hold: false`)

```dataview
TABLE
    size AS Size,
    tension AS Tension
FROM "self/gap"
WHERE status = "active" AND hold = false
SORT size DESC
```

## Held (`hold: true`) — tensions to live with, not fix

```dataview
TABLE
    size AS Size,
    tension AS Tension
FROM "self/gap"
WHERE status = "active" AND hold = true
```

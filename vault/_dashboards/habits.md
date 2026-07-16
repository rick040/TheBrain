---
id: 20260716-0832
type: note
created: 2026-07-16T08:32
updated: 2026-07-16T08:32
source: manual
visibility: interactive
freshness: pointer
tags: [meta, dashboard]
entities: []
links: []
status: active
---

# Habits

Streaks are just frontmatter for now (Phase 0, hand-updated). From Phase 1
onward the Telegram bot's `/done <habit>` ticks these and the streak count
moves to Postgres — this board keeps working either way, since Dataview
just reads whatever's in the note. Requires Dataview.

```dataview
TABLE
    cadence AS Cadence,
    streak AS Streak,
    linked_kr AS "Linked KR"
FROM "goals/habits"
WHERE status = "active"
SORT streak DESC
```

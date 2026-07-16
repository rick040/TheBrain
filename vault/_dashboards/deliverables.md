---
id: 20260716-0831
type: note
created: 2026-07-16T08:31
updated: 2026-07-16T08:31
source: manual
visibility: interactive
freshness: pointer
tags: [meta, dashboard]
entities: []
links: []
status: active
---

# Open deliverables

Flattens the `deliverables` array across every active project. Requires
Dataview.

```dataview
TABLE WITHOUT ID
    file.link AS Project,
    d.task AS Deliverable,
    d.due AS Due
FROM "crm/projects"
FLATTEN deliverables AS d
WHERE status = "active" AND !d.done
SORT d.due ASC
```

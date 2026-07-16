---
id: 20260716-0830
type: note
created: 2026-07-16T08:30
updated: 2026-07-16T08:30
source: manual
visibility: interactive
freshness: pointer
tags: [meta, dashboard]
entities: []
links: []
status: active
---

# Pipeline

Requires the **Dataview** community plugin (Settings → Community plugins →
enable). Once installed, this table renders live from `crm/projects/`.

```dataview
TABLE
    client AS Client,
    stage AS Stage,
    budget_hours AS "Budget (h)",
    rate AS "Rate (€/h)"
FROM "crm/projects"
WHERE status = "active"
SORT stage ASC
```

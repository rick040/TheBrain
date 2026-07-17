---
id: 20260717-0901
type: note
created: 2026-07-17T09:01
updated: 2026-07-17T09:01
source: manual
visibility: interactive
freshness: pointer
tags: [meta, dashboard]
entities: []
links: []
status: active
---

# Decisions due for review

From `self/decisions/` — logged with an `expected` outcome and a
`review_on` date (docs/03-engineering-build-spec.md §8.5). Also nudged
proactively by the coach (`app/brain/decisions.py`). Requires Dataview.

```dataview
TABLE
    chosen AS Chosen,
    expected AS Expected,
    review_on AS "Review on"
FROM "self/decisions"
WHERE status = "active" AND !outcome AND date(review_on) <= date(today)
SORT review_on ASC
```

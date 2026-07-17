"""A minimal fake of the supabase-py chainable query builder, just
enough surface for app/crm/billing.py's calls, so Phase 3 can be tested
without real Supabase credentials (docs/00-PLAN.md — SUPABASE_SERVICE_ROLE_KEY
and THEBRAIN_USER_ID are yours to fill in, not something to fabricate)."""
from __future__ import annotations


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, value))
        return self

    def contains(self, key, value):
        self._filters.append(("contains", key, value))
        return self

    def execute(self):
        rows = self._rows
        for kind, key, value in self._filters:
            if kind == "eq":
                rows = [r for r in rows if r.get(key) == value]
            elif kind == "contains":
                rows = [r for r in rows if (r.get(key) or {}).items() >= value.items()]
        return _FakeResult(rows)


class _FakeClient:
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table

    def table(self, name):
        return _FakeQuery(list(self._rows_by_table.get(name, [])))


class FakeDB:
    """Stands in for app.common.db.DB in tests — same public shape
    (`.client`, `.user_id`), backed by in-memory rows instead of Postgres."""

    def __init__(self, events: list[dict] | None = None, user_id: str = "test-user-id"):
        self.user_id = user_id
        self.client = _FakeClient({"events": events or []})

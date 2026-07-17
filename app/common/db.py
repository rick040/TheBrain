"""Thin wrapper around the Postgres telemetry store (Supabase now,
self-hosted later — docs/00-PLAN.md). Single-user: the backend connects
with the Supabase *service role* key (bypasses RLS; RLS still protects
the tables if they're ever queried through a client/anon key) and tags
every row with a fixed THEBRAIN_USER_ID rather than doing a full Supabase
Auth sign-in for a backend-only process.

Needs in .env (see .env.example):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY   (Dashboard -> Project Settings -> API -> service_role)
    THEBRAIN_USER_ID            (any stable UUID4 you generate once and keep forever;
                                  `python3 -c "import uuid; print(uuid.uuid4())"`)
"""
from __future__ import annotations

import datetime
from typing import Any

from app.common.config import get_env


class DB:
    def __init__(self) -> None:
        # Imported lazily so `import app.common.db` doesn't require the
        # `supabase` package for code paths that don't touch the DB
        # (e.g. running tools/lint.py, or llm.py in mock mode).
        from supabase import create_client

        url = get_env("SUPABASE_URL", required=True)
        key = get_env("SUPABASE_SERVICE_ROLE_KEY", required=True)
        self.user_id = get_env("THEBRAIN_USER_ID", required=True)
        self.client = create_client(url, key)

    def insert_event(
        self,
        kind: str,
        *,
        value: float | None = None,
        meta: dict[str, Any] | None = None,
        source: str | None = None,
        ts: datetime.datetime | None = None,
    ) -> dict:
        row = {
            "user_id": self.user_id,
            "ts": (ts or datetime.datetime.now()).isoformat(),
            "kind": kind,
            "value": value,
            "meta": meta or {},
            "source": source,
        }
        return self.client.table("events").insert(row).execute().data[0]

    def insert_insight(
        self,
        *,
        about: str,
        statement: str,
        confidence: float,
        evidence: list | None = None,
        wrote_to: str | None = None,
        ts: datetime.datetime | None = None,
    ) -> dict:
        row = {
            "user_id": self.user_id,
            "ts": (ts or datetime.datetime.now()).isoformat(),
            "about": about,
            "statement": statement,
            "confidence": confidence,
            "evidence": evidence or [],
            "wrote_to": wrote_to,
        }
        return self.client.table("insights").insert(row).execute().data[0]

    def upsert_embedding(self, ref: str, vec: list[float], kind: str) -> dict:
        row = {
            "ref": ref,
            "user_id": self.user_id,
            "vec": vec,
            "kind": kind,
            "updated": datetime.datetime.now().isoformat(),
        }
        return self.client.table("embeddings").upsert(row).execute().data[0]

    def search_embeddings(self, query_vec: list[float], *, limit: int = 5) -> list[dict]:
        """RAG retrieval — backs the Telegram bot's /ask command."""
        return self.client.rpc(
            "match_embeddings",
            {"query_embedding": query_vec, "match_count": limit, "for_user": self.user_id},
        ).execute().data

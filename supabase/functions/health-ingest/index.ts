// Health Connect-style ingestion endpoint (docs/03-engineering-build-spec.md
// Phase 7). Meant to be called from an Android automation (Tasker / HTTP
// Shortcuts) exporting Health Connect data, not from a browser session —
// so it authenticates via a shared secret header, not a Supabase user JWT
// (deployed with verify_jwt=false for exactly that reason).
//
// POST body: a single {kind, value, ts?, meta?} object, or an array of them.
//   kind: "steps" | "sleep" | "hr"
//   value: numeric payload (step count, sleep minutes, bpm...)
//   ts: ISO timestamp, defaults to now if omitted
//   meta: optional JSON object
//
// Required secrets (set via Supabase Dashboard -> Edge Functions -> Manage
// secrets, or `supabase secrets set` — NOT settable via MCP, a manual step
// documented in docs/05-manual-setup-checklist.md):
//   INGEST_SECRET     — shared secret; caller sends it as X-Ingest-Secret
//   THEBRAIN_USER_ID   — same fixed UUID app/common/db.py uses
// SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are auto-provided by the
// Supabase platform inside every Edge Function — nothing to set for those.

import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const INGEST_SECRET = Deno.env.get("INGEST_SECRET");
const THEBRAIN_USER_ID = Deno.env.get("THEBRAIN_USER_ID");

const ALLOWED_KINDS = new Set(["steps", "sleep", "hr"]);

Deno.serve(async (req: Request) => {
  if (!INGEST_SECRET || req.headers.get("x-ingest-secret") !== INGEST_SECRET) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }
  if (!THEBRAIN_USER_ID) {
    return new Response(
      JSON.stringify({ error: "server not configured: THEBRAIN_USER_ID secret is unset" }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid JSON body" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  const items = Array.isArray(body) ? body : [body];
  const rows = [];
  for (const item of items) {
    const { kind, value, ts, meta } = (item ?? {}) as Record<string, unknown>;
    if (typeof kind !== "string" || !ALLOWED_KINDS.has(kind)) {
      return new Response(JSON.stringify({ error: `unsupported kind '${kind}'` }), {
        status: 400,
        headers: { "content-type": "application/json" },
      });
    }
    rows.push({
      user_id: THEBRAIN_USER_ID,
      kind,
      value: value ?? null,
      ts: (ts as string) ?? new Date().toISOString(),
      meta: meta ?? {},
      source: "health",
    });
  }

  const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);
  const { error } = await supabase.from("events").insert(rows);
  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "content-type": "application/json" },
    });
  }
  return new Response(JSON.stringify({ inserted: rows.length }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
});

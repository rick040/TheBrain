# TheBrain — reconciliation notes

## Context

Two things converged on this project independently:

1. **An audit of `oslife`** (rick040/OSLIFE, the predecessor to this repo):
   it became cluttered — zero tests, ~2,600-3,000 LOC of duplication, a live
   Notion dual-sync bug, and 30+ screens mixing personal life with
   freelance-business tooling. But its `docs/DATA-ARCHITECTURE.md` already
   contains a genuinely good, *implemented* design: an append-only event
   log, a universal envelope (id/type/domain/tier/confidence/status), an
   hourly inference engine with a Telegram confirm/reject loop, and
   "promotion" rules where repeated patterns become new structure (a real
   rule: 3× vet visits in 6 weeks → auto-creates a health record —
   precisely the "I went to the vet 3× this week, is this a thing?"
   behavior this project wants).
2. **A design conversation** (preserved in `Second_Brain_Chat__16_juli.pdf`,
   not in this repo): a self-model/gap-engine as the spine ("close the
   distance between who you are and who you want to become, without
   flattening the nuance"), four domain modules (CRM/freelance-ops,
   Goals→OKR→Habits, a Business-Idea Evaluator, Health/Gym), a two-store
   design (Obsidian vault for what you see, a database for telemetry), a
   Telegram coach with self-compassion guardrails, NL-specific invoicing,
   and a 10-phase (0-9) build plan with Definition-of-Done gates between
   phases.

That design conversation is excellent and is what `01-build-plan.md`,
`02-data-structure-and-flow.md`, and `03-engineering-build-spec.md` in this
`docs/` folder are built from. This file records: what's already decided,
the one open question that got resolved, what's reused from oslife, and a
few corrections layered on top.

## Decisions already locked (don't relitigate)

- **oslife keeps running in parallel**; TheBrain is a fresh build; migration/cutover happens later, not now.
- **Business tooling (CRM/freelance ops) is in scope from day one** — Phase 3, the very first domain module built after the foundation.
- **No NAS yet** — the stack must work today on whatever's available and move to NAS hardware later without a redesign.
- **Interface = Telegram bot + Obsidian only** — no custom UI until Phase 9 (last).
- **Region NL**: invoicing is NL-compliant (sequential per-year numbering, BTW 21% + reverse-charge line, KVK/BTW-id fields, IBAN).
- **Encryption**: sensitive-only via gocryptfs — `self/`, `crm/invoices/`, `health/`, and anything tagged `visibility: sensitive`. Rest of the vault stays plain.
- **llm() default**: Claude Haiku for high-volume work (normalizing, tagging, coach messages, metabolism); routes to a stronger model on-demand for the evaluator's deep report and the weekly gap-review synthesis.
- **The self-model is the spine**: `self/current/` (descriptive, brain-derived, low-confidence-until-earned) and `self/desired/` (aspirational, seeded by an onboarding interview) — the gap between them generates north-stars → OKRs → habits → coach nudges. Nuance is structural: every trait has `confidence`, `contexts` (true *when*), `polarity` (strength/tension/neutral, never good/bad), and contradictions are *held* (`hold: true`), not force-resolved. A **self-compassion guardrail** is a hard requirement, not a nicety — an aggressive coach plus a gap engine is the #1 way systems like this get abandoned.

## The one open question that got resolved: storage substrate

The original design conversation ended mid-thought on exactly this:
*"Kunnen we hem ook eerst bouwen op Supabase in plaats van lokaal... totdat
ik mijn NAS heb?"* Resolution:

**Build on Postgres, not SQLite — Supabase-hosted now, self-hosted on the
NAS later.** Concretely, the one change from the original spec's
`telemetry.sqlite + sqlite-vec`: use **Postgres + pgvector** (Supabase is
just hosted Postgres with pgvector already enabled). Reasons:
- A laptop isn't a viable always-on backend for a Telegram coach that needs to push a 7:30am brief and receive live nudges — Supabase already solves "always reachable" for free/cheap, today, with no NAS purchase required.
- The migration to the NAS later becomes a `pg_dump` → `pg_restore`, not a rewrite — Postgres-on-Supabase and Postgres-on-NAS are the same database.
- It costs nothing to decide before Phase 0 code exists, and real work to change later.

Component mapping (now → later — nothing else changes):

| Component | Now (Supabase) | Later (NAS) |
|---|---|---|
| Telemetry + insights tables | Postgres | same Postgres, self-hosted |
| Embeddings/search | pgvector | same |
| Inbox/file storage | Storage bucket (S3-compatible) | MinIO |
| Scheduled jobs (metabolism, gap-review) | pg_cron / scheduled Edge Functions | systemd timers |
| Telegram coach webhook | Edge Function | Python service |
| Python workers (OCR/Whisper/normalizer) | small VPS (~€5/mo) or batch on your laptop when it's on | same host as NAS |
| LLM calls (`llm()`) | Edge Function → Anthropic API | same, local Ollama optional once you add a GPU |

**Two caveats that still apply:**
1. **The Obsidian vault itself stays local**, synced via Syncthing/git to phone and laptop — Supabase has no filesystem for Obsidian to edit directly. Only the *telemetry + brain* layer lives on Supabase; the human-facing knowledge layer stays local, which is exactly the two-store split the spec already uses.
2. **Supabase Edge Functions are Deno/TypeScript, not Python** — OCR (Tesseract) and transcription (faster-whisper) don't run there. Run the Python watcher/normalizer/gap-engine either on a cheap always-on VPS, or batch them on your own machine whenever it's on (not latency-critical the way the coach webhook is).

**Refinement using a mechanism the spec already has**: use the
`visibility: sensitive` tier not just to decide what the AI can see, but
*where data physically lives* during the interim. `sensitive` records
(self-model, finances, health) stay in the local gocryptfs-encrypted vault
only — never uploaded to Supabase — until the NAS exists. Only
`interactive`/`brain-only` telemetry (steps, location, time entries) goes to
Supabase in the interim.

**Cost note**: Supabase's free tier pauses on inactivity and won't sustain
an always-on coach; budget for the Pro tier (~$25/mo, verify current
pricing) until the NAS replaces it.

## Reuse from oslife (concrete — don't re-derive this)

- oslife's `events` + `type_registry` envelope (id/type/domains/tier/confidence/status) **is** this spec's universal frontmatter contract + `insights` table, already proven in production SQL. Port the `emit_event()` trigger pattern directly rather than redesigning it.
- oslife's `confirm_inference()` + Telegram `infer:` callback flow **is** the coach's required "all self-model/money changes are proposals until confirmed via Telegram" rule (engineering spec §8.3, §12.1). Reuse the callback-button pattern verbatim.
- oslife's promotion rules (e.g., P1: 3× vet_visit in 6 weeks → new `health_condition`) are the direct precursor to this spec's coach triggers + gap-engine proposals — same mechanism, generalize the rule table instead of starting from zero.
- **Explicitly not carried over**: the Notion dual-sync path (has a live bug), the 30-screen React SPA, or any side-business screens as bespoke UI (Buurtkaart/Eyes/Dakmeester) — none of that belongs in TheBrain.

## Corrections / improvements layered on top of the original spec

1. **Storage**: Postgres+pgvector over SQLite+sqlite-vec — covered above. `02-data-structure-and-flow.md` and `03-engineering-build-spec.md` in this repo already reflect this.
2. **Model IDs**: current exact IDs are Haiku 4.5 = `claude-haiku-4-5-20251001`, Sonnet 5 = `claude-sonnet-5` — verify against `docs.claude.com` at build time regardless, since these move. For the hardest jobs — the evaluator's deep report, the weekly gap-review synthesis, **and the metabolism pass that revises `self/current` traits** (getting this subtly wrong quietly corrupts the self-model everything else depends on) — consider an on-demand escalation to Opus 4.8 (`claude-opus-4-8`) above the existing Haiku→Sonnet routing, gated the same way the deep report already is (cheap by default, borrows power only when asked).
3. **Data migration from oslife**: a non-blocking, low-priority task for once Phase 3 (CRM) and Phase 7 (Health) exist — a one-time script mapping oslife's `finance_tx`/`health_daily_stats`/`health_sleep`/`projects`/`clients` rows into the new note/event schema, so history isn't lost whenever oslife is eventually retired. Doesn't block Phase 0-2.
4. **The onboarding interview** (`04-self-model-interview.md`) is drafted in full but needs to be filled in by hand — that's a you-must-do-it action, not a build task. It's the real gate on Phase 2 ("Seed the self"); do it whenever the questions catch you at a good moment, partial answers are fine.
5. **Business-Idea Evaluator (Phase 6)**: confirmed buildable exactly as scoped — an MCP server exposing vault read/write + web search to a Claude Skill that encodes the analyst workflow. Both primitives (MCP servers, Claude Skills) are real, supported building blocks, so §9 of the engineering spec is implementable as written, not aspirational.

## Immediate next steps (yours, not build tasks)

- Fill in `04-self-model-interview.md` at your own pace — it's the gate on Phase 2.
- Create a fresh Supabase project (separate from oslife's `nhyunnnmdcmojvkxrbpl`) to host the telemetry/brain layer per the storage decision above.
- Gather the NL business details Phase 3 needs: KVK number, BTW-id, IBAN, business name/address for the invoice template.

## Verification

Each phase carries its own Definition-of-Done in `03-engineering-build-spec.md`
§11 — e.g. Phase 0 is done when notes create from templates and the
linter/Dataview boards work with zero AI; Phase 1 is done when dropping a
txt/URL/screenshot/voice-note/PDF each produces a correctly-typed,
lint-passing note or event within 60s. Keep using those gates unmodified —
don't start a phase until the prior one's DoD is met, which is the
mechanism that keeps this from turning into oslife's
half-finished-everything problem again.

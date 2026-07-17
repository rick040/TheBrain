# TheBrain

A local-first second brain: one inbox for everything (thoughts, transactions,
health data, messages, articles, photos of letters), a self-model that tracks
the gap between who you are and who you want to become, and four domain
modules (freelance CRM, goals/OKRs/habits, a business-idea evaluator,
health/gym) — coached over Telegram, browsed in Obsidian.

Replaces `oslife` (which stays running in parallel until this covers what it
needs to and gets cut over deliberately, not on a deadline).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env               # fill in the secrets — see below
python3 tools/lint.py --path vault  # "lint passed — 10 note(s) OK."
python3 -m pytest -q                # 34 passed, all offline (mock llm/embeddings, fake DB)
git config core.hooksPath hooks     # enable the pre-commit lint gate
```

Open `vault/` directly in Obsidian (see `vault/README.md` for the one-time
Dataview setup) and start replacing the notes tagged `example` with your
own.

To run the capture pipeline for real:

```bash
python3 -m app.watcher --path vault --once   # process anything already in vault/inbox/
python3 -m app.watcher --path vault          # or stay running (Syncthing's target on your phone/NAS)
python3 -m app.bot.telegram_bot              # the Telegram bot (capture, /track, /invoice, /done, /lift, /ask)
```

Needs `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`THEBRAIN_USER_ID`, and `TELEGRAM_BOT_TOKEN` in `.env` for capture; add
`BUSINESS_NAME`, `BUSINESS_ADDRESS`, `BUSINESS_KVK_NUMBER`,
`BUSINESS_BTW_ID`, `BUSINESS_IBAN` for `/invoice` — see `.env.example`.
Never commit `.env`; it's gitignored.

## Start here

1. [`docs/00-PLAN.md`](docs/00-PLAN.md) — how this repo's docs relate to each
   other, the reconciliation notes between the original design chat and the
   oslife audit, and the one architecture decision (Postgres over SQLite)
   made after the original spec was written.
2. [`docs/01-build-plan.md`](docs/01-build-plan.md) — the "what and why":
   the self-model/gap-engine, the four domain modules, the coach, the
   roadmap.
3. [`docs/02-data-structure-and-flow.md`](docs/02-data-structure-and-flow.md) —
   the canonical technical spec: vault tree, frontmatter contract, note type
   catalog, database schema, data flows, extension guides.
4. [`docs/03-engineering-build-spec.md`](docs/03-engineering-build-spec.md) —
   the self-contained developer handoff: phases 0-9, each with a Definition
   of Done. Build strictly in phase order.
5. [`docs/04-self-model-interview.md`](docs/04-self-model-interview.md) — fill
   this in yourself, at your own pace. It seeds `self/current` and
   `self/desired`, the two models the whole system works to close the gap
   between. This is the one piece that needs you, not code — it gates
   Phase 2.

## Status

- **Phase 0 (foundation) — done.** Vault tree, 18 note-type templates,
  taxonomy/config/lint-rules, `tools/lint.py` (+ pre-commit hook + CI),
  four Dataview dashboards, nightly auto-commit script.
- **Phase 1 (capture + normalize) — done.** `app/llm.py` (Anthropic +
  mock provider, tier routing), `app/common/{config,db,frontmatter}.py`,
  `app/watcher.py` + `app/normalizer.py` (text/URL live; OCR/voice/PDF
  wired but need `requirements-media.txt` + system deps), `app/embedder.py`
  (pgvector, mock embedding provider until a worker host runs Ollama —
  see `docs/00-PLAN.md`), `app/bot/telegram_bot.py` (capture, `/track`,
  `/done`, `/lift`, `/ask` RAG). Postgres schema is live on a fresh
  Supabase project ("TheBrain", separate from oslife's) — see
  `supabase/migrations/`. 24 tests pass offline against the mock
  provider; the real Anthropic key and Telegram bot token were verified
  live. **Not yet done**: nothing is running continuously anywhere (this
  repo doesn't host a server) — you still need to run
  `python3 -m app.watcher` and `python3 -m app.bot.telegram_bot` on
  whatever machine will keep them alive (a VPS, or your laptop while
  it's on) per `docs/00-PLAN.md`. `SUPABASE_SERVICE_ROLE_KEY` and
  `THEBRAIN_USER_ID` in `.env.example` are still yours to fill in (grab
  the key from the Supabase dashboard; generate the UUID once and keep
  it forever).
- **Phase 2 (seed the self) — parked, on purpose.** Not blocking; nothing
  after it in this list needed it, since CRM/billing don't read the
  self-model (only the Phase 4 gap engine does). Pick it up whenever.
- **Phase 3 (CRM / freelance ops) — partially done**, reordered ahead of
  Phase 2 to unblock testing the capture layer. Built: `app/crm/billing.py`
  (project-level time rollup + `budget_status`, period-based invoice
  computation, a persistent per-year counter for NL's sequential-no-gaps
  invoice numbering, EU reverse-charge auto-detection from a client's
  `country`/`vat_id`), `app/crm/invoice_pdf.py` (renders the compliant
  PDF — KVK/BTW-id, line items, VAT or reverse-charge line, IBAN), and
  two new/changed bot commands: **`/track` now takes a project slug, not
  a client name** (budget_hours/rate live on the project note), and
  `/invoice <project-slug> <YYYY-MM>` drafts the note + PDF and sends the
  PDF back to you in chat — nothing auto-sends anywhere else, that
  approval step is the point. 10 new tests (billing math, VAT/reverse-charge,
  invoice numbering, and one full compute→write→lint integration test).
  **Deferred, not done**: the Gmail comms-log (needs a Google Cloud OAuth
  app + a browser consent flow this session can't do) and per-project file
  auto-filing (needs your own Syncthing setup). **Still yours to do**:
  the example client/project notes haven't been swapped for real ones yet
  — give me real client/project details (or edit them yourself in
  Obsidian) whenever; and `BUSINESS_KVK_NUMBER`/`BUSINESS_BTW_ID`/
  `BUSINESS_IBAN`/`BUSINESS_NAME`/`BUSINESS_ADDRESS` in `.env` are needed
  before `/invoice` produces a real invoice rather than placeholder text.
- Phases 4-9: see `docs/03-engineering-build-spec.md` §11.

## Security note

An Anthropic API key, Supabase project URL, and Telegram bot token were
shared in chat during this build and used to verify Phase 1 end-to-end —
none of them are in this repo (`.env` is gitignored; only `.env.example`
with blank placeholders is committed). Since they passed through a chat
transcript, treat them as potentially exposed: rotate the Telegram bot
token via @BotFather (`/revoke`) and regenerate the Anthropic key at
console.anthropic.com if you haven't already, then update your local
`.env`.
